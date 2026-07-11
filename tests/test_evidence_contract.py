#!/usr/bin/env python3
"""循证 provider 契约门（hermetic，mock KnowS 的 ok/超时/空三态，不联网）。

验收 方案v2 §10 契约 + §11 安全用例 #8/#9/#10：
- 判证(verdict)：恒有本地保底；在线 ok→status=ok+source=knows；在线超时/空→fallback_local 但仍 ≥1 真实引用。
- 答疑(qa)：仅当 KnowS 返回含可引用 snippet+url 才作答；无 url / 仅日期类低置信 / 超时 / 离线 → no_evidence。
- 判级绝不依赖本调用：在线挂掉时判证仍返回保底引用（断网保底用例 §11#8）。
失败退出码非 0。
"""
import os
import sys

import yaml

_root = os.path.join(os.path.dirname(__file__), os.pardir)
sys.path.insert(0, os.path.join(_root, "mcp", "evidence_lookup"))
import adapter  # noqa: E402
import prefetch_verdict_cache as pf  # noqa: E402

_RULES = os.path.join(_root, "rules", "redflags.yaml")
_CACHE = os.path.join(_root, "mcp", "evidence_lookup", "knows_cache.yaml")

# 固定一个判证缓存 fixture（不依赖仓库里 knows_cache.yaml 的实时内容）
CACHE = {
    "idsa_fn_2010": {"query": "...", "citations": [
        {"guideline": "CSCO 中性粒细胞减少规范化管理指南(2021)", "org": "中国临床肿瘤学会",
         "year": 2021, "snippet": "发布日期：2021-01-01", "url": "", "source": "knows"},
    ]},
}


# ---- mock KnowS 三态（返回 knows_provider.lookup 的 sources 形状） ----
def knows_ok_guide(*a, **k):
    return {"found": True, "sources": [
        {"title": "在线刷新到的新指南(2025)", "publisher": "某权威机构", "url": "",
         "snippet": "发布日期：2025-01-01", "year": 2025, "source_id": "x"}]}


def knows_ok_with_url(*a, **k):  # qa 可作答场景：有 url + 真实原文 snippet
    return {"found": True, "sources": [
        {"title": "答疑可引用指南", "publisher": "机构", "url": "https://example.org/g",
         "snippet": "指南原文：建议……", "year": 2023, "source_id": "y"}]}


def knows_no_url(*a, **k):  # qa 不可作答：无 url + 仅日期类低置信 snippet
    return {"found": True, "sources": [
        {"title": "只有日期没原文", "publisher": "机构", "url": "",
         "snippet": "发布日期：2024-01-01", "year": 2024, "source_id": "z"}]}


def knows_timeout(*a, **k):  # knows_provider 捕获异常后的返回形状
    return {"found": False, "sources": [], "provider": "knows", "error": "timeout"}


def knows_empty(*a, **k):
    return {"found": False, "sources": [], "provider": "knows"}


def run(name, fn):
    try:
        fn()
        print("PASS " + name)
        return 0
    except AssertionError as e:
        print("FAIL " + name + " :: " + str(e))
        return 1


def with_knows(stub, online=True):
    """临时替换 adapter._knows.lookup 与在线开关。"""
    orig = adapter._knows.lookup
    env = dict(os.environ)
    adapter._knows.lookup = stub
    if online:
        os.environ["KNOWS_API_KEY"], os.environ["KNOWS_USE"] = "k", "1"
    else:
        os.environ.pop("KNOWS_API_KEY", None)
        os.environ["KNOWS_USE"] = "0"

    def restore():
        adapter._knows.lookup = orig
        os.environ.clear()
        os.environ.update(env)
    return restore


def ev(query, **kw):
    return adapter.evidence_lookup(query, cache=CACHE, **kw)


# ---------- 判证 verdict ----------
def t_verdict_offline_baseline():
    r = ev("idsa_fn_2010", mode="verdict", refresh=False)
    assert r["status"] == "fallback_local", r
    assert r["used_online"] is False, r
    assert len(r["citations"]) >= 1, "断网/离线判证必须 ≥1 条引用（§11#8 保底）"
    assert any(c["source"] == "local" for c in r["citations"]), "必须含本地 validated 保底引用"


