#!/usr/bin/env python3
"""有爱无恙（OncoRedFlag）· 魔搭 Space 交互 demo（gradio，适老化 + 三层循证）。

面向化疗/肿瘤治疗期患者与家属的「居家就医决策」助手。设计要点：
- 判级 = 确定性引擎（engine/triage.py），LLM 不参与；**绝无"你没事/在家观察"放行分支**。
- 默认大字高对比、大点击区、四色清晰卡片；PC / 平板 / 手机自适应（无失效的"大字模式"开关）。
- 每个判定都把**三层循证**接进卡片：本地保底引用 + KnowS 权威指南 + 研究文献佐证（可点开 doi）。
- 全程仅用于**虚构病例**演示；不诊断、不替代急诊；危急请拨 120。

本地：pip install gradio pyyaml && python3 space/app.py
魔搭 Space：入口 app.py（见 space/README.md）。
"""
import os
import sys

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
# 仓库根 = 含 engine/ 的目录：本地在 space/app.py（根=上级），
# 魔搭 Space 把 app.py 提到仓库根时（根=自身），都能正确定位。
_ROOT = _HERE if os.path.isdir(os.path.join(_HERE, "engine")) else os.path.dirname(_HERE)
for p in (
    os.path.join(_ROOT, "engine"),
    os.path.join(_ROOT, "mcp", "redflag_intake"),
    os.path.join(_ROOT, "mcp", "evidence_lookup"),
    os.path.join(_ROOT, "skill", "onco-redflag-companion"),
):
    if p not in sys.path:
        sys.path.insert(0, p)

from pipeline import run as redflag_run  # noqa: E402
from adapter import evidence_lookup  # noqa: E402  (统一循证契约：三层 citations + status)

NONE_LABEL = "未提供"

# 症状标签内嵌大白话（修问题⑦：去黑话、解释输液港）。
SYMPTOMS = [
    ("发冷、打寒战（盖被子也止不住地抖）", "rigors"),
    ("喘不上气 / 胸口痛", "dyspnea"),
    ("意识模糊 / 怎么都叫不醒", "altered_consciousness"),
    ("出血不止 / 呕血 / 解黑便", "active_bleeding"),
    ("输液港或管子周围红肿（埋在胸口或手臂的输液管，也叫 PICC）", "cvc"),
]
SYMPTOM_KEYS = {label: key for label, key in SYMPTOMS}

# 卡片配色与标题（修问题⑥：全局去"红旗"黑话 → 大白话"要不要去医院"）。
LEVEL_STYLE = {
    "RED": ("#FCEBEB", "#501313", "#A32D2D", "现在就去医院 / 联系治疗团队"),
    "AMBER": ("#FAEEDA", "#412402", "#BA7517", "尽快复测，并联系治疗团队"),
    "ESCALATE": ("#FAECE7", "#4A1B0C", "#993C1D", "拿不准，建议联系治疗团队就医"),
    "NO_REDFLAG": ("#F1EFE8", "#2C2C2A", "#888780", "暂时没看到要马上去医院的危险信号（但不等于没事）"),
}

# NO_REDFLAG / AMBER 时显著列出"出现以下任一请立刻去医院"（修问题④：不安抚、给可执行的危险信号）。
ESCALATE_HINTS = [
    "口腔温度到 38.3℃，或 38.0℃ 持续超过 1 小时",
    "发冷打寒战、喘不上气、胸口痛",
    "意识模糊、怎么都叫不醒",
    "出血不止、呕血、解黑便",
    "输液港或管子周围红肿、发热、疼痛",
    "剧烈腹痛、拉肚子停不下来、吃不下也喝不下",
]

