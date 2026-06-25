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
