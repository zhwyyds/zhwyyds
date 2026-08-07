#!/usr/bin/env bash
# ============================================================================
# 启动数据治理平台（独立于终端会话运行）
# 用法：
#   ./start.sh              # 默认 DATA_GOV_LLM_MODE=auto, PORT=8765
#   DATA_GOV_LLM_MODE=mock ./start.sh   # mock 模式
#   PORT=9000 ./start.sh    # 换端口
# 日志：/tmp/dg_serve.log（追加）
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")"

export DATA_GOV_LLM_MODE="${DATA_GOV_LLM_MODE:-auto}"
PORT="${PORT:-8765}"

# 若已有进程在跑，先停
if lsof -ti tcp:"$PORT" >/dev/null 2>&1; then
  echo "端口 $PORT 已有服务，先停止旧进程…"
  lsof -ti tcp:"$PORT" | xargs kill 2>/dev/null || true
  sleep 1
fi

nohup .venv/bin/python -m uvicorn data_governance.api.app:create_app --factory \
  --port "$PORT" >> /tmp/dg_serve.log 2>&1 &

echo "✅ 已启动（pid=$!，模式=${DATA_GOV_LLM_MODE}）"
echo "   页面：http://127.0.0.1:${PORT}/"
echo "   日志：tail -f /tmp/dg_serve.log"