PLACEHOLDER = (
    '<div style="color:#7A7972;padding:20px;line-height:1.8">'
    "填好上面的情况后，点一下 <b>看看现在要不要去医院</b>——"
    "这里会用大白话告诉你怎么做，并显示判断所依据的权威指南。</div>"
)
# 输入被修改后的「请重新评估」提示（修问题5）。id 走 CSS 强制深色字，夜间模式下加粗也可见。
STALE = (
    '<div id="orf-stale">你刚改了上面的情况——'
    "请再点一次 <b>看看现在要不要去医院</b>，我按新情况重新判断。</div>"
)

# 默认大字高对比；并把自有内容（标题/提示/卡片）做成「自带浅色底 + 强制深色字」的面板，
# 这样无论平台切到深色还是浅色主题，文字都不会被主题改成浅色而在浅底上看不见（修问题1）。
CSS = """
.gradio-container{max-width:960px!important;margin:auto!important;font-size:20px!important}
.gradio-container button{min-height:56px!important;font-size:1.05em!important}
.gradio-container input,.gradio-container select,.gradio-container textarea{font-size:1em!important}
#orf-head{background:#FBF7EF;border-radius:12px;padding:14px 18px;margin-bottom:10px}
#orf-h1{margin:0;font-size:1.95em;color:#1F1F1D!important}
#orf-sub{color:#5C5B55!important;font-size:1.05em;margin-top:2px}
#orf-disc{background:#FAEEDA!important;font-size:0.95em;line-height:1.75;padding:14px 18px;border-radius:10px;margin-bottom:10px}
#orf-disc,#orf-disc b,#orf-disc strong{color:#412402!important}
.orf-card{border-radius:12px;overflow:hidden;margin-top:4px;background:#fff}
.orf-band{padding:16px 18px;font-weight:600}
.orf-body{padding:16px 18px;background:#fff!important;color:#2C2C2A!important;line-height:1.75}
.orf-body a{color:#185FA5!important}
.orf-ev-crit{background:#F4F8F4!important;border:1px solid #D7E5D7;border-radius:10px;padding:12px 14px;margin-bottom:12px}
.orf-ev-crit,.orf-ev-crit *{color:#243024!important}
.orf-ev-crit a{color:#1C6B3A!important}
#orf-stale{background:#FBF1EE!important;border:1px solid #E8C9BE;border-radius:10px;padding:16px 18px;line-height:1.8}
#orf-stale,#orf-stale b,#orf-stale strong{color:#7A2E2E!important}
/* 辟谣卡：与结果卡同样「自带浅色底 + 强制深色字」，深/浅主题下都清晰（沿用修问题1方案）。 */
.orf-myth{background:#FBF8F2!important;border:1px solid #E7E0D2;border-radius:12px;padding:16px 18px;margin-bottom:14px}
.orf-myth *{color:#2C2C2A!important}
.orf-myth a{color:#185FA5!important}
.orf-myth-claim{background:#F1ECE2!important;border-radius:9px;padding:10px 13px;line-height:1.65;margin-bottom:10px}
.orf-myth-claim,.orf-myth-claim *{color:#5A564C!important}
.orf-myth-verdict{font-weight:700;font-size:1.05em;margin-bottom:8px}
.orf-myth-verdict,.orf-myth-verdict *{color:#1F5A33!important}
.orf-myth-truth{line-height:1.78;margin-bottom:10px}
.orf-myth-safety{background:#FBF1EE!important;border:1px solid #E8C9BE;border-radius:9px;padding:10px 13px;line-height:1.7;margin-bottom:6px}
.orf-myth-safety,.orf-myth-safety *{color:#7A2E2E!important}
.orf-myth-ev{border-top:1px solid #E5E3DA;padding-top:12px;margin-top:12px}
.orf-myth-ev-h{font-weight:600;font-size:0.9em;margin-bottom:8px}
/* 折叠区内的引导语也要自带浅底+强制深色字，避免深色主题下贴在深色面板上看不清。 */
.orf-myth-intro{background:#FBF8F2!important;border:1px solid #E7E0D2;border-radius:10px;padding:12px 15px;line-height:1.7;margin-bottom:12px}
.orf-myth-intro,.orf-myth-intro *{color:#5C5B55!important}
/* 「病友群辟谣专区」：作为产品第二支柱，给独立视觉身份（暖橙边框+标题带），别让它像底部脚注。 */
.orf-myth-zone{margin-top:22px!important;border:2px solid #EAC196!important;border-radius:14px!important;overflow:hidden;background:#FFFDF9!important;box-shadow:0 1px 6px rgba(168,90,26,0.06)}
.orf-myth-zone>*{border-radius:0!important}
.orf-myth-section-head{background:#FBEAD4!important;padding:16px 20px}
.orf-myth-section-head *{color:#8A4F16!important}
.orf-myth-section-title{font-size:1.3em;font-weight:700;line-height:1.45}
.orf-myth-section-sub{font-size:0.9em;line-height:1.65;margin-top:6px;color:#9A6634!important}
/* 每条谣言独立成可展开项，问题标题常驻可见（钩子）；标题加大加粗+暖色，明显可点。 */
.orf-myth-acc{border:none!important;border-top:1px solid #F1E2CD!important;border-radius:0!important;background:transparent!important}
.orf-myth-acc>.label-wrap,.orf-myth-acc button.label-wrap{padding:14px 20px!important}
.orf-myth-acc .label-wrap span{font-size:1.1em!important;font-weight:600!important;color:#A85A1A!important}
@media (max-width:640px){.gradio-container{font-size:21px!important}}
"""

