# OncoRedFlag · 治疗期红旗信号核对与就医沟通助手

> Team **Nightlight** ｜ 2026 小X宝开源医疗社区黑客松（通用医学方向）
> 一句话：帮**化疗期肿瘤患者/家属**只回答一件事——**现在要不要立刻联系治疗团队/挂急诊**，以及去之前要把哪些信息讲清楚给医生。

> ⚠️ 这是黑客松脚手架，当前托管在个人活跃仓 `Personal-OS` 内（`projects/小X宝医疗黑客松/onco-redflag/`），
> 提交前会抽取为**独立公开 GitHub 仓库**并部署为**魔搭 Space**。

## 使用说明

面向用户/开发者的完整用法见 **[使用说明.md](使用说明.md)**：网页版（魔搭 Space）怎么用、MCP 怎么接、循证怎么来、四色结果含义、安全须知。

## 这不是什么（边界即卖点）

- ❌ 不诊断、不判断病因、不解读预后
- ❌ 不给"可以居家观察 / 无需处理"这类**安抚结论**（引擎里没有 GREEN 级）
- ❌ 不替代急诊、不是急救通道（危急直接拨 120）
- ❌ 不覆盖：儿童、免疫治疗、靶向、血液肿瘤、移植、孕产 → 命中即升级"请联系治疗团队/急诊"

详见 [SAFETY.md](SAFETY.md)。

## 架构（把"判断权"从 LLM 手里拿走）

    用户自由描述
       │  MCP: redflag-intake   （LLM 只抽取结构化字段，不判定）
       ▼
    结构化 case + 缺失字段清单
       │  engine/triage.py      （纯函数确定性规则引擎，无 LLM / 无网络）
       ▼
    判级 RED / AMBER / ESCALATE / NO_REDFLAG
       │  MCP: evidence-lookup  （KnowS，仅挂循证来源，不定阈值）
       ▼
    Skill: onco-redflag-companion（套输出模板 + caveat + 越界拒答）

- **红旗判定的唯一依据**是 `rules/redflags.yaml`（确定性、可审计、可单测），**不是模型**。
- LLM 只做两件事：把自由文本抽成字段（intake）、把结果讲成人话（skill）。
- 安全语义全部写在 `engine/triage.py` 的评估顺序里（先通用急症 → 范围守门 → 专项红旗 → 信息不足升级 → 低危 AMBER → 未触发但不安抚）。

## 目录结构

    onco-redflag/
      README.md
      LICENSE                      # Apache-2.0（完整正文）
      NOTICE                       # 版权 + 安全声明
      SAFETY.md                    # 边界 / 判级语义 / 数据红线 / 阈值治理
      .env.example                 # KNOWS/STEPFUN key 占位（真实 .env 被 gitignore）
      export-public-repo.sh        # 一键抽取为独立公开仓（排除 .env + 密钥自检）
      .github/workflows/ci.yml     # CI：4 套测试自动跑
      rules/
        redflags.yaml              # 确定性规则表（每条带 source，已去 draft）
        sources.md                 # evidence pack：逐规则指南核证 + 引用
      engine/
        triage.py                  # 纯函数规则引擎（可独立运行）
      tests/
        danger_cases.yaml          # 危险案例（绝不能漏判）
        test_triage.py             # 引擎回归（22/22）
        test_pipeline.py           # 端到端冒烟（4/4）
        test_mcp_server.py         # MCP server 握手冒烟
        test_space_app.py          # Space assess 冒烟
        test_intake.py             # 自由文本 intake 安全管道（mock，8/8）
      eval/
        knows_golden_queries.md    # KnowS 覆盖度金标准评测
        intake_cases.yaml          # 自由文本 intake live 评测金标准（12 条）
        run_intake_eval.py         # live intake 评测（需 STEPFUN_API_KEY，无则跳过）
      mcp/
        server.py                      # 标准 stdio MCP server（封装下列工具，零依赖）
        redflag_intake/SPEC.md         # MCP 规格：文本 → 结构化字段
        redflag_intake/form_intake.py  # v0 表单式 intake（无 LLM，可跑）
        redflag_intake/llm_intake.py   # 自由文本 intake（模型无关 + StepFun + 关键词兜底）
        evidence_lookup/SPEC.md        # MCP 规格：循证检索（provider 接口）
        evidence_lookup/local_provider.py  # local provider（本地 evidence pack）
        evidence_lookup/knows_provider.py  # KnowS provider（在线检索，读 env key）
        evidence_lookup/lookup.py          # provider 调度（默认 local，可切 knows）
        evidence_lookup/evidence_pack.yaml # 本地循证数据（摘自 sources.md）
      skill/
        onco-redflag-companion/SKILL.md
        onco-redflag-companion/pipeline.py # 端到端编排（intake→engine→evidence→红旗卡）
      examples/
        sample_cases.md

