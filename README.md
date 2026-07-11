# 有爱无恙 · OncoRedFlag —— 化疗居家红旗信号核对与就医决策助手

> **Team Nightlight** ｜ 2026 小X宝开源医疗社区黑客松（通用医学 / 肿瘤方向）
> 🔗 魔搭创空间：<https://modelscope.cn/studios/AdrianChen/onco-redflag> ｜ 📄 License：Apache-2.0

---

## 1. 项目简介与医疗场景

- **一句话**：帮**化疗期肿瘤患者和家属**只回答一件事——**现在要不要立刻联系治疗团队/挂急诊**，以及去之前该把哪些信息讲清楚给医生。
- **解决的痛点**：化疗后居家最凶险的窗口，患者和家属常在深夜面对"38 度算不算发烧""要不要跑急诊"这类判断，一边是病友群里"发物忌口""白细胞低别出门"的经验之谈，一边是查不到、看不懂的专业指南。**判断失误的代价是双向的**：漏判中性粒细胞减少性发热可能危及生命，过度就医又徒增奔波。这个工具把"要不要就医"这一步做窄、做确定、做得可审计。
- **目标受众**：化疗期肿瘤患者及其家属（第一受众，界面按适老化设计）；也可作为 MCP 工具/Skill 集成进面向患者的 AI 助手。

## 2. 功能特性

- **确定性分诊引擎（安全命门）**：判级完全由 `rules/redflags.yaml` + `engine/triage.py` 的纯函数规则决定，**不交给大模型**。评估顺序写死为：通用急症 → 覆盖范围守门 → 专项红旗 → 信息不足即升级 → 低危 AMBER → 未触发也不安抚。**引擎里没有"你没事/在家观察"这一级**——缺信息、超范围、超窗、脏输入一律 fail-safe 升级就医。
- **三层循证展示**：本地已核证证据兜底（真实 url + 原文片段）→ KnowS 在线指南 → KnowS 论文（可点 DOI）。**查不到就说查不到，绝不编造 url / DOI / 证据分级**；在线检索弱结果宁可回落本地保底，也不硬塞偏题文献。
- **病友群谣言辟谣专区**：人工撰写、逐条挂真实指南的循证辟谣卡，覆盖 3 条高频谣言——"化疗要忌发物""饿死癌细胞""白细胞低绝对不能出门"。每条都桥回就医判断，**辟谣文案同样不含放行宽慰语**。
- **适老化 + 全端自适应**：默认大字号、高对比、大点击区（患者多为中老年）；四色卡片（红/橙/黄/灰）一眼看懂"该不该立刻就医"；同一链接 PC / 平板 / 手机自适应，手机浏览器直接打开即用，无需下载。
- **一套内核，三种形态**：同一套安全内核同时以 **Agent 应用（魔搭 Space）+ MCP 工具（`redflag_check` / `evidence_lookup`）+ Skill（`onco-redflag-companion`）** 三种形态交付，可独立运行，也可集成进现有 Agent 框架。

## 3. 魔搭社区运行 / 部署指南

- **魔搭展示链接**：<https://modelscope.cn/studios/AdrianChen/onco-redflag>（Gradio 创空间，公开可访问；首次访问若处于休眠会冷启动，稍等即可）
- **本地运行**（唯一依赖 pyyaml；接在线循证再加 gradio）：

  ```bash
  cd onco-redflag
  python3 -m pip install pyyaml                       # 引擎/测试的唯一依赖
  python3 engine/triage.py                            # 引擎单例：化疗后第7天38.5 → RED/FN-001
  python3 tests/test_triage.py                        # 危险案例回归，应 38/38 passed
  python3 skill/onco-redflag-companion/pipeline.py    # 端到端 demo（默认 local 循证）
  python3 mcp/server.py                               # 启动 stdio MCP server（供 MCP 客户端挂载）

  # 起交互网页（本地预览 Space）：
  python3 -m pip install -r space/requirements.txt
  python3 space/app.py                                # 打开 http://127.0.0.1:7860
  ```

