#!/bin/bash
# 組出免編譯的 CCTokenDashboard.app（依賴使用者已安裝的 python3 + rumps）
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/dist/quick/CCTokenDashboard.app"
rm -rf "$ROOT/dist/quick"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>CC Token 儀表板</string>
  <key>CFBundleDisplayName</key><string>CC Token 儀表板</string>
  <key>CFBundleIdentifier</key><string>cc.watermansports.tokendashboard</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleSignature</key><string>????</string>
  <key>CFBundleExecutable</key><string>cc-token</string>
  <key>LSUIElement</key><true/>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

printf 'APPL????' > "$APP/Contents/PkgInfo"
cp "$ROOT/src/cc_token_dashboard.py" "$APP/Contents/Resources/cc_token_dashboard.py"

cat > "$APP/Contents/MacOS/cc-token" <<'LAUNCH'
#!/bin/bash
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../Resources/cc_token_dashboard.py"
LOGIN_PY="$(/bin/zsh -lc 'command -v python3' 2>/dev/null)"
[ -z "$LOGIN_PY" ] && LOGIN_PY="$(/bin/bash -lc 'command -v python3' 2>/dev/null)"
CANDIDATES=()
[ -n "$LOGIN_PY" ] && CANDIDATES+=("$LOGIN_PY")
CANDIDATES+=(/opt/homebrew/bin/python3 /usr/local/bin/python3 "$HOME/.pyenv/shims/python3" /usr/bin/python3)
PY=""
for c in "${CANDIDATES[@]}"; do
  if [ -x "$c" ] && "$c" -c 'import rumps' >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  /usr/bin/osascript -e 'display dialog "找不到已安裝 rumps 的 Python。請先在終端機執行一次：pip3 install rumps，再開啟本程式。" with title "CC Token 儀表板" buttons {"好"} default button 1 with icon caution'
  exit 1
fi
exec "$PY" "$SCRIPT" menubar
LAUNCH
chmod +x "$APP/Contents/MacOS/cc-token"

echo "✅ 已產生：$APP"
echo "   把它拖進「應用程式」即可（首次需右鍵→打開 過 Gatekeeper）。"