## 快速开始

    cd onco-redflag
    python3 -m pip install pyyaml          # 唯一依赖
    python3 engine/triage.py               # 引擎单例（化疗后第7天38.5 → RED/FN-001）
    python3 tests/test_triage.py           # 危险案例回归，应 22/22 passed
    python3 skill/onco-redflag-companion/pipeline.py  # 端到端 demo（默认 local 循证）
    python3 tests/test_pipeline.py         # 端到端冒烟，应 4/4 passed
    python3 tests/test_mcp_server.py       # MCP server 握手冒烟，应 ALL PASS
    python3 mcp/server.py                  # 启动 stdio MCP server（供 MCP 客户端挂载）

    # 用 KnowS 在线循证（需 Key）：
    cp .env.example .env && vi .env        # 填入 KNOWS_API_KEY，设 KNOWS_USE=1
    set -a; . ./.env; set +a               # 加载到环境（.env 已被 gitignore）
    python3 skill/onco-redflag-companion/pipeline.py  # RED 场景将挂 KnowS 检出的权威指南

## case 字段 schema（intake 产出 → engine 消费）

见 `engine/triage.py` 顶部 docstring。关键字段：`treatment_type`、`days_since_last_chemo`、
`temp_c`（缺任一 → 默认升级就医）、以及各红旗布尔位（rigors / dyspnea / active_bleeding / …）。

## 开发路线（对齐三阶段奖）

- [x] 确定性规则引擎 + 危险案例回归（**22/22**，含反例/脏输入/边界）
- [x] 过两路对抗复验（Codex + Claude 子 Agent），修掉超窗漏判 / 38℃ 降级 / 脏输入崩溃等（见 ../复验r2-采纳与修复.md）
- [x] `rules/sources.md` 用公开指南（IDSA 2010 / NCI / ACS）固化原文，规则去 draft → validated / validated-operational（CSCO 中文本地化待补）
- [x] `redflag-intake`(v0 表单) + `evidence-lookup`(local provider) + `onco-redflag-companion` 端到端 pipeline 跑通（冒烟 4/4）
- [x] `evidence-lookup` 接入 **KnowS** provider（在线循证，实测返回 CSCO 等指南；默认 local，`KNOWS_USE=1` 切 knows，失败回退）
- [x] 标准 stdio MCP server（`mcp/server.py`：initialize/tools.list/tools.call + redflag_check/evidence_lookup，握手冒烟通过）
- [x] 自由文本 intake（`llm_intake.py`：模型无关 + StepFun 适配器 + 关键词兜底；安全管道 mock 测 8/8；live 评测待 key）
- [ ] 部署魔搭 Space（需账号）
- [ ] 规则全 validated 后过一轮 Codex 对抗复验

## 局限与免责

本工具仅核对**有限的**危险信号，不能覆盖所有急症，**不构成医疗建议、不替代医护判断**。
阈值已用公开指南核证（IDSA 2010 / NCI / ACS，见 `rules/sources.md`，状态 `validated` / `validated-operational`）；
面向真实用户前仍需 **CSCO 中文本地化 + 临床复核**。危急情况请直接拨打 120。

## License

Apache-2.0（见 [LICENSE](LICENSE)）。
