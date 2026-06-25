# 示例输入输出（均为虚构病例）

> 输出由 `python3 engine/triage.py` 实际生成（确定性引擎）。完整判级矩阵见
> `tests/danger_cases.yaml`（**22 例回归，全过**，含反例/脏输入/边界）。
> **示例一律用虚构病例，不含真实身份/病历。** 阈值已用公开指南核证（见 `rules/sources.md`）；
> `validated` 来源不带 note，`validated-operational`（如 GI/低热）会带"数值为保守操作化"提示。

## 1. RED —— 化疗后第 7 天发烧 38.5、有点发抖

输入:

    {"treatment_type": "cytotoxic_chemo", "days_since_last_chemo": 7, "temp_c": 38.5, "temp_route": "oral", "rigors": true}

输出（节选）:

    {
      "level": "RED",
      "rule_id": "FN-001",
      "reason": "发热（化疗后 ≥38℃，疑似中性粒细胞减少性发热，急症）",
      "action": "化疗后发热（≥38℃）属急症…请立即联系治疗团队或前往急诊，不要在家等待。",
      "source": "idsa_fn_2010",
      "source_status": "validated",
      "prepare_for_visit": ["末次化疗/治疗的日期与方案名称", "..."]
    }

## 2. ESCALATE —— 化疗第 30 天发烧 38.5（超出 0–21 天窗口）

> 这是复验 r2 修掉的**致命漏判**：旧版会判 `NO_REDFLAG`（"无红旗"），现在一律升级。

输入:

    {"treatment_type": "cytotoxic_chemo", "days_since_last_chemo": 30, "temp_c": 38.5}

输出（节选）:

    {
      "level": "ESCALATE",
      "rule_id": "ESC-WINDOW",
      "reason": "末次化疗天数 30 超出本工具覆盖窗口（0–21 天）",
      "action": "你的情况超出本工具覆盖的化疗后 0–21 天窗口（或日期异常），无法排除风险，请联系治疗团队；若有不适请前往急诊。"
    }

## 3. NO_REDFLAG —— 化疗第 8 天、信息齐、无任何红旗（合法可达）

输入:

    {"treatment_type": "cytotoxic_chemo", "days_since_last_chemo": 8, "temp_c": 36.8}

输出（节选）:

    {
      "level": "NO_REDFLAG",
      "rule_id": null,
      "action": "本工具未覆盖到需要立即就医的红旗信号——但这不代表安全。本工具只检查有限的危险信号，覆盖范围窄。若症状持续/加重，或你有任何不放心，请联系治疗团队。"
    }

> 注：NO_REDFLAG 仅在"范围内 + 信息齐 + 在窗 + 无任何红旗"时可达，文案**明确不安抚**。