# 治疗类型中文 → 引擎枚举。
TREAT_MAP = {"化疗": "cytotoxic_chemo", "免疫治疗": "immunotherapy",
             "靶向治疗": "targeted", "放疗": "radiation", NONE_LABEL: NONE_LABEL}


def _clean(v):
    return None if v in (NONE_LABEL, "", None) else v


# 展示层术语净化（修问题①⑥）：引擎 reason/action 面向工程，含"红旗"黑话与裸英文枚举/字段名，
# 在 UI 卡片里统一替换为中文大白话。仅改展示，不动判级（引擎/CLI/MCP 输出不变）。
_HUMANIZE = [
    ("treatment_type=", ""), ("patient_group=", ""),
    ("treatment_type", "治疗类型"), ("days_since_last_chemo", "距上次化疗天数"), ("temp_c", "体温"),
    ("cytotoxic_chemo", "化疗"), ("immunotherapy", "免疫治疗"), ("targeted", "靶向治疗"),
    ("radiation", "放疗"), ("hematologic", "血液肿瘤"), ("transplant", "移植"),
    ("pregnant", "孕产"), ("other", "其他治疗"),
    ("红旗信号", "危险信号"), ("红旗", "危险信号"),  # 整词先行，避免"危险信号信号"叠词
]


def _humanize(text):
    text = text or ""
    for a, b in _HUMANIZE:
        text = text.replace(a, b)
    return text


def _trunc(s, n=160):
    s = s or ""
    return s if len(s) <= n else s[:n].rstrip() + "…"


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
    """返回纯文本判定卡（供测试/复用）。"""
    card, _ = redflag_run(_build_case(treatment_type, days, temp, diarrhea_count, age, symptoms))
    return card


_EV_TAG = {"local": "权威指南", "knows": "权威指南", "knows_paper": "研究文献"}
_EV_MAX_SUPPORT = 3  # 少而精：判断标准 + 最多 3 条支持依据（修问题4c）

