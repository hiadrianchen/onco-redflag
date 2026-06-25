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

# source key（见 redflags.yaml）→ KnowS 检索式（中文为主，指南库）
TOPIC_QUERY = {
    "idsa_fn_2010": "中性粒细胞减少性发热 化疗后发热 急症 处理 指南",
    "nci_infection": "肿瘤化疗 感染 发热 寒战 中心静脉导管感染 就医 指南",
    "acs_when_to_call": "化疗 不良反应 出血 腹泻 呕吐 何时就医 指南",
    "nccn_gi_management": "化疗相关 腹泻 呕吐 管理 指南",
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


def lookup(source_key, max_results=2, query=None, key=None, endpoint="ai_search_guide"):
    key = key or os.environ.get("KNOWS_API_KEY")
    if not key:
        return {"sources": [], "found": False, "provider": "knows", "error": "no KNOWS_API_KEY"}
    q = query or TOPIC_QUERY.get(source_key) or source_key
    try:
        data = _post("/evidences/" + endpoint, {"query": q}, key)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        return {"sources": [], "found": False, "provider": "knows", "error": str(e)}
    items = []
    for ev in (data.get("evidences") or [])[:max_results]:
        orgs = ev.get("organizations") or []
        items.append({
            "title": ev.get("title", ""),
            "publisher": "；".join(orgs) if orgs else "KnowS 指南库",
            "url": "",  # KnowS guide 结果不直接返回 URL；以 title/机构/日期 引用
            "snippet": ("发布日期：%s" % ev.get("publish_date", "")) + ("（有全文 PDF）" if ev.get("has_pdf") else ""),
            "source_id": ev.get("id", ""),
        })
    return {"sources": items, "found": bool(items), "provider": "knows",
            "query": q, "question_id": data.get("question_id", "")}


if __name__ == "__main__":
    print(json.dumps(lookup("idsa_fn_2010"), ensure_ascii=False, indent=2))
