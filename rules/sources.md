# rules/sources.md — 红旗阈值白名单指南登记表（evidence pack）

> `redflags.yaml` 每条规则的 `source` 字段对应下表一个 key。
> **本轮已用公开权威指南核证（2026-06-24，不依赖 KnowS）**；阈值与出处见下。
> KnowS Key 到手后仅作 `evidence-lookup` 的动态补充检索，不改变这里固化的阈值。
>
> 状态：`validated` = 阈值直接来自所引指南原文；`validated-operational` = 定性依据来自指南、
> 具体数值为本工具的**保守操作化**（非指南逐字数值，引擎会在输出加 `source_note` 提示）。
> 红线：阈值只能来自下列权威来源；不得由模型推断或编造。中文本地化（CSCO）见 §3 待补。

## 1. 权威来源（公开可访问，已实查）

| key | 指南/材料 | 引用 / 链接 |
|---|---|---|
| `idsa_fn_2010` | IDSA 中性粒细胞减少肿瘤患者抗菌药物使用临床实践指南（2010 更新） | Freifeld AG, Bow EJ, Sepkowitz KA, et al. *Clin Infect Dis.* 2011;52(4):e56–e93. https://academic.oup.com/cid/article/52/4/e56/382256 |
| `nci_infection` | NCI《Infection and Neutropenia during Cancer Treatment》（患者教育） | National Cancer Institute. https://www.cancer.gov/about-cancer/treatment/side-effects/infection |
| `acs_when_to_call` | ACS《Chemotherapy Side Effects》"何时联系治疗团队 / 急救" | American Cancer Society. https://www.cancer.org/cancer/managing-cancer/treatment-types/chemotherapy/chemotherapy-side-effects.html |
| `nccn_gi_management` | （定性依据见 ACS/NCI；数值参 CTCAE 分级，见 §2 GI-001） | 数值为操作化，CSCO/NCCN 中文版待补 |

> 注：`redflags.yaml` 历史上的 `source: nccn_thrombocytopenia / idsa_clabsi` 已并入上述实查来源
> （出血 → ACS/NCI；导管 → NCI/ACS），见下表"覆盖规则"列。

## 2. 逐规则核证

| rule | 核证阈值 / 原文要点 | 来源 | 状态 |
|---|---|---|---|
| **FN-001** 发热≥38.0℃→RED | IDSA 发热定义：单次口温 **≥38.3℃(101°F)** 或 **≥38.0℃(100.4°F) 持续1h**；NCI 患教：**≥38℃(100.5°F) 即联系治疗团队**；ACS：通常 ≥100.5–101°F 口温联系。本工具取**单次≥38.0℃即 RED**（比 IDSA 临床定义更保守，对齐 NCI 患者就医阈值；不依赖"持续1h"，时长未知不下调风险）。 | idsa_fn_2010 / nci_infection / acs_when_to_call | **validated** |
| **FN-002** 寒战/僵直→RED | NCI 感染征象含 **"chills"**；ACS 含 **"intense chills"**。寒战常为严重感染早期信号，按联系治疗团队处理。 | nci_infection / acs_when_to_call | **validated** |
| **CVC-001** 导管红肿→RED | NCI：**"swelling or redness, especially where a catheter enters your body"** 属需联系信号；ACS：**"pain or soreness at … catheter site"**。 | nci_infection / acs_when_to_call | **validated** |
| **EMG-002** 气促/胸痛/发绀→RED | ACS：**"Shortness of breath or trouble breathing (If you're having trouble breathing, call 911 first.)"**。胸痛/发绀按通用急救常识纳入（≥气促同级处理）。 | acs_when_to_call | **validated** |
| **EMG-003** 出血/呕血黑便→RED | ACS：**"Bleeding or unexplained bruising"、"Bloody stool or blood in your urine"**；NCI：**"urine that is bloody…"**。呕血/黑便按急症纳入。 | acs_when_to_call / nci_infection | **validated** |
| **EMG-001** 意识改变→RED | 神志改变/抽搐属任何情况下的急救范畴（拨 120），通用急救常识；癌症患教未单列但不降级。 | （通用急症标准） | **validated-operational** |
| **GI-001** 呕吐/腹泻致脱水→RED | 定性依据：ACS **"Long-lasting diarrhea or vomiting"、"Bloody stool"**；NCI 列 "diarrhea"。**数值为操作化**：腹泻 ≥6 次/日（参 CTCAE 腹泻分级，3 级≈较基线 ≥7 次/日，本工具取更保守的 ≥6）、呕吐无法进食/饮水 ≥24h（脱水风险）、血便。 | acs_when_to_call / nci_infection（+CTCAE 参考） | **validated-operational** |
| **AMB-001** 低热37.5–37.9→AMBER | 指南就医阈值是 **38.0℃**；**37.5–37.9℃ 为本工具的保守观察带**（规范复测+联系咨询），非指南逐字数值。 | idsa_fn_2010 / nci_infection | **validated-operational** |

## 3. 待补（不阻塞，提质项）

- **CSCO 中文本地化**：用 CSCO《肿瘤治疗相关感染》《CINV / 腹泻管理》等中文指南交叉复核上述阈值与表述，提升中文场景适配（KnowS Key 到手可加速检索）。
- **导管/出血**可补 IDSA CLABSI、血小板减少出血处理的专项原文，进一步加固 CVC-001 / EMG-003。
- GI-001 的数值阈值若 CSCO/NCCN 有更适配的患者版数值，按指南替换并去 `-operational`。

## 4. 固化流程（每个 source key）

1. 用上面来源（或 KnowS）检出权威原文，摘录阈值与适用条件 → 填本表。
2. 比对 `redflags.yaml` 阈值；不一致以指南为准，改规则表并跑 `tests/test_triage.py` 全过。
3. 直接来自指南 → `validated`；定性依据+操作化数值 → `validated-operational`（输出会标注）。
4. 全表稳定后整体过一轮 `codex_cross_review.sh`（安全命门复验）。