# 证据等级（todo3 待办2）：按**来源类型的证据层级**标注（EBM 证据金字塔），
# 而非逐条 GRADE 评级——我们不读全文、不臆断每条的「推荐强度（强/弱）」，那样会变成编造。
# 诚实口径：Ⅰ级=指南/专家共识（多研究综合、权威机构制定）> Ⅱ级=单篇研究文献（原始证据，供佐证）。
_EV_GRADE = {
    "local": ("Ⅰ级证据 · 权威指南", "#E6EFF6", "#1C5A8A"),
    "knows": ("Ⅰ级证据 · 权威指南", "#E6EFF6", "#1C5A8A"),
    "knows_paper": ("Ⅱ级证据 · 研究文献", "#F3ECDD", "#7A5A1E"),
}
_EV_GRADE_LEGEND = (
    '<div style="color:#9A998F!important;font-size:0.74em;margin-top:8px;line-height:1.6">'
    '证据等级按<b>来源类型</b>排序：Ⅰ级=权威指南/专家共识（多研究综合、权威机构制定）'
    '＞Ⅱ级=单篇研究文献（原始证据，供佐证）；非逐条评定的推荐强度。</div>'
)


def _ev_meta(c):
    """来源可信度标注：杂志/机构 + 年份（年份缺失则省略，保持一致；修问题3b/4a）。"""
    return " · ".join(x for x in [c.get("org", ""), str(c["year"]) if c.get("year") else ""] if x)


def _support_cite_html(c):
    """单条「支持依据」HTML：证据等级徽标（Ⅰ级指南 / Ⅱ级研究，待办2）+ 出处机构年份 + 弱化标题链接。
    判证卡与辟谣卡共用，确保两处循证展示口径一致（标证据等级、文章标题弱化为小字链接）。"""
    tag, tbg, tcol = _EV_GRADE.get(c.get("source"), ("参考", "#ECEAE2", "#6B6A63"))
    url = (c.get("url") or "").strip()
    parts = ['<div style="margin-bottom:9px">']
    parts.append('<span style="display:inline-block;background:%s;color:%s;font-size:0.72em;'
                 'padding:1px 9px;border-radius:999px;margin-right:6px">%s</span>' % (tbg, tcol, tag))
    parts.append('<span style="color:#48473F;font-size:0.85em">%s</span>' % (_ev_meta(c) or "来源见原文"))
    title = _trunc(c.get("guideline", ""), 46)
    if url:
        parts.append('<a href="%s" target="_blank" rel="noopener" style="display:block;color:#185FA5;'
                     'font-size:0.8em;text-decoration:none;margin-top:1px">%s ↗</a>' % (url, title))
    else:
        parts.append('<div style="color:#8A897F;font-size:0.78em;margin-top:1px">%s</div>' % title)
    parts.append("</div>")
    return "".join(parts)


