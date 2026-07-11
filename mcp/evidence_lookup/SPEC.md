# MCP 工具：evidence-lookup（规格草案）

> 职责：封装 **KnowS** 医学循证检索，为判定结果**附权威来源**。
> **只检索、不判定、不定阈值**——绝不用检索结果去改引擎的判级。

## tool name
evidence_lookup

## input
    {
      "topic": "中性粒细胞减少性发热 处理",   // 通常取自命中规则的 source 主题
      "lang": "zh|en",
      "max_results": 2
    }

## output
    {
      "sources": [
        { "title": "...", "publisher": "指南/患教来源", "url": "...", "snippet": "原文摘录" }
      ],
      "found": true
    }

## provider 接口（关键：不把 KnowS 当单点依赖）

evidence-lookup 设计成可插拔 provider，**默认不依赖比赛 API**：

    provider = local   # 默认：读 rules/sources.md 固化的本地 evidence pack
    provider = knows   # 拿到 KnowS Key 后启用：动态检索文献/指南/说明书/临床试验

- 没有 KnowS Key 也能跑：本地 evidence pack（从 IDSA/NCI/ACS/CSCO 等**公开来源**整理）即可支撑【参考来源】。
- KnowS Key 到手后热插拔为补充检索，不改变规则判级。
- "规则不依赖比赛 API 才成立"本身就是更强的工程/安全叙事（评委向）。

## 使用约束
- 仅作 Skill 输出里的【参考来源】，**不参与 engine 判级**。
- 只采信权威来源（指南/患教/说明书/临床试验）；过滤论坛、自媒体。
- 检索失败/无结果 → `found:false`，Skill 注明"未检索到权威来源，请以医护为准"，**不得**因此放松判级。
- 规则阈值仍为 draft 时，输出**不得**把 `source` 展示为"已循证"（引擎已加 `source_note` 标注）。
- 阈值固化（写进 `rules/sources.md`）是**离线人工**流程，不在本工具的运行时路径里做。

## 已接入 KnowS（2026-06-25，实测可用）

KnowS = 医学文献搜索引擎（类似医学版 Google/DuckDuckGo，**不提供模型能力**），让回答有据可依。

- 端点：`POST https://api.nullht.com/v1/evidences/ai_search_guide`（指南；另有 paper_cn/paper_en/trial/package_insert/meeting）
- 鉴权：`Authorization: Bearer $KNOWS_API_KEY`（从环境变量读，**绝不入仓**；见 `.env.example`）
- 请求：`{"query": "..."}`；响应：`{"question_id", "evidences":[{id,title,has_pdf,publish_date,organizations}]}`
- 实测：query「中性粒细胞减少性发热…」返回 CSCO(2021) 等中文权威指南，正好覆盖红旗主题。
- 实现：`knows_provider.py`（仅标准库 urllib）+ `lookup.py`（provider 调度，KnowS 失败自动回退 local）。
- 参考实现：小X宝社区 MCP-KnowS-AI（github.com/PancrePal-xiaoyibao/MCP-KnowS-AI）。

## 实现备注
- 默认 local（确定性、可离线、测试用）；`KNOWS_USE=1` 且有 Key 时走 KnowS，失败回退 local。
- 共享额度池、活动期 7/12 截止；topic→query 映射见 `knows_provider.TOPIC_QUERY`，可用 `eval/knows_golden_queries.md` 调优。

## v2 统一契约（adapter.py · 方案v2 §10）

判证(verdict) 与 答疑(qa) 共用入口：

    evidence_lookup(query, mode="verdict"|"qa", timeout=12, refresh=False) -> {
      "citations": [ {guideline, year, org, snippet, url, source[, doi]} ],
      "status": "ok" | "fallback_local" | "no_evidence",
      "used_online": bool,
    }
    # source: "local"(本地 validated 保底,带真实 url+snippet)
    #       | "knows"(KnowS 指南,权威但只有名/机构/年)
    #       | "knows_paper"(研究文献佐证,带 doi 链接 + 摘要节选;展示须标"研究文献(非指南)")
    # 展示优先级：local → knows → knows_paper

