#!/usr/bin/env python3
"""判证 topic 预缓存（构建期工具，非交互热路径）。

为什么存在（见 方案v2 §10 spike 实测）：KnowS 判证检索延迟 4–11.2s，放进交互链路会卡；
而判证 topic 是**固定的有限集合**（= redflags.yaml 里各规则绑定的 source_key）。
所以构建期把每个判证 topic 的真实指南引用预抓下来、去重后 vendored 到 knows_cache.yaml，
运行时判证显示即时且离线可用；KnowS 仅用于「刷新/补充」，不在用户等待的热路径上。

用法（需 KNOWS_API_KEY，绝不入仓；缓存产物 knows_cache.yaml 才入仓）：
    set -a; source .env; set +a
    KNOWS_USE=1 python3 prefetch_verdict_cache.py            # 覆盖写 knows_cache.yaml
    KNOWS_USE=1 python3 prefetch_verdict_cache.py --dry-run  # 只打印不写

去重：KnowS 同一指南会重复返回（如 ABHH×3），按 (title, org) 去重。
安全：本工具只产出「指南名+机构+年份」级别的引用元数据，不抓取/不存储任何受版权全文或 PII。
"""
import os
import sys
import datetime

import yaml

from knows_provider import lookup as knows_lookup, lookup_paper, TOPIC_QUERY

CACHE_PATH = os.path.join(os.path.dirname(__file__), "knows_cache.yaml")
RAW_FETCH = 8       # 每 topic 多取一些再去重
KEEP = 4            # 去重后每 topic 保留上限（指南）
PAPER_RAW = 8       # 论文检索多取再筛
PAPER_KEEP = 2      # 每 topic 保留的 grounded 论文佐证上限
ABSTRACT_MAX = 240  # 摘要展示截断（仅作展示佐证，非全文）

# 安全黑名单：论文摘要可能含"在家观察/无需就医"类宽慰语，挂到 RED 判定下会危险。
# prefetch 时凡摘要命中以下任一词的论文一律丢弃——展示的循证佐证绝不能与"绝无放行"红线相悖。
ABSTRACT_REASSURE_BLACKLIST = [
    "在家观察", "居家观察", "观察即可", "无需就医", "不需就医", "不用就医",
    "不用去医院", "无需处理", "可在家", "无需特殊处理", "无须就医",
]

# 构建期相关性过滤（ai_search_guide 无相关性/排序/过滤参数——已查 KnowS API 文档+实测确认，
# 只能 query 精炼 + 在此按标题关键词白名单剔除偏题项，守住「循证脊梁」可信度）。
# 规则：标题须同时命中 (a) 本 topic ≥1 个症状/主题词 且 (b) ≥1 个肿瘤/化疗语境词，
#       否则丢弃（如「高血压性脑出血」「RET-TKI 不良反应」这类同词不同病的偏题指南）。
#       某 topic 过滤后为空时，由本地 validated 保底兜底——诚实优于硬塞偏题指南。
ONCO_CONTEXT = ["化疗", "放化疗", "肿瘤", "抗肿瘤", "癌", "中性粒", "粒细胞", "csco", "nccn"]
TOPIC_FILTERS = {
    "idsa_fn_2010":     ["中性粒细胞", "粒细胞减少", "发热", "neutropenia", "感染"],
    "nci_infection":    ["感染", "中心静脉", "导管", "picc", "输液港", "粒细胞", "发热"],
    "acs_when_to_call": ["急症", "不良反应", "副作用", "何时就医", "危险信号"],
    "acs_resp_emergency": ["呼吸困难", "气促", "呼吸衰竭", "胸痛", "呼吸", "肺", "急症"],
    "acs_bleeding": ["出血", "血小板", "止血", "消化道出血", "凝血", "血便", "咯血"],
    "nccn_gi_management": ["腹泻", "呕吐", "恶心", "消化道", "胃肠", "止吐"],
    "onco_nutrition": ["营养", "膳食", "饮食", "恶液质", "恶病质", "食欲", "蛋白", "忌口", "进食"],
}


def _norm(s):
    return (s or "").strip().lower()


def _on_topic(title, keywords):
    """标题须同时含「主题词」与「肿瘤/化疗语境词」，剔除同词不同病的偏题指南。"""
    t = _norm(title)
    hit_topic = any(_norm(k) in t for k in keywords)
    hit_onco = any(_norm(k) in t for k in ONCO_CONTEXT)
    return hit_topic and hit_onco


def _dedup(sources, keywords=None):
    """按 (title, org) 去重，保序；可选按标题关键词白名单过滤偏题项。"""
    seen, out = set(), []
    for s in sources:
        title = s.get("title")
        if not title:
            continue
        if keywords and not _on_topic(title, keywords):
            continue
        key = (_norm(title), _norm(s.get("publisher")))
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _to_citation(s):
    """KnowS 原始条目 → vendored 引用（与 §10 citation 字段对齐）。"""
    return {
        "guideline": s.get("title", ""),
        "org": s.get("publisher", ""),
        "year": s.get("year"),
        "publish_date": s.get("publish_date", ""),
        "has_pdf": bool(s.get("has_pdf")),
        "url": "",                       # KnowS guide 不返回可引用 URL（spike 实测）
        "source": "knows",               # 来源 KnowS，但已 vendored → 离线即时
        "knows_source_id": s.get("source_id", ""),
    }


def _abstract_safe(abstract):
    """论文摘要不得含"在家观察/无需就医"类宽慰语（与"绝无放行"红线相悖）。"""
    a = _norm(abstract)
    return not any(_norm(b) in a for b in ABSTRACT_REASSURE_BLACKLIST)


