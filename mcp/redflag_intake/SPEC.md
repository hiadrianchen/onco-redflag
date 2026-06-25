# MCP 工具：redflag-intake（规格草案）

> 职责：把用户的**自由文本描述**抽取成结构化 `case`（供确定性引擎消费）。
> **只抽取、不判定**；抽不准/没说到的字段一律留 `null`（由引擎走"信息不足→升级"）。

## tool name
redflag_intake

## input
    { "text": "用户的自由描述，例如：我爸化疗第7天，今天下午开始发烧38.5度，有点发抖" }

## output（结构化 case，字段与 engine/triage.py schema 对齐）
    {
      "case": {
        "treatment_type": "cytotoxic_chemo|immunotherapy|targeted|radiation|other|null",
        "days_since_last_chemo": "int|null",
        "temp_c": "float|null",
        "temp_route": "oral|axillary|ear|forehead|null",
        "temp_duration_min": "int|null",
        "rigors": "bool|null",
        "dyspnea": "bool|null",
        "chest_pain": "bool|null",
        "cyanosis": "bool|null",
        "altered_consciousness": "bool|null",
        "active_bleeding": "bool|null",
        "hematemesis_melena": "bool|null",
        "vomiting_unable_intake_hours": "int|null",
        "diarrhea_count_per_day": "int|null",
        "diarrhea_bloody": "bool|null",
        "has_cvc": "bool|null",
        "cvc_site_inflamed": "bool|null",
        "age": "int|null",
        "patient_group": "solid_tumor|hematologic|transplant|pregnant|null"
      },
      "missing_fields": ["temp_route", "..."],
      "notes": "抽取时的不确定点（可选）"
    }

## 抽取规则（安全优先）
- **不脑补**：用户没明确说的，留 `null`，不要根据"常理"填默认值。
- 数值带单位歧义（体温 38 / 38.0、腹泻"好几次"）→ 能确定才填，否则 `null` 并在 notes 说明。
- 涉及"是否危急/要不要去医院"的判断**不在本工具做**——本工具只填字段。
- 抽取置信度低的关键字段（treatment_type / days / temp）宁可留 `null`，触发引擎升级。
- **类型**：数值字段输出真正的 number、布尔字段输出真正的 bool（引擎虽对脏输入做强转兜底，但 intake 不应依赖它）。
- **禁忌筛查（强制）**：识别"儿童 / 血液肿瘤 / 移植 / 孕产 / 免疫治疗 / 靶向 / 放疗"等信号，落到 `age` / `patient_group` / `treatment_type`，让引擎在范围守门处排除（见 SAFETY.md §6）。
- 描述里的"胸痛 / 口唇发绀 / 呕血 / 黑便"分别落到 `chest_pain` / `cyanosis` / `hematemesis_melena`，不要折叠丢失。

## 已实现：`llm_intake.py`（模型无关 + StepFun 适配器）

- `extract(text, llm=callable)`：模型无关；缺省用 StepFun（读 `STEPFUN_API_KEY`，OpenAI 兼容 `/chat/completions`）。
- **安全管道**（hermetic 单测 `tests/test_intake.py` 8/8）：脏输出/无法解析 → 全 None → 引擎信息不足 ESCALATE，不崩溃；容忍代码围栏 JSON。
- **关键词兜底**：LLM 漏抽时，文本里的儿童/血液瘤/移植/孕产/免疫/靶向信号仍强制落到 case → 引擎范围守门升级（只往就医方向，不放松）。
- **live 评测**：`eval/intake_cases.yaml`（12 条自由文本→期望级）+ `eval/run_intake_eval.py`（有 key 才跑，**漏判 RED 即不达标**）。
- 接入：`pipeline.run_text(text)` 走 LLM intake；表单/MCP/Space 默认走结构化 `form_intake`（不依赖 key，更稳）。

## 实现备注
- v0 用 StepFun（`STEPFUN_MODEL` 可配，默认 step-1-8k）+ 严格 JSON 抽取 prompt（temperature 0，只输出 JSON）。
- 非必须：无 StepFun 也能用结构化表单 intake 跑全链路（见 README）。
