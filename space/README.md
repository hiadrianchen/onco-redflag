# 魔搭 Space 部署指引（OncoRedFlag demo）

> 这是给 chenjie 操作的部署步骤（Phase 4 的 [USER] 部分）。AGENT 已备好 `app.py` + `requirements.txt`。

## 适老化与自适应（对外加分点）

- **大字号、高对比、大点击区**：肿瘤患者多为中老年，默认 18px 起，页面内「大字模式」一键放大到 22px。
- **四色清晰卡片**：红/黄/橙/灰一眼看懂"该不该立刻就医"。
- **PC / 平板 / 手机自适应**：同一链接，手机即 H5 体验，无需下载。

## 本地预览
```bash
cd onco-redflag
pip install -r space/requirements.txt
python3 space/app.py            # 打开 http://127.0.0.1:7860
```

## 部署到魔搭创空间（Space）
1. 登录 ModelScope → 创空间（Studio）→ 新建，SDK 选 **Gradio**。
2. 关联代码：把 `onco-redflag/` 作为 Space 仓库（公开仓 graduate 后用它），**入口文件指向 `space/app.py`**；
   或把 `space/app.py` 提到仓库根并把 `engine/ mcp/ skill/ rules/` 一起带上（app.py 用相对路径找这些目录）。
3. 依赖：`space/requirements.txt`（gradio + pyyaml）。
4. （可选）循证用 KnowS：在 Space 的环境变量里加 `KNOWS_API_KEY` 与 `KNOWS_USE=1`；**不要把 key 写进代码或仓库**。
5. 启动后用首页 Example（化疗第7天38.5+寒战 → RED）自测。

## 安全/合规复核（上线前必看）
- 首屏须显著展示：不诊断、不替代急诊、非急救通道、危急拨 120、仅虚构病例勿输真实信息（`app.py` 已内置 DISCLAIMER）。
- 不收集、不持久化任何用户输入；Space 不要开启会落库的日志。
- 判定逻辑与 CLI/MCP 同一套确定性引擎，Space 仅 UI 包装。
