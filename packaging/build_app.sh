#!/bin/bash
# 用 py2app 打包「自包含、不依賴系統 Python」的 .app（並做 .dmg）
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY3="${PYTHON:-$(command -v python3 || true)}"
[ -z "$PY3" ] && { echo "找不到 python3，請先安裝（建議 brew install python）"; exit 1; }

echo "==> 建立乾淨 venv 並安裝 py2app / rumps"
rm -rf "$ROOT/.build-venv" "$ROOT/.build"
"$PY3" -m venv "$ROOT/.build-venv"
# shellcheck disable=SC1091
source "$ROOT/.build-venv/bin/activate"
python -m pip install --upgrade pip wheel >/dev/null
python -m pip install py2app rumps >/dev/null

echo "==> 準備建置暫存目錄"
mkdir -p "$ROOT/.build"
cp "$ROOT/src/cc_token_dashboard.py" "$ROOT/.build/"
cp "$ROOT/packaging/app_main.py" "$ROOT/.build/"
cp "$ROOT/packaging/setup.py" "$ROOT/.build/"

echo "==> py2app 打包中（首次較久）"
( cd "$ROOT/.build" && python setup.py py2app >/dev/null )

mkdir -p "$ROOT/dist"
rm -rf "$ROOT/dist/CCTokenDashboard.app"
APP_SRC="$(ls -d "$ROOT/.build/dist/"*.app | head -1)"
cp -R "$APP_SRC" "$ROOT/dist/CCTokenDashboard.app"

echo "==> 放入鬆散腳本副本（供 statusLine 收集器以系統 python3 直接執行）"
# py2app 會把 .py 壓進 zip，無法當 statusLine 命令路徑；額外放一份鬆散檔在
# Contents/Resources/，儀表板「設定收集器」就會指向這份可執行的副本。
cp "$ROOT/src/cc_token_dashboard.py" \
   "$ROOT/dist/CCTokenDashboard.app/Contents/Resources/cc_token_dashboard.py"

echo "==> 製作 .dmg"
rm -f "$ROOT/dist/CCTokenDashboard.dmg"
hdiutil create -volname "CC Token 儀表板" -srcfolder "$ROOT/dist/CCTokenDashboard.app" \
  -ov -format UDZO "$ROOT/dist/CCTokenDashboard.dmg" >/dev/null || echo "（.dmg 略過）"

deactivate || true
echo "✅ 完成："
echo "   $ROOT/dist/CCTokenDashboard.app"
echo "   $ROOT/dist/CCTokenDashboard.dmg"