def t_verdict_online_ok():
    restore = with_knows(knows_ok_guide)
    try:
        r = ev("idsa_fn_2010", mode="verdict", refresh=True)
        assert r["status"] == "ok", r
        assert r["used_online"] is True, r
        assert any(c["source"] == "knows" for c in r["citations"]), "在线成功应附 source=knows"
        assert any(c["source"] == "local" for c in r["citations"]), "保底仍在"
    finally:
        restore()


def t_verdict_online_timeout_falls_back():
    restore = with_knows(knows_timeout)
    try:
        r = ev("idsa_fn_2010", mode="verdict", refresh=True)
        assert r["status"] == "fallback_local", r
        assert r["used_online"] is True, r
        assert len(r["citations"]) >= 1, "在线超时判证仍须保底（判级不依赖检索成败）"
    finally:
        restore()


def t_verdict_online_empty_falls_back():
    restore = with_knows(knows_empty)
    try:
        r = ev("idsa_fn_2010", mode="verdict", refresh=True)
        assert r["status"] == "fallback_local", r
        assert len(r["citations"]) >= 1, r
    finally:
        restore()


def t_verdict_unmapped_no_evidence():
    # 既无本地保底也无缓存的未映射 key → 诚实 no_evidence，不编
    r = ev("zzz_unknown_key", mode="verdict", refresh=False)
    assert r["status"] == "no_evidence", r
    assert r["citations"] == [], r


# ---------- 答疑 qa ----------
def t_qa_offline_no_evidence():
    restore = with_knows(knows_ok_with_url, online=False)
    try:
        r = ev("化疗能不能吃发物", mode="qa")
        assert r["status"] == "no_evidence", "离线 qa 无在线检索→no_evidence（§10 不自由生成）"
        assert r["used_online"] is False, r
    finally:
        restore()


def t_qa_ok_with_url():
    restore = with_knows(knows_ok_with_url)
    try:
        r = ev("某可引用问题", mode="qa")
        assert r["status"] == "ok", r
        assert r["citations"] and r["citations"][0]["url"], "可作答必须带 url"
    finally:
        restore()


def t_qa_no_url_no_evidence():  # §11#9：KnowS 仅返回无 url/低置信 → 不得编造
    restore = with_knows(knows_no_url)
    try:
        r = ev("化疗能不能吃发物", mode="qa")
        assert r["status"] == "no_evidence", "无 url/仅日期低置信必须 no_evidence"
        assert r["citations"] == [], r
    finally:
        restore()


def t_qa_timeout_no_evidence():
    restore = with_knows(knows_timeout)
    try:
        r = ev("化疗能不能吃发物", mode="qa")
        assert r["status"] == "no_evidence", r
    finally:
        restore()


def t_bad_mode_raises():
    try:
        ev("x", mode="judge")
        raise AssertionError("非法 mode 应抛 ValueError")
    except ValueError:
        pass


def t_every_rule_source_has_local_baseline():
    """§9/§11#8 断网保底（真实数据，非 fixture）：redflags.yaml 里每个被规则引用的 source_key，
    在离线（无在线刷新）下经真实 evidence_pack/knows_cache 解析后，必须 ≥1 条本地 validated 保底引用。
    防 evidence_pack/rules 漂移导致某判定断网后没有真实指南可挂。"""
    os.environ.pop("KNOWS_API_KEY", None)
    os.environ["KNOWS_USE"] = "0"
    rules = yaml.safe_load(open(_RULES, encoding="utf-8"))["rules"]
    sources = sorted({r["source"] for r in rules if r.get("source")})
    assert sources, "redflags.yaml 应有带 source 的规则"
    for key in sources:
        r = adapter.evidence_lookup(key, mode="verdict", refresh=False)  # 真实 cache（cache=None）
        locals_ = [c for c in r["citations"] if c["source"] == "local"]
        assert len(locals_) >= 1, "判证 source_key %r 断网下缺本地 validated 保底引用" % key


