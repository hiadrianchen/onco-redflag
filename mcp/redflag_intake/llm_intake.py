#!/usr/bin/env python3
"""自由文本 intake（模型无关 + StepFun 适配器）。

安全立场（见 ../../SAFETY.md）：
- LLM **只抽取不判断**：自由文本 → 结构化 case 字段；判级永远由确定性引擎做。
- 抽取失败/无法解析 → 返回全 None（→ 引擎走信息不足 ESCALATE），绝不臆造、绝不崩溃。
- **关键词兜底**：即使 LLM 漏抽，文本里出现儿童/血液瘤/移植/孕产/免疫/靶向/放疗等禁忌信号，
  也强制落到 case → 引擎在范围守门处升级（宁可过度转诊）。

模型无关：`extract(text, llm=callable)`，llm 接收 prompt 返回字符串。缺省用 StepFun（读 STEPFUN_API_KEY）。
"""
import os
import re
import json
import urllib.request
import urllib.error

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "engine"))
from triage import normalize_case, NUM_FIELDS, BOOL_FIELDS, STR_FIELDS  # noqa: E402

ALLOWED = list(NUM_FIELDS) + list(BOOL_FIELDS) + list(STR_FIELDS)

EXTRACT_PROMPT = """你是医疗信息抽取器，只抽取、不判断、不诊断。把用户的中文描述抽成 JSON。
字段（没明确提到的一律用 null，不要推断、不要编造）：
treatment_type(cytotoxic_chemo/immunotherapy/targeted/radiation/other/null)、
days_since_last_chemo(int)、temp_c(float,摄氏)、temp_route(oral/axillary/ear/forehead/null)、
rigors、dyspnea、chest_pain、cyanosis、altered_consciousness、active_bleeding、hematemesis_melena、
diarrhea_bloody、has_cvc、cvc_site_inflamed（以上为 true/false/null）、
vomiting_unable_intake_hours(int)、diarrhea_count_per_day(int)、age(int)、
patient_group(solid_tumor/hematologic/transplant/pregnant/null)。
若提到儿童/血液肿瘤/移植/孕产/免疫治疗/靶向/放疗，务必在对应字段标出。
只输出 JSON 对象，不要任何解释或代码围栏。

用户描述：
%s"""


def _stepfun_complete(prompt, key, model=None, timeout=30):
    model = model or os.environ.get("STEPFUN_MODEL", "step-1-8k")
    body = {"model": model, "temperature": 0,
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(
        "https://api.stepfun.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d["choices"][0]["message"]["content"]


def _default_llm(prompt):
    key = os.environ.get("STEPFUN_API_KEY")
    if not key:
        return None
    return _stepfun_complete(prompt, key)


def _parse_json(text):
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)  # 容忍代码围栏/前后缀
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except ValueError:
        return None


def _keyword_backstop(text, case):
    """LLM 漏抽时的禁忌信号兜底；只往'升级就医'方向加，不放松。"""
    t = text or ""
    if case.get("age") is None and re.search(r"儿童|小孩|孩子|宝宝|岁的小", t):
        case["age"] = 10
    if not case.get("patient_group") and re.search(r"白血病|淋巴瘤|骨髓瘤|血液(病|肿瘤)|移植|怀孕|孕妇|妊娠", t):
        if re.search(r"怀孕|孕妇|妊娠", t):
            case["patient_group"] = "pregnant"
        elif re.search(r"移植", t):
            case["patient_group"] = "transplant"
        else:
            case["patient_group"] = "hematologic"
    if not case.get("treatment_type") and re.search(r"免疫治疗|PD-?1|PD-?L1|免疫检查点|O药|K药", t):
        case["treatment_type"] = "immunotherapy"
    elif not case.get("treatment_type") and re.search(r"靶向", t):
        case["treatment_type"] = "targeted"
    return case


def extract(text, llm=None):
    """自由文本 → 规范化 case（供 engine.evaluate）。失败/缺失走引擎升级，不崩溃。"""
    llm = llm or _default_llm
    raw = None
    try:
        out = llm(EXTRACT_PROMPT % text)
        raw = _parse_json(out)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError, ValueError):
        raw = None
    raw = {k: v for k, v in (raw or {}).items() if k in ALLOWED}
    case = normalize_case(raw)
    return _keyword_backstop(text, case)


if __name__ == "__main__":
    import sys as _s
    txt = _s.argv[1] if len(_s.argv) > 1 else "我爸化疗第7天下午开始发烧38.5度，还有点发抖"
    print(json.dumps(extract(txt), ensure_ascii=False, indent=2))
