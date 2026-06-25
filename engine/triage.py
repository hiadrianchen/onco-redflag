#!/usr/bin/env python3
"""OncoRedFlag 确定性红旗规则引擎。

设计红线（见 ../SAFETY.md）：
- 纯函数 + 纯本地：不调用 LLM、不联网。判定只由 rules/redflags.yaml 决定。
- fail-safe：先判通用急症 RED；范围外 / 信息缺失 / 超窗一律 ESCALATE（升级就医）；
  绝不输出"可以居家观察 / 无需处理"这类安抚结论（没有 GREEN 级）。
- 输入强校验：脏输入（字符串数值、无法解析）一律降为 None → 触发升级，绝不 TypeError 崩溃。
- LLM（在 MCP redflag-intake 里）只负责把自由文本抽成下面的结构化字段，不参与判定。

【唯一权威评估顺序】（redflags.yaml / SAFETY.md / 本 docstring 三处必须与此一致）：
  1) 规范化输入（类型强转，无法转 → None）
  2) 通用急症 RED（applies_when 为空 → 任何人群先拦）
  3) 范围守门（人群）：儿童 / 免疫 / 靶向 / 放疗 / 其他治疗、血液瘤 / 移植 / 孕产 → ESCALATE
  4) 专项 RED（化疗 0–21 天）——明确红旗优先于"信息不足 / 超窗"，不被无关缺失降级
  5) 关键信息缺失（治疗类型 / 化疗天数 / 体温）→ ESCALATE
  6) 窗口守门（化疗天数 <0 或 >21）→ ESCALATE
  7) 低危 AMBER（化疗 0–21 天）
  8) NO_REDFLAG（明确不安抚；仅在"范围内 + 信息齐 + 在窗 + 无任何红旗"时可达）

case dict 字段 schema（缺失用 None）：
  treatment_type: 'cytotoxic_chemo'|'immunotherapy'|'targeted'|'radiation'|'other'|None
  days_since_last_chemo: int|None        # 末次化疗至今天数；本工具仅覆盖 0–21
  temp_c: float|None
  temp_route: 'oral'|'axillary'|'ear'|'forehead'|None   # 阈值按口温；非口温仅加提示，不下调风险
  temp_duration_min: int|None            # 仅记录；不再用于下调发热风险
  rigors / dyspnea / chest_pain / cyanosis / altered_consciousness: bool|None
  active_bleeding / hematemesis_melena: bool|None
  vomiting_unable_intake_hours: int|None
  diarrhea_count_per_day: int|None
  diarrhea_bloody / has_cvc / cvc_site_inflamed: bool|None
  age: int|None
  patient_group: 'solid_tumor'|'hematologic'|'transplant'|'pregnant'|None

范围默认假设（见 SAFETY.md §6）：本工具面向**成人实体瘤化疗**患者。age/patient_group
缺失时按该默认处理（不因缺这两项就升级，否则工具不可用）；但只要抽到禁忌信号即排除。
"""
import os
import sys
import json
import yaml

RULES_PATH = os.path.join(os.path.dirname(__file__), os.pardir, "rules", "redflags.yaml")

CRITICAL_FIELDS = ("treatment_type", "days_since_last_chemo", "temp_c")
CHEMO_WINDOW = (0, 21)
OUT_OF_SCOPE_TREATMENTS = ("immunotherapy", "targeted", "radiation", "other")
OUT_OF_SCOPE_GROUPS = ("hematologic", "transplant", "pregnant")

NUM_FIELDS = ("days_since_last_chemo", "temp_c", "temp_duration_min",
              "vomiting_unable_intake_hours", "diarrhea_count_per_day", "age")
BOOL_FIELDS = ("rigors", "dyspnea", "chest_pain", "cyanosis", "altered_consciousness",
               "active_bleeding", "hematemesis_melena", "diarrhea_bloody",
               "has_cvc", "cvc_site_inflamed")
STR_FIELDS = ("treatment_type", "temp_route", "patient_group")

DISCLAIMER = (
    "本工具仅做有限的'危险信号'核对，不诊断、不替代医护判断，也不是急救通道。"
    "危急情况请直接拨打 120。"
)
PREP_CHECKLIST = [
    "末次化疗/治疗的日期与方案名称",
    "症状出现时间与变化过程",
    "体温数值与测量方式（口温/腋温/耳温）、复测记录",
    "正在使用的药物（含退烧药、止吐药等）",
    "是否有 PICC/输液港等中心静脉导管",
    "既往过敏史与基础疾病",
]


# ---------- 输入规范化（防脏输入崩溃，fail-safe 到 None） ----------
def _to_num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return float(v.strip())
        except ValueError:
            return None
    return None


def _to_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "yes", "y", "是", "1"):
            return True
        if s in ("false", "no", "n", "否", "0"):
            return False
    return None  # 数字 / 其它一律不猜


def normalize_case(case):
    """把任意来源的 case 强转为规范类型；无法解析的字段降为 None（→ 触发升级）。"""
    norm = {}
    for f in NUM_FIELDS:
        norm[f] = _to_num(case.get(f))
    for f in BOOL_FIELDS:
        norm[f] = _to_bool(case.get(f))
    for f in STR_FIELDS:
        v = case.get(f)
        norm[f] = v.strip() if isinstance(v, str) else (v if v is None else str(v))
    return norm