- **用 KnowS 在线循证**（需 Key）：

  ```bash
  cp .env.example .env && vi .env    # 填入 KNOWS_API_KEY，设 KNOWS_USE=1
  set -a; . ./.env; set +a           # 加载到环境（.env 已被 .gitignore 忽略，绝不入库）
  python3 skill/onco-redflag-companion/pipeline.py   # RED 场景将挂 KnowS 检出的权威指南
  ```

## 4. 演示与输入输出示例

> 以下输出均由 `python3 engine/triage.py` 的确定性引擎实际生成，**病例一律虚构，不含任何真实身份/病历**。完整判级矩阵见 [`examples/sample_cases.md`](examples/sample_cases.md) 与 [`tests/danger_cases.yaml`](tests/danger_cases.yaml)（38 例回归，全过）。

**① RED —— 化疗后第 7 天发烧 38.5、有点发抖**

```
输入：{"treatment_type":"cytotoxic_chemo","days_since_last_chemo":7,"temp_c":38.5,"temp_route":"oral","rigors":true}
输出：level=RED  rule_id=FN-001
     reason=发热（化疗后 ≥38℃，疑似中性粒细胞减少性发热，急症）
     action=请立即联系治疗团队或前往急诊，不要在家等待。
     source=idsa_fn_2010（validated）
```

**② ESCALATE —— 化疗第 30 天发烧 38.5（超出 0–21 天覆盖窗口）**

```
输入：{"treatment_type":"cytotoxic_chemo","days_since_last_chemo":30,"temp_c":38.5}
输出：level=ESCALATE  rule_id=ESC-WINDOW
     reason=末次化疗天数 30 超出本工具覆盖窗口（0–21 天）
     action=超出覆盖窗口无法排除风险，请联系治疗团队；若有不适请前往急诊。
```
> 这是对抗复验修掉的一处致命漏判：旧版会判"无红旗"，现在一律 fail-safe 升级。

**③ NO_REDFLAG —— 化疗第 8 天、信息齐、无任何红旗（合法可达，但不安抚）**

```
输入：{"treatment_type":"cytotoxic_chemo","days_since_last_chemo":8,"temp_c":36.8}
输出：level=NO_REDFLAG  rule_id=null
     action=本工具未覆盖到需立即就医的红旗信号——但这不代表安全。覆盖范围窄，
            若症状持续/加重，或你有任何不放心，请联系治疗团队。
```

> 四色结果卡与辟谣专区的实际观感建议在魔搭链接现场体验；如需静态截图可在演示材料中补充。

## 5. 局限性与未来规划

**如实说明局限（医疗应用需严谨）：**

- 只核对**有限的**危险信号，**不能覆盖所有急症**，不构成医疗建议、不替代医护判断；危急情况请直接拨打 120。
- 覆盖范围窄：仅限**细胞毒化疗后 0–21 天**窗口；**不覆盖**儿童、免疫治疗、靶向、血液肿瘤、移植、孕产——命中即升级"请联系治疗团队/急诊"。
- 阈值已用公开指南核证（IDSA 2010 / NCI / ACS 等，见 [`rules/sources.md`](rules/sources.md)，状态 `validated` / `validated-operational`）；面向真实用户前仍需 **CSCO 中文本地化 + 临床复核**。

**未来规划：**

- 规则全量 validated 后再过一轮 Codex 对抗复验；补 CSCO 中文本地化阈值。
- 扩充辟谣专区（保持"有权威依据才收"的门槛）；接入更多真实中文专家共识作为分簇 source。

## 6. 团队与致谢

- **Team Nightlight** —— 光已成炬，照亮崎岖。
- 感谢 **小X宝开源医疗社区 × 魔搭 ModelScope 社区** 主办本次黑客松；感谢 **KnowS** 提供医学循证证据检索 API 与开发者 Skill 支持。
- 引证指南来源：IDSA 中性粒细胞减少性发热指南、NCI/ACS 患教材料、急性呼吸衰竭/血小板减少症/恶心呕吐·腹泻管理等中文专家共识（逐条见 `rules/sources.md` 与 `mcp/evidence_lookup/evidence_pack.yaml`）。

