#!/bin/bash
# 不需 Claude Code：模擬 statusLine 餵資料、驗證 /api/stats 彙整是否正確
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
export CC_TOKEN_DASH_DIR="$(mktemp -d)/dash"
PORT="${PORT:-8807}"

echo "1) 語法檢查"
"$PY" -c "import ast; ast.parse(open('$ROOT/src/cc_token_dashboard.py').read()); print('  OK')"

echo "2) 模擬收集器寫入兩個工作階段、兩個專案"
echo '{"session_id":"A","workspace":{"project_dir":"/x/aicms"},"model":{"display_name":"Opus 4.6"},"cost":{"total_cost_usd":0.30},"context_window":{"total_input_tokens":60000,"total_output_tokens":1500,"used_percentage":18}}' | "$PY" "$ROOT/src/cc_token_dashboard.py" status >/dev/null
echo '{"session_id":"A","workspace":{"project_dir":"/x/aicms"},"model":{"display_name":"Opus 4.6"},"cost":{"total_cost_usd":0.50},"context_window":{"total_input_tokens":99000,"total_output_tokens":2600,"used_percentage":24}}' | "$PY" "$ROOT/src/cc_token_dashboard.py" status >/dev/null
echo '{"session_id":"B","workspace":{"project_dir":"/x/citablerank"},"model":{"display_name":"Sonnet 4.6"},"cost":{"total_cost_usd":0.04},"context_window":{"total_input_tokens":10000,"total_output_tokens":300,"used_percentage":9}}' | "$PY" "$ROOT/src/cc_token_dashboard.py" status >/dev/null
echo '{"session_id":"B","workspace":{"project_dir":"/x/citablerank"},"model":{"display_name":"Sonnet 4.6"},"cost":{"total_cost_usd":0.09},"context_window":{"total_input_tokens":25000,"total_output_tokens":900,"used_percentage":12}}' | "$PY" "$ROOT/src/cc_token_dashboard.py" status >/dev/null

echo "3) 啟動伺服器並查 /api/stats"
"$PY" "$ROOT/src/cc_token_dashboard.py" serve --port "$PORT" --no-open >/tmp/cc_srv.log 2>&1 &
SRV=$!; sleep 1.5
curl -s "http://127.0.0.1:$PORT/api/stats" | "$PY" -c "import sys,json; d=json.load(sys.stdin); print('  本日產出:',d['totals']['out']); print('  各專案:',[(p['name'],p['out']) for p in d['projects']]); assert d['totals']['out']==(1100+600), '彙整不符!'; print('  ✅ 彙整正確（aicms 1100 + citablerank 600 = 1700）')"
kill $SRV 2>/dev/null || true
echo "完成"
