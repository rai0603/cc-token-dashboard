# PROGRESS

## 已完成
- [x] 主程式三模式：status / serve / menubar（`src/cc_token_dashboard.py`）
- [x] 準確 token 來源改採 statusLine 的 context_window（非 JSONL）
- [x] Store 增量讀檔 + 每 session delta + 今日彙整 + 連續分鐘時間序列
- [x] 前端：KPI、即時折線（多專案/可切區間/累積）、長條、圈圖、各專案明細表、三主題
- [x] 多終端機原子 append 寫入 events.jsonl
- [x] 免編譯 .app 組裝腳本（make_quick_app.sh）
- [x] py2app 自包含建置（build_app.sh / .command）+ .dmg
- [x] 煙霧測試（make test，含彙整斷言）— 通過

## 進行中 / 待辦
- [x] 在 Mac 實跑 `make app`：自包含 .app + .dmg 已產出於 dist/（x86_64，內嵌 Python.framework），open 後選單列進程常駐不崩；內嵌解譯器可跑 serve（2026-06-17 驗）
- [ ] codesign + notarytool（需 Apple Developer ID）
- [ ] 選單列「設定 statusLine 收集器」按鈕（安全寫入 settings.json）
- [ ] 開機常駐（LaunchAgent 或登入項目）
- [ ] （可選）歷史日切換 / 5 小時視窗 / SQLite 落地

## Verified facts（2026-06-17 實測）
- statusLine payload 同時有 `workspace.project_dir`（= 啟動 claude 的目錄，固定）與
  `workspace.current_dir`（= 目前實際工作的資料夾，會跟著 cd/操作變動）。實測:在
  /Users/waterman 啟動的 session，cd 進子目錄後 current_dir 即反映新路徑。
- 收集器已改為**優先用 current_dir**，再用 `project_name_for()` 往上找專案根標記
  （.git/.claude/package.json/...）把子目錄歸回專案本身 → 「家目錄啟動、再請 claude
  進某專案工作」的用法可自動分流，不需 cd 啟動、不需帶環境變數。
- 影響範圍只在 src（statusLine 收集器）；.app 只是顯示器，此修正不需重新打包。
- 既有的歷史 "waterman" 累計不會回溯重新分類（無從得知當時 token 屬哪個專案）。
- 儀表板「設定收集器」原本用 `os.path.abspath(__file__)` 產指令，py2app 下會變成
  zip 內 .pyc 路徑（python3 無法執行）。已修：新增 `DISPLAY_SCRIPT_PATH`，偵測到
  `.app/Contents/` 就改指向 bundle 內鬆散副本；build_app.sh 會 cp 一份
  `src/cc_token_dashboard.py` 到 `Contents/Resources/`。已端到端驗證（bundle 真實
  SCRIPT_PATH = zip/.pyc，DISPLAY = Resources/cc_token_dashboard.py，系統 python3 可執行）。
- 重新打包後的 dist/CCTokenDashboard.app + .dmg 已含上述兩項修正（2026-06-17）。

## 已知限制
- 數字僅在工作階段執行（statusLine tick）時更新；顆粒度依 Claude Code tick 頻率。
- 折線圖需連 cdn.jsdelivr.net 載 Chart.js（離線可改內嵌）。
