#!/usr/bin/env python3
"""统一循证 provider 契约（方案v2 §10）。判证(verdict) 与 答疑(qa) 共用一个入口。

    evidence_lookup(query, mode="verdict"|"qa", timeout=12, refresh=False) -> {
      "citations": [ {guideline, year, org, snippet, url, source} ],   # source: "knows"|"local"
      "status": "ok" | "fallback_local" | "no_evidence",
      "used_online": bool,
    }

安全红线（不可动摇）：
- **判级绝不依赖本调用的成败**。本模块只为「已判定的结果」附循证展示，从不参与判级（判级在 engine/triage.py）。
- 判证恒有保底：本地 validated pack（IDSA/NCI/ACS，带真实 url+snippet）保证离线每个判定 ≥1 条真实引用。
- 答疑诚实：qa 仅当 KnowS 返回**含可引用 snippet+url** 的条目才允许作答；否则 no_evidence，
  产品层固定回「没找到可靠依据，建议就医/问主诊」，**绝不自由生成兜底**。

热路径设计（见 §10 spike）：判证 topic 是固定集合，已由 prefetch_verdict_cache.py 构建期预抓为
knows_cache.yaml（vendored）。运行时 verdict 默认从「本地保底 + vendored 缓存」即时返回，离线可用；
KnowS 在线检索延迟 4–11s，**只在 refresh=True 时走**，不卡用户。
"""
import os
import re

import yaml

from local_provider import lookup as _local_lookup
import knows_provider as _knows

_CACHE_PATH = os.path.join(os.path.dirname(__file__), "knows_cache.yaml")
_YEAR_RE = re.compile(r"(19|20)\d{2}")


def _want_online(refresh):
    return bool(refresh) and bool(os.environ.get("KNOWS_API_KEY")) \
        and os.environ.get("KNOWS_USE", "0") == "1"


def _year_from_text(text):
    m = _YEAR_RE.search(str(text or ""))
    return int(m.group(0)) if m else None


def _norm(s):
    return (s or "").strip().lower()


def _load_cache(path=_CACHE_PATH):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("topics", {})
    except FileNotFoundError:
        return {}


def _cite(guideline, year, org, snippet, url, source, doi=""):
    c = {"guideline": guideline or "", "year": year, "org": org or "",
         "snippet": snippet or "", "url": url or "", "source": source}
    if doi:
        c["doi"] = doi
    return c


def _from_local(source_key, max_results):
    """本地 validated pack → citations（保底，带真实 url+snippet）。"""
    out = []
    for s in (_local_lookup(source_key, max_results=max_results).get("sources") or []):
        pub = s.get("publisher", "")
        out.append(_cite(s.get("title", ""), _year_from_text(pub) or _year_from_text(s.get("title")),
                         pub, s.get("snippet", ""), s.get("url", ""), "local"))
    return out


def _from_cache(source_key, cache):
    """vendored KnowS 缓存 → citations。citations=指南(source=knows)，papers=研究文献佐证(source=knows_paper，带 doi+摘要)。"""
    entry = (cache or {}).get(source_key) or {}
    out = []
    for c in entry.get("citations", []):
        out.append(_cite(c.get("guideline", ""), c.get("year"), c.get("org", ""),
                         c.get("snippet", ""), c.get("url", ""), "knows"))
    for p in entry.get("papers", []):
        out.append(_cite(p.get("guideline", ""), p.get("year"), p.get("org", ""),
                         p.get("snippet", ""), p.get("url", ""), "knows_paper", doi=p.get("doi", "")))
    return out


def _from_online(source_key, timeout, max_results):
    """KnowS 在线（仅 refresh 时；off 热路径）→ (citations, ok)。"""
    res = _knows.lookup(source_key, max_results=max_results, timeout=timeout)
    if not res.get("found"):
        return [], False
    out = []
    for s in res["sources"]:
        out.append(_cite(s.get("title", ""), s.get("year"), s.get("publisher", ""),
                         s.get("snippet", ""), s.get("url", ""), "knows"))
    return out, True


def _dedup(cites):
    """按 (guideline, org) 去重，保序；展示优先级：本地保底 → KnowS 指南 → 论文佐证。"""
    order = {"local": 0, "knows": 1, "knows_paper": 2}
    ordered = sorted(cites, key=lambda c: order.get(c["source"], 9))
    seen, out = set(), []
    for c in ordered:
        key = (_norm(c["guideline"]), _norm(c["org"]))
        if not c["guideline"] or key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def _verdict(query, timeout, refresh, max_results, cache):
    """判证：本地保底 + vendored 缓存（即时离线）+ 可选在线刷新。判级绝不依赖此处成败。"""
    source_key = query  # 判证入参 = rule 绑定的 guideline_key
    cites = _from_local(source_key, max_results) + _from_cache(source_key, cache)
    used_online, online_ok = False, False
    if _want_online(refresh):
        used_online = True
        fresh, online_ok = _from_online(source_key, timeout, max_results)
        cites += fresh
    cites = _dedup(cites)
    if not cites:
        # 该 source_key 既无本地保底也无缓存（未映射的规则）：诚实 no_evidence，不编。
        return {"citations": [], "status": "no_evidence", "used_online": used_online}
    status = "ok" if (used_online and online_ok) else "fallback_local"
    return {"citations": cites, "status": status, "used_online": used_online}


def _qa(query, timeout, max_results):
    """答疑：仅当 KnowS 返回含可引用 snippet+url 的条目才作答；否则 no_evidence（不自由生成）。"""
    if not _want_online(True):
        return {"citations": [], "status": "no_evidence", "used_online": False}
    res = _knows.lookup(None, max_results=max_results, query=query, timeout=timeout)
    if not res.get("found"):
        return {"citations": [], "status": "no_evidence", "used_online": True}
    cites = []
    for s in res["sources"]:
        snippet, url = (s.get("snippet") or "").strip(), (s.get("url") or "").strip()
        # §10「查不到」定义：无 url 或仅日期类低置信 snippet 一律不可作答。
        if url and snippet and not snippet.startswith("发布日期"):
            cites.append(_cite(s.get("title", ""), s.get("year"), s.get("publisher", ""),
                               snippet, url, "knows"))
    if not cites:
        return {"citations": [], "status": "no_evidence", "used_online": True}
    return {"citations": cites, "status": "ok", "used_online": True}


def evidence_lookup(query, mode="verdict", timeout=12, refresh=False, max_results=4, cache=None):
    cache = cache if cache is not None else _load_cache()
    if mode == "verdict":
        return _verdict(query, timeout, refresh, max_results, cache)
    if mode == "qa":
        return _qa(query, timeout, max_results)
    raise ValueError("mode 必须是 'verdict' 或 'qa'，收到 %r" % mode)


if __name__ == "__main__":
    import json
    print("verdict(local+cache):",
          json.dumps(evidence_lookup("idsa_fn_2010", mode="verdict"), ensure_ascii=False, indent=2))
    print("qa(no online):",
          json.dumps(evidence_lookup("化疗能不能吃发物", mode="qa"), ensure_ascii=False))
