#!/usr/bin/env python3
"""evidence-lookup 的 KnowS provider —— 调 KnowS 医学循证检索（文献/指南/说明书/临床试验）。

KnowS 是医学文献搜索引擎（类似 Google/DuckDuckGo for medical evidence），不提供模型能力。
- 端点：POST https://api.nullht.com/v1/evidences/ai_search_guide  body {"query": "..."}
- 鉴权：Authorization: Bearer $KNOWS_API_KEY（从环境变量读，绝不写入仓库）
- 文档：https://developers.nullht.com/api/reference/overview

只用标准库（urllib），无第三方依赖。失败时返回 found=False，由 dispatcher 回退本地 pack。
"""
import os
import json
import urllib.request
import urllib.error

BASE = "https://api.nullht.com/v1"

# source key（见 redflags.yaml）→ KnowS 检索式（中文为主，指南库）。
# 注：ai_search_guide 仅接受 query、无相关性/排序/过滤参数（已查 KnowS API 文档实证），
# 故相关性只能靠「检索式精炼 + 构建期标题关键词过滤」(见 prefetch_verdict_cache.TOPIC_FILTERS)。
TOPIC_QUERY = {
    "idsa_fn_2010": "化疗后 中性粒细胞减少性发热 何时就医 处理 指南 共识",
    "nci_infection": "化疗 中性粒细胞减少 感染 发热 中心静脉导管 PICC 输液港 处理 指南",
    # acs_when_to_call 保留为「通用何时就医」框架（EMG-001 意识改变等通用急症）；
    # 按症状簇拆出下列专属来源（与 redflags.yaml source 对齐）：
    "acs_when_to_call": "化疗 不良反应 何时就医 急症 处理 指南 共识",
    "acs_resp_emergency": "肿瘤 化疗 呼吸困难 气促 胸痛 急症 处理 指南 共识",
    "acs_bleeding": "肿瘤 化疗 出血 血小板减少 消化道出血 止血 处理 指南 共识",
    "nccn_gi_management": "化疗相关 腹泻 呕吐 恶心 管理 指南 共识",
    # 谣言辟谣卡（todo3）循证来源：肿瘤患者营养（"发物忌口"/"饿死癌细胞"两条谣言共用）。
    "onco_nutrition": "肿瘤 化疗 患者 营养不良 恶液质 营养治疗 食欲 膳食 蛋白质 专家共识 指南",
}


def _post(path, payload, key, timeout=20):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _year_of(publish_date):
    """从 '2021-01-01' 取年份 int；解析不出返回 None。"""
    s = str(publish_date or "").strip()
    if len(s) >= 4 and s[:4].isdigit():
        return int(s[:4])
    return None


def lookup(source_key, max_results=2, query=None, key=None, endpoint="ai_search_guide", timeout=20):
    key = key or os.environ.get("KNOWS_API_KEY")
    if not key:
        return {"sources": [], "found": False, "provider": "knows", "error": "no KNOWS_API_KEY"}
    q = query or TOPIC_QUERY.get(source_key) or source_key
    try:
        data = _post("/evidences/" + endpoint, {"query": q}, key, timeout=timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        return {"sources": [], "found": False, "provider": "knows", "error": str(e)}
    items = []
    for ev in (data.get("evidences") or [])[:max_results]:
        orgs = ev.get("organizations") or []
        pub = ev.get("publish_date", "")
        items.append({
            "title": ev.get("title", ""),
            "publisher": "；".join(orgs) if orgs else "KnowS 指南库",
            "url": "",  # KnowS guide 结果不直接返回 URL；以 title/机构/日期 引用
            "snippet": ("发布日期：%s" % pub) + ("（有全文 PDF）" if ev.get("has_pdf") else ""),
            "year": _year_of(pub),
            "publish_date": pub,
            "has_pdf": bool(ev.get("has_pdf")),
            "source_id": ev.get("id", ""),
        })
    return {"sources": items, "found": bool(items), "provider": "knows",
            "query": q, "question_id": data.get("question_id", "")}


def lookup_paper(query, max_results=5, key=None, cn=True, timeout=20):
    """检索论文证据（ai_search_paper_cn/en）。与 guide 不同，论文条目带 `abstract`(可引证原文)
    + `doi`(可拼 https://doi.org/<doi> 链接) → 这是公开 API 下唯一能拿到 grounded 可引用原文的途径。
    返回 sources 每条含 title/abstract/doi/url/journal/authors/year。失败 found=False。"""
    key = key or os.environ.get("KNOWS_API_KEY")
    if not key:
        return {"sources": [], "found": False, "provider": "knows_paper", "error": "no KNOWS_API_KEY"}
    endpoint = "ai_search_paper_cn" if cn else "ai_search_paper_en"
    try:
        data = _post("/evidences/" + endpoint, {"query": query}, key, timeout=timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        return {"sources": [], "found": False, "provider": "knows_paper", "error": str(e)}
    items = []
    for ev in (data.get("evidences") or [])[:max_results]:
        doi = (ev.get("doi") or "").strip()
        pub = ev.get("publish_date", "")
        items.append({
            "title": ev.get("title", "").strip(),
            "abstract": (ev.get("abstract") or "").strip(),
            "journal": ev.get("journal", ""),
            "authors": ev.get("authors") or [],
            "doi": doi,
            "url": ("https://doi.org/" + doi) if doi else "",
            "year": _year_of(pub),
            "publish_date": pub,
            "source_id": ev.get("id", ""),
        })
    return {"sources": items, "found": bool(items), "provider": "knows_paper",
            "query": query, "question_id": data.get("question_id", "")}


if __name__ == "__main__":
    print(json.dumps(lookup("idsa_fn_2010"), ensure_ascii=False, indent=2))
