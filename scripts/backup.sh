#!/usr/bin/env bash
# 数据治理平台每日备份脚本（IT1-3）
#
# 用法：
#   scripts/backup.sh [项目根目录]
#   KEEP_DAYS=14 scripts/backup.sh   # 保留最近 14 天（默认 7）
#
# 行为：
#   1. 将 config/ roots/ metrics/ lineage/ reviews/ scores/ releases/ 快照到 backup/YYYY-MM-DD_HHMMSS/
#   2. 清理超过 KEEP_DAYS 天的旧备份
#
# 恢复：
#   将 backup/<时间戳>/ 下对应目录复制回项目根即可，例如：
#     cp -R backup/2026-08-05_120000/metrics ./metrics
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
BACKUP_ROOT="$ROOT/backup"
KEEP_DAYS="${KEEP_DAYS:-7}"
STAMP="$(date +%Y-%m-%d_%H%M%S)"
DEST="$BACKUP_ROOT/$STAMP"
DIRS=(config roots metrics lineage reviews scores releases)

mkdir -p "$DEST"
for d in "${DIRS[@]}"; do
  if [ -d "$ROOT/$d" ]; then
    cp -R "$ROOT/$d" "$DEST/$d"
  fi
done

# 清理过期备份（保留最近 KEEP_DAYS 天）
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +"$KEEP_DAYS" -exec rm -rf {} + 2>/dev/null || true

echo "backup done: $DEST"
ls "$DEST"