- **判证(verdict)**：入参 = 命中规则绑定的 `source_key`。默认从「本地 validated 保底 + vendored 缓存
  (`knows_cache.yaml`)」**即时离线**返回，恒含 ≥1 条真实引用；`refresh=True` 且 `KNOWS_USE=1` 时才在线
  刷新（成功 `status=ok`，超时/空 `status=fallback_local`）。**判级绝不依赖本调用成败。**
- **答疑(qa)**：仅当 KnowS 返回**含可引用 snippet+url** 的条目才作答；无 url / 仅日期类低置信 / 超时 /
  离线 → `status=no_evidence`，产品层固定回「没找到可靠依据，建议就医/问主诊」，**绝不自由生成兜底**。
- **判证 topic 预缓存**（解 KnowS 4–11s 延迟）：`prefetch_verdict_cache.py` 构建期对固定的判证 topic 集
  调 KnowS、按 `(title, org)` 去重，写入 vendored `knows_cache.yaml`（**入仓**；Key 只在 `.env`，不入仓）。
  运行时判证不走在线热路径；刷新缓存重跑 prefetch 即可。

### 相关性 / grounded 佐证 / 缓存治理（回应 challenge-plans 异议）

- **相关性**（`ai_search_guide` 无 ranking/filter/score 参数，已查文档+实测确认 → 只能构建期解）：
  `prefetch._on_topic` 要求标题同时命中「症状词 + 肿瘤/化疗语境词(`ONCO_CONTEXT`)」，剔除「高血压性脑出血」
  「RET-TKI 不良反应」等同词不同病偏题指南。**测试 `t_cache_entries_pass_filter_invariant` 断言缓存内
  每条都过滤通过、毒样本永不混入**（防刷新/手改漂移）。
- **grounded 原文佐证（④）**：guide 端点无 url/无原文 → 改用 `ai_search_paper_cn` 取 `abstract`+`doi`，
  每 topic 选 ≤2 条 on-topic 论文作可点开(doi.org)、可引证的原文佐证（标 `knows_paper`、展示注明「研究文献
  (非指南)」，权威性不与指南混同）。**安全：论文摘要过 `ABSTRACT_REASSURE_BLACKLIST`（在家观察/无需就医…）
  过滤，绝不让宽慰语进入展示证据**（测试 `t_no_reassurance_in_displayed_evidence`）。论文佐证让覆盖面宽、
  KnowS 指南检索为空的规则源（如 `acs_when_to_call`）也有可核验循证。
- **缓存治理（③）**：`knows_cache.yaml._meta` 记 `generated_at` / `refresh_owner` / `refresh_cadence`
  （改 `redflags.yaml` 的 source/`TOPIC_QUERY` 后，或距生成 >90 天，重跑 prefetch 并 review diff）。
- 契约门：`tests/test_evidence_contract.py`（mock KnowS ok/超时/空三态 + §11#8/#9/#10 + 上述相关性/安全/佐证
  真实数据断言，14/14 全绿，接入 CI）。

### 仍是限制（诚实记录，非本轮目标）
- KnowS 富端点 `evidence/highlight`、`evidence/get_guide`(全文)、`answer`(合成) 对本黑客松 key **403 tier-gated**
  （dev-api 是另一套 key）。若日后拿到高 tier，可让 guide 也有 grounded 原文 + 支撑开放答疑；现阶段不依赖。
- 开放生成式答疑仍 fast-follow（需我方 LLM 基于 paper 摘要合成 + 扛幻觉验收，会稀释「判级可靠/答疑诚实」主线）。
- `acs_when_to_call` 是杂烩规则源：7/12 后宜按症状簇拆分、各挂专属指南（todo2/fast-follow）。
