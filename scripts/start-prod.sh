#!/usr/bin/env bash
# ============================================================
# 生产环境启动脚本（main 分支，生产工作区 data_go_prod/）
#   页面: http://127.0.0.1:8081  (main 代码 + 生产数据)
#   API : http://127.0.0.1:8766
#   数据: prod-data/（正式录入数据）
# 注意：生产环境默认使用 ./prod-data 作为 base-dir，
#       避免与测试环境（dev 工作区）的数据互相污染。
# ============================================================
set -e
cd "$(dirname "$0")/.."

UI_PORT="${UI_PORT:-8081}"
API_PORT="${API_PORT:-8766}"
BASE_DIR="${BASE_DIR:-$(pwd)/prod-data}"

echo "▶ 启动生产环境 (main)"
echo "  页面: http://127.0.0.1:${UI_PORT}  |  API: http://127.0.0.1:${API_PORT}"
echo "  数据: ${BASE_DIR}"

# 数据目录检查：生产必须有 prod-data（正式数据从此开始录入）
if [ ! -d "${BASE_DIR}" ]; then
  echo "❌ 生产数据目录不存在: ${BASE_DIR}" >&2
  echo "   请先创建并录入正式数据（参照测试环境 metrics/ 结构）" >&2
  exit 1
fi

# 防污染门禁：生产数据目录中禁止出现测试编号指标（_N 后缀）
# 误把测试数据当生产启动时直接拒绝，避免污染正式库
TEST_MARK="$(grep -l "_N[0-9]" "${BASE_DIR}"/metrics/*_metrics.csv 2>/dev/null | head -1)"
if [ -n "${TEST_MARK}" ]; then
  echo "❌ 生产数据目录含测试编号指标: ${TEST_MARK}" >&2
  echo "   生产环境禁止使用测试数据！请检查 BASE_DIR 配置。" >&2
  exit 1
fi

# 1. 启动 API（prod-data = 生产数据）
export PYTHONPATH=src
PY_BIN="${PY_BIN:-$(pwd)/.venv/bin/python}"
if [ ! -x "${PY_BIN}" ]; then echo "❌ 未找到 venv python: ${PY_BIN}"; exit 1; fi
"${PY_BIN}" -m data_governance.cli serve --host 127.0.0.1 --port "${API_PORT}" --base-dir "${BASE_DIR}" &
API_PID=$!

# 2. 启动静态页（生产页面注入 API 端口 8766）
#    用临时 html 注入 DG_API_FALLBACK，避免改仓库内文件
TMP_UI="$(mktemp -d)"
cp -r ui-prototype/* "${TMP_UI}/"
# 在 <head> 后注入 API fallback（生产 API 端口）
python3 - "$TMP_UI/index.html" "${API_PORT}" <<'PYEOF'
import sys
path, port = sys.argv[1], sys.argv[2]
html = open(path, encoding='utf-8').read()
inject = f'<script>window.DG_API_FALLBACK="http://127.0.0.1:{port}";</script>'
if 'DG_API_FALLBACK' not in html:
    html = html.replace('<head>', '<head>\n  ' + inject, 1)
    open(path, 'w', encoding='utf-8').write(html)
PYEOF
python3 -m http.server "${UI_PORT}" --directory "${TMP_UI}" --bind 127.0.0.1 &
UI_PID=$!

echo "  进程: API=${API_PID}  UI=${UI_PID}（临时目录 ${TMP_UI}）"
echo "  停止: kill ${API_PID} ${UI_PID}"

trap "kill $API_PID $UI_PID 2>/dev/null; rm -rf ${TMP_UI}" EXIT
wait