---

## 医疗合规性声明（Bonus）

- 本工具的输出**不作为最终医疗诊断依据**，不诊断、不判断病因、不解读预后、不承诺任何治疗结论。
- 判级只服务于"要不要就医"这一步，且**只会升级、不会放行**（引擎无 GREEN 级）。
- **禁用真实患者数据**：全部示例与测试用例均为虚构；密钥经 `.env` 隔离，绝不硬编码入库（`export-public-repo.sh` 导出时做密钥自检）。
- 详细边界、判级语义、数据红线见 [SAFETY.md](SAFETY.md)。

## 评测数据报告（Bonus）

安全性用**危险案例回归**衡量——这是本工具的命门指标，要求"绝不漏判、绝不错误放行"。

| 测试套件 | 用例数 | 结果 | 说明 |
|---|---|---|---|
| `test_triage.py` 危险案例回归 | **38** | ✅ 全过 | 含反例 / 脏输入 / 边界 / 超窗漏判 |
| `test_evidence_contract.py` 循证契约 | 14 | ✅ 全过 | 三层循证不编造 url/doi 的契约 |
| `test_space_app.py` Space 冒烟 | ALL | ✅ | assess 端到端 |
| `test_pipeline.py` 端到端冒烟 | 4 | ✅ | intake→engine→evidence→红旗卡 |
| `test_intake.py` intake 安全管道 | 8 | ✅ | 自由文本抽取（mock） |
| `test_mcp_server.py` MCP 握手 | ALL | ✅ | initialize/tools.list/tools.call |

38 例危险案例的判级分布：**RED 23 / ESCALATE 9 / AMBER 4 / NO_REDFLAG 2**——覆盖"必须红、必须升级、可低危、可合法无红旗但不安抚"四类边界；每条都断言"绝不降级/绝不放行"。另有 `eval/` 下 KnowS 循证覆盖度金标准与自由文本 intake 评测集（12 条，需 key 时 live 跑）。

## 架构（把"判断权"从 LLM 手里拿走）

```
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
```

- **红旗判定的唯一依据**是 `rules/redflags.yaml`（确定性、可审计、可单测），**不是模型**。
- LLM 只做两件事：把自由文本抽成字段（intake）、把结果讲成人话（skill）。
- 安全语义全部写在 `engine/triage.py` 的评估顺序里。

## 目录结构

```
onco-redflag/
  README.md  LICENSE(Apache-2.0)  NOTICE  SAFETY.md  使用说明.md
  .env.example                 # KNOWS/STEPFUN key 占位（真实 .env 被 gitignore）
  export-public-repo.sh        # 一键抽取为独立公开仓（排除 .env + 密钥自检）
  rules/
    redflags.yaml              # 确定性规则表（每条带 source）
    myths.yaml                 # 循证辟谣卡（3 条，逐条挂真实来源）
    sources.md                 # evidence pack：逐规则指南核证 + 引用
  engine/triage.py             # 纯函数规则引擎（可独立运行）
  mcp/
    server.py                  # 标准 stdio MCP server（redflag_check + evidence_lookup）
    redflag_intake/            # 文本 → 结构化字段（表单式 + 自由文本 + 关键词兜底）
    evidence_lookup/           # 三层循证（local pack / KnowS provider / 调度）
  skill/onco-redflag-companion/  # 端到端编排（intake→engine→evidence→红旗卡）
  space/app.py                 # 魔搭 Space 交互界面（Gradio，适老化 + 三层循证）
  tests/                       # 危险案例 38 例 + 契约/冒烟/intake 全套
  eval/                        # KnowS 覆盖度金标准 + intake live 评测集
```

## License

Apache-2.0（见 [LICENSE](LICENSE)）。完整使用说明见 [使用说明.md](使用说明.md)。