# ---------- 规则匹配 ----------
def _cond_match(cond, case):
    for key, expected in cond.items():
        if key.endswith("_min"):
            field, op = key[:-4], "ge"
        elif key.endswith("_max"):
            field, op = key[:-4], "le"
        else:
            field, op = key, "eq"
        actual = case.get(field)
        if actual is None:
            return False
        try:
            if op == "ge" and not actual >= expected:
                return False
            if op == "le" and not actual <= expected:
                return False
            if op == "eq" and not actual == expected:
                return False
        except TypeError:
            return False  # 类型不可比一律视为不匹配（fail-safe）
    return True


def _applies(rule, case):
    aw = rule.get("applies_when") or {}
    return _cond_match(aw, case) if aw else True


def _triggered(rule, case):
    return any(_cond_match(t, case) for t in rule.get("triggers", []))


def load_rules(path=RULES_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["rules"]


def _out_of_scope(case):
    age = case.get("age")
    if age is not None and age < 18:
        return "儿童（age<18）"
    tt = case.get("treatment_type")
    if tt in OUT_OF_SCOPE_TREATMENTS:
        return "treatment_type=%s（未覆盖）" % tt
    pg = case.get("patient_group")
    if pg in OUT_OF_SCOPE_GROUPS:
        return "patient_group=%s（未覆盖）" % pg
    return None


def _missing_critical(case):
    return [f for f in CRITICAL_FIELDS if case.get(f) is None]


def _temp_route_note(case):
    if case.get("temp_c") is not None and case.get("temp_route") in ("axillary", "ear", "forehead"):
        return "体温为非口温测量，可能高估或低估，建议用口温规范复测（本工具不因此下调风险等级）。"
    return None


def _decision(level, case=None, rule=None, **kw):
    d = {"level": level, "disclaimer": DISCLAIMER}
    if rule is not None:
        d["rule_id"] = rule["id"]
        d["reason"] = rule["desc"]
        d["action"] = rule["action"]
        d["source"] = rule.get("source")
        st = rule.get("status")
        d["source_status"] = st
        if st and st != "validated":
            if "draft" in st:
                d["source_note"] = "来源待核证（未循证），仅供开发参考。"
            elif st == "validated-operational":
                d["source_note"] = "定性依据见所引指南；具体数值为本工具的保守操作化阈值，非指南逐字数值。"
    d.update(kw)
    if level in ("RED", "AMBER", "ESCALATE"):
        d["prepare_for_visit"] = PREP_CHECKLIST
    if case is not None:
        note = _temp_route_note(case)
        if note:
            d["temp_route_note"] = note
    return d


def evaluate(raw_case, rules=None):
    """对单个 case 做确定性判定，返回决策 dict。raw_case 会先被规范化。"""
    rules = rules if rules is not None else load_rules()
    case = normalize_case(raw_case)

    reds = [r for r in rules if r["level"] == "RED"]
    universal_reds = [r for r in reds if not r.get("applies_when")]
    scoped_reds = [r for r in reds if r.get("applies_when")]
    ambers = [r for r in rules if r["level"] == "AMBER"]

    # 2) 通用急症（任何人群）
    for r in universal_reds:
        if _triggered(r, case):
            return _decision("RED", case, r)

    # 3) 范围守门（人群）
    oos = _out_of_scope(case)
    if oos:
        return _decision("ESCALATE", case, rule_id="ESC-SCOPE",
                         reason="超出工具覆盖范围：%s" % oos,
                         action="本工具仅覆盖成人实体瘤细胞毒化疗后 0–21 天；你的情况超出范围，"
                                "无法排除风险，请直接联系治疗团队或前往急诊。")

    # 4) 专项 RED（在窗内才会命中；优先于信息不足/窗口守门）
    for r in scoped_reds:
        if _applies(r, case) and _triggered(r, case):
            return _decision("RED", case, r)

    # 5) 关键信息缺失
    missing = _missing_critical(case)
    if missing:
        return _decision("ESCALATE", case, rule_id="ESC-INFO",
                         reason="关键信息缺失：%s" % ", ".join(missing),
                         action="缺少判断所需的关键信息，无法排除风险。请联系治疗团队；"
                                "若症状明显或不放心，请前往急诊。",
                         missing_fields=missing)

    # 6) 窗口守门（到这里 treatment=cytotoxic_chemo 且 days 已是数值）
    d = case.get("days_since_last_chemo")
    if not (CHEMO_WINDOW[0] <= d <= CHEMO_WINDOW[1]):
        return _decision("ESCALATE", case, rule_id="ESC-WINDOW",
                         reason="末次化疗天数 %s 超出本工具覆盖窗口（0–21 天）" % d,
                         action="你的情况超出本工具覆盖的化疗后 0–21 天窗口（或日期异常），"
                                "无法排除风险，请联系治疗团队；若有不适请前往急诊。")

    # 7) AMBER
    for r in ambers:
        if _applies(r, case) and _triggered(r, case):
            return _decision("AMBER", case, r)

    # 8) 未触发红旗（明确不安抚）
    return _decision("NO_REDFLAG", case, rule_id=None,
                     reason="未匹配到本工具覆盖的红旗信号",
                     action="本工具未覆盖到需要立即就医的红旗信号——但这不代表安全。本工具只检查"
                            "有限的危险信号，覆盖范围窄。若症状持续/加重，或你有任何不放心，请联系治疗团队。")


if __name__ == "__main__":
    demo = {
        "treatment_type": "cytotoxic_chemo",
        "days_since_last_chemo": 7,
        "temp_c": 38.5,
        "temp_route": "oral",
    }
    print(json.dumps(evaluate(demo), ensure_ascii=False, indent=2))
