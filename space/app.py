#!/usr/bin/env python3
"""OncoRedFlag · 魔搭 Space 交互 demo（gradio，适老化 + 响应式）。

设计要点：大字号、高对比、大点击区、四色清晰卡片；PC / 平板 / 手机自适应；含「大字模式」开关。
仅用于**虚构病例**演示；不诊断、不替代急诊；危急请拨 120。核心判定走确定性引擎（与 CLI/MCP 同源）。

本地：pip install gradio pyyaml && python3 space/app.py
魔搭 Space：入口 app.py（见 space/README.md）。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for p in (
    os.path.join(_ROOT, "engine"),
    os.path.join(_ROOT, "mcp", "redflag_intake"),
    os.path.join(_ROOT, "mcp", "evidence_lookup"),
    os.path.join(_ROOT, "skill", "onco-redflag-companion"),
):
    if p not in sys.path:
        sys.path.insert(0, p)

from pipeline import run as redflag_run  # noqa: E402
from lookup import lookup as evidence_lookup  # noqa: E402

NONE_LABEL = "未提供"

SYMPTOMS = [
    ("发冷 / 打寒战", "rigors"),
    ("喘不上气 / 胸痛", "dyspnea"),
    ("意识不清 / 叫不醒", "altered_consciousness"),
    ("出血 / 呕血 / 黑便", "active_bleeding"),
    ("输液港 / 管子处红肿", "cvc"),
]
SYMPTOM_KEYS = {label: key for label, key in SYMPTOMS}

LEVEL_STYLE = {
    "RED": ("#FCEBEB", "#501313", "#A32D2D", "立刻就医 / 联系治疗团队"),
    "AMBER": ("#FAEEDA", "#412402", "#BA7517", "复测 + 联系治疗团队"),
    "ESCALATE": ("#FAECE7", "#4A1B0C", "#993C1D", "无法排除风险，请就医"),
    "NO_REDFLAG": ("#F1EFE8", "#2C2C2A", "#888780", "暂未触发红旗（不等于安全）"),
}

CSS = """
.gradio-container{max-width:920px!important;margin:auto!important;font-size:18px!important}
body.orf-big .gradio-container{font-size:22px!important}
.gradio-container button{min-height:50px!important}
.gradio-container input,.gradio-container select,.gradio-container textarea{font-size:1em!important}
#orf-disc{background:#FAEEDA;color:#412402;font-size:1em;line-height:1.6;padding:12px 16px;border-radius:10px;margin-bottom:8px}
.orf-card{border-radius:12px;overflow:hidden;margin-top:4px}
.orf-band{padding:14px 18px;font-weight:500}
.orf-body{padding:14px 18px;background:#fff;color:#2C2C2A;line-height:1.7}
@media (max-width:640px){.gradio-container{font-size:19px!important}}
"""


def _clean(v):
    return None if v in (NONE_LABEL, "", None) else v


def _build_case(treatment_type, days, temp, diarrhea_count, age, symptoms):
    form = {
        "treatment_type": _clean(treatment_type),
        "days_since_last_chemo": days if days not in ("", None) else None,
        "temp_c": temp if (temp not in ("", None) and temp > 0) else None,
        "diarrhea_count_per_day": diarrhea_count if diarrhea_count not in ("", None, 0) else None,
        "age": age if age not in ("", None, 0) else None,
    }
    for label in (symptoms or []):
        key = SYMPTOM_KEYS.get(label)
        if key == "cvc":
            form["has_cvc"] = True
            form["cvc_site_inflamed"] = True
        elif key:
            form[key] = True
    return form


def assess(treatment_type, days, temp, diarrhea_count, age, symptoms):
    """返回纯文本红旗卡（供测试/复用）。"""
    card, _ = redflag_run(_build_case(treatment_type, days, temp, diarrhea_count, age, symptoms))
    return card


def assess_html(treatment_type, days, temp, diarrhea_count, age, symptoms):
    """返回适老化彩色卡 HTML（供 Space UI）。"""
    _, d = redflag_run(_build_case(treatment_type, days, temp, diarrhea_count, age, symptoms))
    bg, fg, bar, title = LEVEL_STYLE.get(d["level"], LEVEL_STYLE["ESCALATE"])
    h = ['<div class="orf-card" style="border:2px solid %s">' % bar]
    h.append('<div class="orf-band" style="background:%s;color:%s;font-size:1.15em">%s</div>' % (bg, fg, title))
    h.append('<div class="orf-body">')
    h.append('<div style="color:#2C2C2A;font-weight:500;margin-bottom:6px">%s</div>' % d.get("reason", ""))
    h.append('<div style="color:#3A3A38">%s</div>' % d.get("action", ""))
    if d.get("prepare_for_visit"):
        h.append('<div style="color:#5F5E5A;margin:12px 0 4px">去医院前，准备好这些：</div><ul style="margin:0;padding-left:22px;line-height:1.8;color:#2C2C2A">')
        h += ['<li style="color:#2C2C2A">%s</li>' % x for x in d["prepare_for_visit"]]
        h.append("</ul>")
    if d.get("source"):
        srcs = (evidence_lookup(d["source"]) or {}).get("sources") or []
        if srcs:
            h.append('<div style="color:#5F5E5A;margin:12px 0 4px">依据（真实部署会实时检索权威指南）</div>')
            for s in srcs:
                h.append('<div style="color:#185FA5;line-height:1.5">· %s</div>' % s.get("title", ""))
    h.append('<div style="color:#888780;margin-top:12px;font-size:0.9em">本工具仅核对有限危险信号，不诊断、不替代医护判断；危急请拨 120。</div>')
    h.append("</div></div>")
    return "".join(h)


def build_ui():
    import gradio as gr

    with gr.Blocks(title="OncoRedFlag · 治疗期红旗信号核对", css=CSS) as demo:
        gr.Markdown("## OncoRedFlag · 化疗期「要不要立刻就医」核对")
        gr.HTML('<div id="orf-disc"><b>提示：</b>本工具帮你判断要不要立刻就医，不替代医生。请勿填写真实姓名/病历；危急请拨 120。</div>')
        big = gr.Checkbox(label="大字模式（适老化）", value=False)
        with gr.Row():
            with gr.Column():
                treatment = gr.Dropdown(["化疗", NONE_LABEL, "免疫治疗", "靶向治疗", "放疗"],
                                        value="化疗", label="正在做哪种治疗")
                with gr.Row():
                    days = gr.Number(label="上次化疗到现在几天", value=7, precision=0)
                    temp = gr.Number(label="现在体温（℃）", value=38.5)
                with gr.Row():
                    diarrhea = gr.Number(label="一天拉肚子几次", value=None, precision=0)
                    age = gr.Number(label="年龄", value=None, precision=0)
                symptoms = gr.CheckboxGroup([label for label, _ in SYMPTOMS], value=["发冷 / 打寒战"],
                                            label="有没有下面这些情况？")
                btn = gr.Button("核对红旗信号", variant="primary")
            with gr.Column():
                out = gr.HTML()

        TREAT_MAP = {"化疗": "cytotoxic_chemo", "免疫治疗": "immunotherapy",
                     "靶向治疗": "targeted", "放疗": "radiation", NONE_LABEL: NONE_LABEL}

        def _go(t, d, tc, dc, a, s):
            return assess_html(TREAT_MAP.get(t, NONE_LABEL), d, tc, dc, a, s)

        inputs = [treatment, days, temp, diarrhea, age, symptoms]
        btn.click(_go, inputs, out)
        for comp in inputs:
            comp.change(_go, inputs, out)
        big.change(None, [big], None, js="(b)=>document.body.classList.toggle('orf-big', b)")
        demo.load(_go, inputs, out)
    return demo


if __name__ == "__main__":
    build_ui().launch()
