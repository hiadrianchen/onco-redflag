#!/usr/bin/env python3
"""Space app 冒烟（不启动 gradio，只测纯逻辑 assess + assess_html）。失败退出码非 0。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "space"))
from app import assess, assess_html, NONE_LABEL, myths_html, _load_myths  # noqa: E402


def main():
    fails = 0

    # 化疗第7天38.5 + 寒战 → RED（文本卡含"立即"+"参考来源"）
    card = assess("cytotoxic_chemo", 7, 38.5, None, None, ["发冷 / 打寒战"])
    ok = "立即" in card and "参考来源" in card
    print("PASS fever→RED+cite" if ok else "FAIL fever: %s" % card[:160]); fails += 0 if ok else 1

    # HTML 卡：RED 应含红色带 + 就医文案 + 三层循证依据（修问题⑧）
    html = assess_html("cytotoxic_chemo", 7, 38.5, None, None, ["发冷、打寒战（盖被子也止不住地抖）"])
    ok = "orf-card" in html and "去医院" in html and "循证依据" in html
    print("PASS html RED card+evidence" if ok else "FAIL html: %s" % html[:200]); fails += 0 if ok else 1

    # 安全：展示证据/卡片绝不含宽慰放行措辞（与"绝无你没事"红线一致）
    soothe = ["你没事", "不用去", "在家观察", "无需就医", "可以放心"]
    bad = [w for w in soothe if w in html]
    ok = not bad
    print("PASS no-soothe wording" if ok else "FAIL soothe leaked: %s" % bad); fails += 0 if ok else 1

    # NO_REDFLAG 卡：必须给"出现以下任一请立刻去医院"清单，不安抚
    html2 = assess_html("cytotoxic_chemo", 8, 36.8, None, None, [])
    ok = "请立刻去医院" in html2 and not any(w in html2 for w in soothe)
    print("PASS NO_REDFLAG actionable" if ok else "FAIL no_redflag: %s" % html2[:200]); fails += 0 if ok else 1

    # 免疫治疗（超范围）→ ESCALATE
    card = assess("immunotherapy", 5, 37.4, 8, None, [])
    ok = "超出" in card or "无法排除风险" in card
    print("PASS immuno→escalate" if ok else "FAIL immuno: %s" % card[:160]); fails += 0 if ok else 1

    # 修问题①⑥：UI 卡片不得残留"红旗"黑话或裸英文枚举/字段名
    jargon = ["红旗", "treatment_type", "immunotherapy", "cytotoxic_chemo", "days_since_last_chemo", "temp_c"]
    leaked = set()
    for tt in ("immunotherapy", "cytotoxic_chemo"):
        for hd in (assess_html(tt, None, None, None, None, []),
                   assess_html(tt, 8, 36.8, None, None, [])):
            leaked |= {w for w in jargon if w in hd}
    ok = not leaked
    print("PASS no jargon in UI" if ok else "FAIL jargon leaked: %s" % sorted(leaked)); fails += 0 if ok else 1

    # 全空 → 不崩溃
    card = assess(NONE_LABEL, None, None, None, None, [])
    ok = isinstance(card, str) and len(card) > 0
    print("PASS empty→graceful" if ok else "FAIL empty"); fails += 0 if ok else 1

    # todo3 辟谣卡：三条谣言都在，且每条都有「安全提醒」桥回就医、有真实循证依据
    myths = _load_myths()
    ok = {m["id"] for m in myths} >= {"fawu", "starve", "wbc_outdoor"} and all(m.get("safety") for m in myths)
    print("PASS myths loaded+safety" if ok else "FAIL myths: %s" % [m.get("id") for m in myths]); fails += 0 if ok else 1

    mh = myths_html()
    # 每条都渲染出循证依据区 + 至少一个可点开 doi 链接（grounded，非编造）
    ok = mh.count("orf-myth-ev-h") >= 3 and "doi.org" in mh and ("权威指南" in mh or "研究文献" in mh)
    print("PASS myths cited+grounded" if ok else "FAIL myth cites: ev=%d" % mh.count("orf-myth-ev-h")); fails += 0 if ok else 1

    # 安全红线：辟谣卡也绝不含宽慰放行措辞（与判证同一黑名单）
    leaked = [w for w in soothe if w in mh]
    ok = not leaked
    print("PASS myths no-soothe" if ok else "FAIL myth soothe: %s" % leaked); fails += 0 if ok else 1

    # 待办2 证据分级：判证卡 + 辟谣卡都标证据等级（Ⅰ级指南 / Ⅱ级研究），并给口径说明
    grade_html = assess_html("cytotoxic_chemo", 7, 38.5, None, None, ["发冷、打寒战（盖被子也止不住地抖）"])
    ok = "Ⅰ级证据" in grade_html and "证据等级按" in grade_html
    print("PASS verdict evidence-graded" if ok else "FAIL verdict grade: %s" % ("Ⅰ级证据" in grade_html, "证据等级按" in grade_html)); fails += 0 if ok else 1
    ok = ("Ⅰ级证据" in mh or "Ⅱ级证据" in mh) and "证据等级按" in mh
    print("PASS myths evidence-graded" if ok else "FAIL myth grade"); fails += 0 if ok else 1

    print("\n%s" % ("ALL PASS" if fails == 0 else "%d FAILED" % fails))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
