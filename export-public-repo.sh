#!/usr/bin/env bash
# 把 onco-redflag/ 抽取为独立公开仓的内容（排除 .env 等私有物），并做密钥自检。
# 用法：./export-public-repo.sh <目标空目录>
# 之后：cd <目标目录> && git init && git add -A && git commit -m "init" && 推到你的公开仓。
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${1:?用法: export-public-repo.sh <目标空目录>}"
mkdir -p "$DEST"

rsync -a \
  --exclude '.env' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  "$SRC/" "$DEST/"

# 密钥自检：只匹配"真实样子"的 key（长随机串），排除占位符(xxxx)与本脚本自身。
LEAK="$(grep -rInE 'sk-knows-[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{24,}' "$DEST" \
        --exclude='export-public-repo.sh' 2>/dev/null || true)"
if [ -n "$LEAK" ]; then
  echo "ABORT: 导出物中发现疑似真实密钥，请检查后重试。" >&2
  echo "$LEAK" >&2
  exit 1
fi

echo "已导出到: $DEST（已排除 .env，密钥自检通过）"
echo "下一步：cd \"$DEST\" && git init && git add -A && git commit -m 'init: OncoRedFlag' && git remote add origin <你的公开仓> && git push -u origin main"
