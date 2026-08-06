#!/usr/bin/env bash
# ============================================================
# 测试环境启动脚本（dev 分支）
#   页面: http://127.0.0.1:8080  (dev 代码 + 测试数据)
#   API : http://127.0.0.1:8765
#   数据: 当前工作区 metrics/ 等（测试数据）
# ============================================================
set -e
cd "$(dirname "$0")/.."

# 端口可被环境变量覆盖
UI_PORT="${UI_PORT:-8080}"
API_PORT="${API_PORT:-8765}"

echo "▶ 启动测试环境 (dev)"
echo "  页面: http://127.0.0.1:${UI_PORT}  |  API: http://127.0.0.1:${API_PORT}"

# 1. 启动 API（当前工作区 = 测试数据）
export PYTHONPATH=src
PY_BIN="${PY_BIN:-$(pwd)/.venv/bin/python}"
if [ ! -x "${PY_BIN}" ]; then echo "❌ 未找到 venv python: ${PY_BIN}"; exit 1; fi
"${PY_BIN}" -m data_governance.cli serve --host 127.0.0.1 --port "${API_PORT}" &
API_PID=$!

# 2. 启动静态页
python3 -m http.server "${UI_PORT}" --directory ui-prototype --bind 127.0.0.1 &
UI_PID=$!

echo "  进程: API=${API_PID}  UI=${UI_PID}"
echo "  停止: kill ${API_PID} ${UI_PID}"

# 保持前台
trap "kill $API_PID $UI_PID 2>/dev/null" EXIT
wait
