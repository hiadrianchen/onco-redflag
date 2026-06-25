# 贡献指南 · OncoRedFlag

欢迎一起把这个"化疗期红旗信号核对"工具的**安全网越织越密**。最有价值的贡献是**虚构红旗案例**。

## 🚨 安全红线（必读）

- 本工具**不诊断、不替代医护判断，也不是急救通道**；危急请拨 120。
- **禁止提交任何真实患者数据**（身份、病历、真实症状求助）。一切案例必须是**虚构**的。
- 阈值/规则改动**必须**有权威指南出处（IDSA / NCI / ACS / CSCO 等），不接受"凭经验"的阈值。

## 贡献虚构红旗案例（最欢迎）

1. 开 Issue，选「虚构红旗案例贡献」模板，填：虚构场景 + 你认为的判级 + 依据。
2. Maintainer 复核后，把它写进 `tests/danger_cases.yaml`（带你的署名）并跑回归。
3. 从此你的案例成为一条**永久回归测试**——任何会让它漏判的改动都会被 CI 拦下。

> 这就是"社区共建"的形态：不是来试你的真实症状，而是一起扩充**虚构病例的安全测试集**。

## 贡献代码 / 规则

1. Fork → 改 → 确保 `python3 tests/test_triage.py` 与其它测试**全过**。
2. 改 `rules/redflags.yaml` 必须：① 在 `rules/sources.md` 标明指南出处；② 配套新增危险案例。
3. 发 PR，说明动机与依据。涉及红旗阈值的改动会被重点复核。

## 本地自测

```bash
pip install pyyaml
python3 tests/test_triage.py      # 危险案例回归
python3 tests/test_pipeline.py    # 端到端
python3 tests/test_mcp_server.py  # MCP server
python3 tests/test_intake.py      # 自由文本 intake 安全管道
```

## 行为准则

就事论事、尊重医疗边界、对患者善意。涉及真实医疗求助的内容会被关闭并提示就医。
