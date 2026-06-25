#!/usr/bin/env python3
"""Space app 冒烟（不启动 gradio，只测纯逻辑 assess + assess_html）。失败退出码非 0。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "space"))
from app import assess, assess_html, NONE_LABEL  # noqa: E402


def main():
    fails = 0

    # 化疗第7天38.5 + 寒战 → RED（文本卡含"立即"+"参考来源"）
    card = assess("cytotoxic_chemo", 7, 38.5, None, None, ["发冷 / 打寒战"])
    ok = "立即" in card and "参考来源" in card
    print("PASS fever→RED+cite" if ok else "FAIL fever: %s" % card[:160]); fails += 0 if ok else 1

    # HTML 卡：RED 应含红色带与就医文案
    html = assess_html("cytotoxic_chemo", 7, 38.5, None, None, ["发冷 / 打寒战"])
    ok = "orf-card" in html and "立刻就医" in html
    print("PASS html RED card" if ok else "FAIL html: %s" % html[:160]); fails += 0 if ok else 1

    # 免疫治疗（超范围）→ ESCALATE
    card = assess("immunotherapy", 5, 37.4, 8, None, [])
    ok = "超出" in card or "无法排除风险" in card
    print("PASS immuno→escalate" if ok else "FAIL immuno: %s" % card[:160]); fails += 0 if ok else 1

    # 全空 → 不崩溃
    card = assess(NONE_LABEL, None, None, None, None, [])
    ok = isinstance(card, str) and len(card) > 0
    print("PASS empty→graceful" if ok else "FAIL empty"); fails += 0 if ok else 1

    print("\n%s" % ("ALL PASS" if fails == 0 else "%d FAILED" % fails))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