def _evidence_html(source_key):
    """循证依据 → HTML（修问题3/4）。重排版意图：
    - 把「判断标准」（带真实阈值原文的审定依据）作为主角，而非堆期刊名/文章标题；
    - 其余依据按「新→旧」排序、少而精（≤3 条），标可信度等级（权威指南/研究文献）+ 出处；
    - 文章标题弱化为可点开的小字链接，不占主视觉。
    安全：仅展示、不参与判级；摘要已在构建期过宽慰语黑名单。"""
    if not source_key:
        return ""
    res = evidence_lookup(source_key, mode="verdict") or {}
    cites = res.get("citations") or []
    if not cites:
        return ""

    # 判断标准 = 带真实原文阈值的本地审定条目（最有参考价值，置顶为「标准」而非陈旧引用）。
    criterion = next((c for c in cites
                      if c.get("source") == "local" and (c.get("snippet") or "").strip()), None)
    rest = [c for c in cites if c is not criterion]
    rest.sort(key=lambda c: (c.get("year") or 0), reverse=True)  # 新→旧
    shown, hidden = rest[:_EV_MAX_SUPPORT], max(0, len(rest) - _EV_MAX_SUPPORT)

    h = ['<div style="margin-top:16px;border-top:1px solid #E5E3DA;padding-top:14px">']
    h.append('<div style="color:#2C2C2A;font-weight:600;margin-bottom:10px">为什么这么判断 · 循证依据</div>')

    if criterion:
        gtag, gbg, gcol = _EV_GRADE.get(criterion.get("source"), _EV_GRADE["local"])
        h.append('<div class="orf-ev-crit">')
        h.append('<div style="font-weight:600;font-size:0.9em;margin-bottom:4px">判断标准'
                 '<span style="background:%s;color:%s;font-size:0.78em;font-weight:600;'
                 'padding:1px 8px;border-radius:999px;margin-left:8px">%s</span></div>' % (gbg, gcol, gtag))
        h.append('<div style="line-height:1.6">%s</div>' % _trunc(criterion.get("snippet", ""), 200))
        line = "出处：%s" % criterion.get("guideline", "")
        meta = _ev_meta(criterion)
        if meta:
            line += "（%s）" % meta
        url = (criterion.get("url") or "").strip()
        if url:
            h.append('<a href="%s" target="_blank" rel="noopener" '
                     'style="font-size:0.82em;text-decoration:none">%s ↗</a>' % (url, line))
        else:
            h.append('<div style="font-size:0.82em">%s</div>' % line)
        h.append("</div>")

    if shown:
        h.append('<div style="color:#6B6A63;font-size:0.86em;margin-bottom:6px">'
                 '另有以下权威指南 / 研究文献支持此判断（按时间新→旧）：</div>')
        for c in shown:
            h.append(_support_cite_html(c))  # 标题弱化为小字链接，不喧宾夺主（修问题3a）
        if hidden:
            h.append('<div style="color:#9A998F;font-size:0.78em;margin-top:2px">'
                     '（另有 %d 条同类依据，已按时间与相关度精选展示）</div>' % hidden)

    if criterion or shown:
        h.append(_EV_GRADE_LEGEND)  # 证据等级口径说明（待办2）
    # 诚实标注来源性质（替代会误导的「离线/联网刷新」角标，修问题2）：
    # 这些依据本身就是 KnowS 预检索 + 本地审定后离线收录的，不随用户当下联网与否改变。
    h.append('<div style="color:#9A998F;font-size:0.76em;margin-top:10px">'
             '依据为预先检索收录的权威指南 / 文献，离线即可查看；非实时联网结果。</div>')
    h.append("</div>")
    return "".join(h)


def assess_html(treatment_type, days, temp, diarrhea_count, age, symptoms):
    """返回适老化彩色卡 HTML（供 Space UI），含三层循证显示。"""
    _, d = redflag_run(_build_case(treatment_type, days, temp, diarrhea_count, age, symptoms))
    bg, fg, bar, title = LEVEL_STYLE.get(d["level"], LEVEL_STYLE["ESCALATE"])
    h = ['<div class="orf-card" style="border:2px solid %s">' % bar]
    h.append('<div class="orf-band" style="background:%s;color:%s;font-size:1.2em">%s</div>' % (bg, fg, title))
    h.append('<div class="orf-body">')
    h.append('<div style="color:#2C2C2A;font-weight:500;margin-bottom:6px">%s</div>' % _humanize(d.get("reason", "")))
    h.append('<div style="color:#3A3A38">%s</div>' % _humanize(d.get("action", "")))

    # 修问题④：没触发危险信号时，明确列出"出现以下任一请立刻去医院"，不让用户误读为"安全"。
    if d["level"] in ("NO_REDFLAG", "AMBER"):
        h.append('<div style="color:#7A2E2E;font-weight:600;margin:14px 0 4px">出现下面任何一种，请立刻去医院：</div>')
        h.append('<ul style="margin:0;padding-left:22px;line-height:1.85;color:#2C2C2A">')
        h += ['<li style="color:#2C2C2A">%s</li>' % x for x in ESCALATE_HINTS]
        h.append("</ul>")

    if d.get("temp_route_note"):
        h.append('<div style="color:#7A7972;font-size:0.9em;margin-top:10px">%s</div>' % d["temp_route_note"])
    if d.get("prepare_for_visit"):
        h.append('<div style="color:#5F5E5A;margin:14px 0 4px">去医院前，准备好这些：</div>'
                 '<ul style="margin:0;padding-left:22px;line-height:1.85;color:#2C2C2A">')
        h += ['<li style="color:#2C2C2A">%s</li>' % x for x in d["prepare_for_visit"]]
        h.append("</ul>")

    h.append(_evidence_html(d.get("source")))
    h.append('<div style="color:#888780;margin-top:14px;font-size:0.85em">'
             '本工具只核对有限的危险信号，不诊断、不替代医护判断；危急请拨 120。</div>')
    h.append("</div></div>")
    return "".join(h)


