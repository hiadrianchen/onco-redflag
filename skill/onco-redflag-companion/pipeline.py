#!/usr/bin/env python3
"""onco-redflag-companion 端到端编排（可运行 demo）。

数据流：form_intake → engine.triage（确定性判定）→ evidence_lookup（local）→ 渲染红旗卡。
全程不依赖 LLM / KnowS / 网络，用于无凭据的端到端演示与冒烟。真实部署时：
- intake 换成自由文本 LLM 版（StepFun）；
- evidence_lookup 切 knows provider（Key 到手后）；
- 本编排逻辑与输出模板不变。
"""
import os
import sys

_HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_HERE, os.pardir, os.pardir, "engine"))
sys.path.insert(0, os.path.join(_HERE, os.pardir, os.pardir, "mcp", "redflag_intake"))
sys.path.insert(0, os.path.join(_HERE, os.pardir, os.pardir, "mcp", "evidence_lookup"))

from triage import evaluate            # noqa: E402
from form_intake import from_form      # noqa: E402
from lookup import lookup as evidence_lookup  # noqa: E402  (provider 调度：默认 local，KNOWS_USE=1 走 KnowS)

LEVEL_LABEL = {
    "RED": "🔴 立即联系治疗团队 / 急诊（必要时拨 120）",
    "AMBER": "🟡 规范复测并联系治疗团队咨询",
    "ESCALATE": "⚠️ 无法排除风险，请联系治疗团队 / 急诊",
    "NO_REDFLAG": "未触发本工具覆盖的红旗（这不代表安全）",
}


def render_card(decision, ev):
    out = []
    out.append("【判定】" + LEVEL_LABEL.get(decision["level"], decision["level"]))
    if decision.get("reason"):
        out.append("【原因】" + decision["reason"])
    out.append("【现在怎么做】" + decision.get("action", ""))
    if decision.get("temp_route_note"):
        out.append("【测温提示】" + decision["temp_route_note"])
    if decision.get("prepare_for_visit"):
        out.append("【就医前请准备】")
        out += ["  · " + x for x in decision["prepare_for_visit"]]
    srcs = (ev or {}).get("sources") or []
    if srcs:
        out.append("【参考来源】")
        for s in srcs:
            out.append("  · %s（%s）%s" % (s["title"], s.get("publisher", ""), s.get("url", "")))
        if decision.get("source_note"):
            out.append("  ※ " + decision["source_note"])
    else:
        out.append("【参考来源】未检索到权威来源，请以医护为准")
    out.append("【重要提醒】" + decision.get("disclaimer", ""))
    return "\n".join(out)


def _assess(case):
    decision = evaluate(case)
    ev = evidence_lookup(decision["source"]) if decision.get("source") else {"sources": [], "found": False}
    return render_card(decision, ev), decision


def run(form):
    """表单 → 判定 + 渲染卡。返回 (card_text, decision)。"""
    return _assess(from_form(form))


def run_text(text):
    """自由文本 → 判定 + 渲染卡（用 LLM intake，需 STEPFUN_API_KEY；抽取失败→引擎安全升级）。"""
    from llm_intake import extract  # 延迟导入，表单/MCP/Space 路径不依赖它
    return _assess(extract(text))


DEMOS = [
    ("化疗第7天发烧38.5、有点发抖",
     {"treatment_type": "cytotoxic_chemo", "days_since_last_chemo": 7, "temp_c": 38.5, "temp_route": "oral", "rigors": True}),
    ("化疗第7天发烧、但漏说末次化疗日期（信息不足）",
     {"treatment_type": "cytotoxic_chemo", "temp_c": 38.5}),
    ("免疫治疗后腹泻8次（超出覆盖范围）",
     {"treatment_type": "immunotherapy", "days_since_last_chemo": 5, "diarrhea_count_per_day": 8}),
    ("化疗第8天、体温正常、无症状（合法 NO_REDFLAG）",
     {"treatment_type": "cytotoxic_chemo", "days_since_last_chemo": 8, "temp_c": 36.8}),
]


if __name__ == "__main__":
    for title, form in DEMOS:
        print("=" * 60)
        print("# " + title)
        card, _ = run(form)
        print(card)
        print()