def _to_paper_citation(s):
    """论文条目 → grounded 原文佐证（带可点开 doi 链接 + 摘要节选）。标 source=knows_paper、明确"研究文献(非指南)"。"""
    abs = s.get("abstract", "")
    excerpt = abs if len(abs := abs.strip()) <= ABSTRACT_MAX else abs[:ABSTRACT_MAX].rstrip() + "…"
    return {
        "guideline": s.get("title", ""),
        "org": s.get("journal", "") or "研究文献",
        "year": s.get("year"),
        "publish_date": s.get("publish_date", ""),
        "snippet": excerpt,              # 论文摘要节选：可引证 grounded 原文
        "url": s.get("url", ""),         # https://doi.org/<doi> 可点开
        "doi": s.get("doi", ""),
        "source": "knows_paper",         # 论文≠指南：展示层须标"研究文献(非指南)"，不与指南权威混同
        "knows_source_id": s.get("source_id", ""),
    }


def _select_papers(query, keywords, timeout):
    """检索论文 → 过滤(标题肿瘤+主题双命中、摘要非空且通过安全黑名单) → 取前 N 条 grounded 佐证。"""
    res = lookup_paper(query, max_results=PAPER_RAW, timeout=timeout)
    if not res.get("found"):
        return [], res.get("error")
    out, seen = [], set()
    for s in res["sources"]:
        title, abstract = s.get("title", ""), s.get("abstract", "")
        if not title or len(abstract) < 40:
            continue
        if keywords and not _on_topic(title, keywords):
            continue
        if not _abstract_safe(abstract):
            continue
        k = _norm(title)
        if k in seen:
            continue
        seen.add(k)
        out.append(_to_paper_citation(s))
        if len(out) >= PAPER_KEEP:
            break
    return out, None


def build(topics=None, timeout=15):
    topics = topics or list(TOPIC_QUERY.keys())
    cache = {
        "_meta": {
            "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "note": "构建期预抓的 KnowS 判证引用（vendored，离线即时）。判级不依赖本缓存；"
                    "缓存仅供判证展示与离线保底。citations=指南(权威)，papers=研究文献含可点开 doi+摘要佐证(非指南)。"
                    "刷新：重跑 prefetch_verdict_cache.py。",
            "source": "KnowS ai_search_guide + ai_search_paper_cn",
            "refresh_owner": "claude-code（有爱无恙循证维护）",
            "refresh_cadence": "每次改 redflags.yaml 的 source/TOPIC_QUERY 后，或距 generated_at >90 天，重跑 prefetch 并 review diff",
        },
        "topics": {},
    }
    for key in topics:
        keywords = TOPIC_FILTERS.get(key)
        res = knows_lookup(key, max_results=RAW_FETCH, timeout=timeout)
        if not res.get("found"):
            print("  [warn] %-18s 指南未取到（%s）— 保留旧缓存/本地保底兜底" % (key, res.get("error")),
                  file=sys.stderr)
            continue
        raw = res["sources"]
        kept = _dedup(raw, keywords=keywords)
        cites = [_to_citation(s) for s in kept][:KEEP]
        papers, perr = _select_papers(res.get("query") or key, keywords, timeout)
        entry = {"query": res.get("query"), "citations": cites}
        if papers:
            entry["papers"] = papers
        cache["topics"][key] = entry
        print("  [ok]   %-18s 指南取%d→留%d（剔%d）｜论文佐证 %d%s"
              % (key, len(raw), len(cites), len(raw) - len(kept), len(papers),
                 "" if not perr else "（论文检索失败:%s）" % perr), file=sys.stderr)
    return cache


def _arg_value(argv, flag):
    """取 `--flag value` 的 value（不存在返回 None）。"""
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def _load_full(path=CACHE_PATH):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def main(argv):
    dry = "--dry-run" in argv
    if os.environ.get("KNOWS_USE") != "1" or not os.environ.get("KNOWS_API_KEY"):
        print("需要 KNOWS_USE=1 且 KNOWS_API_KEY（从 .env）。中止。", file=sys.stderr)
        return 2
    # --only k1,k2：只抓指定 topic 并**合并**进现有缓存（保留其余已审定 topic，不整体覆盖）。
    timeout = int(_arg_value(argv, "--timeout") or 15)  # 指南检索慢(4–11s+)，--only 时可调大
    only = _arg_value(argv, "--only")
    if only:
        keys = [k.strip() for k in only.split(",") if k.strip()]
        fresh = build(topics=keys, timeout=timeout)
        if not fresh["topics"]:
            print("--only 指定 topic 未取到，未写入。", file=sys.stderr)
            return 1
        cache = _load_full()
        cache["_meta"] = fresh["_meta"]
        cache.setdefault("topics", {})
        cache["topics"].update(fresh["topics"])  # 只更新/新增指定 topic，其余保持原样
        print("  [merge] 合并 topic：%s（保留其余 %d 个不变）"
              % (", ".join(keys), len(cache["topics"]) - len(fresh["topics"])), file=sys.stderr)
    else:
        cache = build()
    if not cache["topics"]:
        print("未取到任何 topic，未写入。", file=sys.stderr)
        return 1
    out = yaml.safe_dump(cache, allow_unicode=True, sort_keys=False)
    if dry:
        print(out)
        return 0
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        f.write("# 构建期预抓的 KnowS 判证引用缓存（vendored，入仓）。请用 prefetch_verdict_cache.py 重新生成，勿手改。\n")
        f.write(out)
    print("已写入 %s" % CACHE_PATH, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