# ── 高频谣言循证辟谣卡（todo3 限定版）──────────────────────────────────────────
# 人工撰写的科普卡（rules/myths.yaml），每条挂真实指南/文献；不做开放生成式答疑、不参与判级。
_MYTHS_PATH = os.path.join(_ROOT, "rules", "myths.yaml")


def _load_myths():
    try:
        with open(_MYTHS_PATH, "r", encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("myths", [])
    except FileNotFoundError:
        return []


def _myth_evidence_html(source_key):
    """辟谣卡的循证依据：复用判证 citations（真实指南/文献），按时间新→旧少而精，标可信度等级。"""
    res = evidence_lookup(source_key, mode="verdict") or {}
    cites = res.get("citations") or []
    if not cites:
        return ""
    cites = sorted(cites, key=lambda c: (c.get("year") or 0), reverse=True)[:_EV_MAX_SUPPORT]
    h = ['<div class="orf-myth-ev">',
         '<div class="orf-myth-ev-h">这条说法的循证依据（权威指南 / 研究文献）</div>']
    h += [_support_cite_html(c) for c in cites]
    h.append(_EV_GRADE_LEGEND)  # 证据等级口径说明（待办2）
    h.append('<div style="color:#9A998F!important;font-size:0.76em;margin-top:8px">'
             '依据为预先检索收录的权威指南 / 文献，离线即可查看；非实时联网结果。</div>')
    h.append("</div>")
    return "".join(h)


# 「辟谣专区」标题带：给这个独占钩子一个产品级的视觉身份，避免被当成底部脚注忽略。
MYTH_SECTION_HEAD = (
    '<div class="orf-myth-section-head">'
    '<div class="orf-myth-section-title">💬 病友群里这些说法，到底信不信？</div>'
    '<div class="orf-myth-section-sub">化疗圈高频流传的说法，我们逐条对照权威指南 / 文献讲清真假——'
    '点开看依据。这些是科普，不替代就医判断；拿不准仍请用上面的工具或联系治疗团队。</div>'
    '</div>')


def _myth_body_html(m):
    """单条辟谣卡正文（问题已在折叠项标题里，正文给：原话 → 结论 → 循证讲清 → 安全提醒 → 依据）。"""
    h = ['<div class="orf-myth">']
    h.append('<div class="orf-myth-claim">病友群常听到：%s</div>' % m.get("claim", ""))
    if m.get("verdict"):
        h.append('<div class="orf-myth-verdict">循证看真假：%s</div>' % m["verdict"])
    h.append('<div class="orf-myth-truth">%s</div>' % m.get("truth", ""))
    if m.get("safety"):
        h.append('<div class="orf-myth-safety">⚠ %s</div>' % m["safety"])
    h.append(_myth_evidence_html(m.get("source_key")))
    h.append("</div>")
    return "".join(h)


def myths_html():
    """全部辟谣卡 HTML（标题带 + 各卡正文；供测试 / 静态预览复用，UI 走 build_ui 的逐条折叠）。"""
    myths = _load_myths()
    if not myths:
        return '<div style="color:#7A7972;padding:12px">暂无辟谣卡。</div>'
    return MYTH_SECTION_HEAD + "".join(
        '<div class="orf-myth-acc"><b>%s</b>%s</div>' % (m.get("title", ""), _myth_body_html(m))
        for m in myths)


def build_ui():
    import gradio as gr

    with gr.Blocks(title="有爱无恙 · 治疗期就医决策助手", css=CSS) as demo:
        # 修问题①：中文 H1「有爱无恙」+ 副标题，不出现裸英文。
        # 修问题1：放进自带浅色底的面板 + 强制深色字，深/浅主题下都清晰。
        gr.HTML('<div id="orf-head"><h1 id="orf-h1">有爱无恙</h1>'
                '<div id="orf-sub">治疗期 · 要不要马上去医院</div></div>')
        # 修问题③：开屏讲清覆盖范围；非化疗不 dead-end、文案不暗示其他疗法更危险。
        gr.HTML(
            '<div id="orf-disc"><b>这是什么：</b>帮治疗期的你判断——现在这些情况，要不要马上去医院。'
            '它循证覆盖最深的是<b>成人实体瘤、化疗后 0–21 天</b>；'
            '其他治疗（免疫 / 靶向 / 放疗）或拿不准的情况，会按<b>更稳妥</b>的方式提醒你联系治疗团队——'
            '这不代表那些治疗更危险，只是本工具对它们的循证覆盖还不够深。'
            '请勿填写真实姓名 / 病历；危急情况请直接拨打 120。</div>')

        with gr.Row():
            with gr.Column():
                treatment = gr.Dropdown(["化疗", NONE_LABEL, "免疫治疗", "靶向治疗", "放疗"],
                                        value="化疗", label="正在做哪种治疗")
                with gr.Row():
                    days = gr.Number(label="上次化疗到现在几天", value=7, precision=0)
                    temp = gr.Number(label="现在体温（℃，口腔最准）", value=38.5)
                with gr.Row():
                    diarrhea = gr.Number(label="一天拉肚子几次（没有就留空）", value=None, precision=0)
                    age = gr.Number(label="年龄（可不填）", value=None, precision=0)
                # 修问题⑦：勾选区提示"不确定就先不选，我们按更安全的方式提醒"。
                symptoms = gr.CheckboxGroup(
                    [label for label, _ in SYMPTOMS], value=[],
                    label="现在有没有下面这些情况？",
                    info="不确定的就先不要勾——拿不准时，我们会按更稳妥的方式提醒你。")
                # 修问题⑤：单按钮，不再"每次输入即刷新"。
                btn = gr.Button("看看现在要不要去医院", variant="primary")
            with gr.Column():
                out = gr.HTML(value=PLACEHOLDER)

        def _go(t, d, tc, dc, a, s):
            return assess_html(TREAT_MAP.get(t, NONE_LABEL), d, tc, dc, a, s)

        inputs = [treatment, days, temp, diarrhea, age, symptoms]
        btn.click(_go, inputs, out)
        # 修问题5：改了任一项就把结果清回提示，避免「换了疗法右侧却没变」的误解；
        # 真正的判定仍只在点按钮时发生（不恢复每输入即刷新）。
        for comp in inputs:
            comp.change(lambda: STALE, None, out)

        # todo3 「高频谣言循证辟谣卡」：作为产品第二支柱，给独立「辟谣专区」视觉身份；
        # 每条谣言独立成可展开项、问题标题常驻可见（钩子），首条默认展开以示可点开；纯科普、不参与判级。
        myths = _load_myths()
        if myths:
            with gr.Group(elem_classes="orf-myth-zone"):
                gr.HTML(MYTH_SECTION_HEAD)
                for i, m in enumerate(myths):
                    with gr.Accordion(m.get("title") or "辟谣", open=(i == 0),
                                      elem_classes="orf-myth-acc"):
                        gr.HTML(_myth_body_html(m))
    return demo


if __name__ == "__main__":
    build_ui().launch()