def _load_real_cache():
    return (yaml.safe_load(open(_CACHE, encoding="utf-8")) or {}).get("topics", {})


def t_cache_entries_pass_filter_invariant():
    """①(过滤质量验收，challenge-plans high?)：缓存里每条指南/论文都须通过 prefetch 的相关性过滤
    （标题肿瘤+主题双命中）。防刷新/手改时偏题指南(如「高血压性脑出血」「RET-TKI」)混入。"""
    cache = _load_real_cache()
    assert cache, "knows_cache.yaml 应已 prefetch 生成"
    for key, entry in cache.items():
        kws = pf.TOPIC_FILTERS.get(key)
        if not kws:
            continue
        for c in entry.get("citations", []) + entry.get("papers", []):
            title = c.get("guideline", "")
            assert pf._on_topic(title, kws), "缓存偏题项混入 %r: %r" % (key, title)
        # 明示毒样本永不在缓存里（回归 challenge-plans 举的反例）
        for c in entry.get("citations", []) + entry.get("papers", []):
            t = c.get("guideline", "")
            for bad in ("高血压性脑出血", "ret-tki", "宫颈癌"):
                assert bad not in t.lower(), "偏题毒样本进入缓存 %r: %r" % (key, t)


def t_no_reassurance_in_displayed_evidence():
    """安全(§11#3 延伸到展示证据)：缓存里任何要展示的证据文本（指南 snippet / 论文摘要）
    都不得含"在家观察/无需就医"类宽慰语——展示证据绝不能与"绝无放行"红线相悖。"""
    cache = _load_real_cache()
    for key, entry in cache.items():
        for c in entry.get("citations", []) + entry.get("papers", []):
            assert pf._abstract_safe(c.get("snippet", "")), \
                "展示证据含宽慰语 %r: %r" % (key, c.get("snippet", "")[:40])


def t_papers_have_doi_links():
    """④(grounded 佐证)：缓存里的论文佐证须带可点开链接（doi.org）与非空摘要。"""
    cache = _load_real_cache()
    n = 0
    for entry in cache.values():
        for p in entry.get("papers", []):
            assert p.get("url", "").startswith("http"), "论文佐证缺可点开链接: %r" % p.get("guideline")
            assert len(p.get("snippet", "")) >= 20, "论文佐证摘要过短: %r" % p.get("guideline")
            n += 1
    assert n >= 1, "应至少有一条 grounded 论文佐证"


TESTS = [
    ("verdict 离线保底≥1引用(§11#8)", t_verdict_offline_baseline),
    ("verdict 在线ok→status=ok+knows", t_verdict_online_ok),
    ("verdict 在线超时→fallback_local仍保底", t_verdict_online_timeout_falls_back),
    ("verdict 在线空→fallback_local仍保底", t_verdict_online_empty_falls_back),
    ("verdict 未映射key→no_evidence不编", t_verdict_unmapped_no_evidence),
    ("qa 离线→no_evidence不自由生成", t_qa_offline_no_evidence),
    ("qa 有url+原文→可作答ok", t_qa_ok_with_url),
    ("qa 无url低置信→no_evidence(§11#9)", t_qa_no_url_no_evidence),
    ("qa 在线超时→no_evidence", t_qa_timeout_no_evidence),
    ("非法mode→ValueError", t_bad_mode_raises),
    ("真实数据:每个规则source断网有本地保底(§9/§11#8)", t_every_rule_source_has_local_baseline),
    ("①缓存全部通过相关性过滤(无偏题毒样本)", t_cache_entries_pass_filter_invariant),
    ("安全:展示证据无宽慰语(§11#3延伸)", t_no_reassurance_in_displayed_evidence),
    ("④论文佐证带doi链接+摘要", t_papers_have_doi_links),
]


def main():
    fails = sum(run(name, fn) for name, fn in TESTS)
    print("\n%d/%d passed" % (len(TESTS) - fails, len(TESTS)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
