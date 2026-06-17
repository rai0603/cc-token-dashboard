# CLAUDE.md — CC Token 儀表板

> 給 Claude Code 的專案啟動協議。請先讀完本檔再動手。
> 原則：**先有證據，才能動手**。每次宣稱「完成」前，先用 `make test` 或實際執行驗證。

## 這是什麼
一個監控「本機所有正在執行的 Claude Code 終端機」token 產出的工具。單一 Python 檔、三種角色：
- `status`  — 給 Claude Code 的 **statusLine 收集器**（讀 stdin 的 JSON，寫準確 token 快照）
- `serve`   — 瀏覽器**全功能儀表板**（KPI + 折線/長條/圈圖 + 各專案明細表）
- `menubar` — macOS **常駐選單列**小工具（rumps；點開可開啟全功能頁）

主程式：`src/cc_token_dashboard.py`（status/serve 純標準函式庫；menubar 才需要 rumps）。

## ⚠️ 關鍵事實（不要修錯方向）
1. **token 準確度只能靠 statusLine，不能靠 ~/.claude/projects 的 JSONL。**
   Claude Code 寫進 conversation JSONL 的 `output_tokens` 多為串流中途值（常是 1），會低估 10～100 倍
   （anthropics/claude-code #22686）。**準確來源**是 statusLine 餵進來的
   `context_window.total_output_tokens / total_input_tokens`（與 API 1:1）。
   → 若有人想「改成直接讀 JSONL 以涵蓋歷史」，必須明白那會犧牲準確度，僅適合做「大概的」歷史值。
2. statusLine 只在「**有工作階段在跑**」時 tick → 這正是「目前在跑的終端機」即時監控的特性，不是 bug。

## 資料流與格式
```
Claude Code (每次狀態更新)
   │  stdin: { session_id, workspace.project_dir, model.display_name,
   │           cost.total_cost_usd, context_window.{total_output_tokens,total_input_tokens,used_percentage} }
   ▼
status 收集器  ──append（單筆 <4KB，POSIX 原子寫，多終端機安全）──▶  events.jsonl
   每筆: {"ts","sid","project","dir","model","out","in","cost","ctx"}
   位置: ~/.claude/token-dashboard/events.jsonl（可用 env CC_TOKEN_DASH_DIR 覆寫）
   ▼
Store（serve / menubar 共用邏輯）
   - 增量讀檔（offset + 殘行緩衝；檔案縮小→重讀）
   - 每個 sid 存「最後累計值」，新值 - 舊值 = delta（clamp >=0）
   - 首見某 sid：只設基準、delta=0（避免把整段歷史灌進某一分鐘）
   - 只累計 ts 為「今天(本地)」的 delta；跨午夜 reset 當日彙整但保留 sess_last
   ▼
/api/stats（JSON）→ 前端 Chart.js 每 3 秒輪詢
```

## 常用指令
```
make test          # 煙霧測試（不需 Claude Code，驗證彙整正確）
make run           # 開瀏覽器儀表板  http://127.0.0.1:8787
make menubar       # 直接跑選單列（需先 pip3 install rumps）
make quick-app     # 產生免編譯 .app → dist/quick/CCTokenDashboard.app
make app           # py2app 自包含 .app + .dmg → dist/
make install-statusline   # 印出要貼到 ~/.claude/settings.json 的設定
make clean
```

## 目前待辦（見 PROGRESS.md）
- [ ] 在 Mac 上跑 `make app`，驗證自包含 .app 能開、選單列出現、能開全功能頁
- [ ] （有 Apple Developer ID 時）codesign + notarytool，做出別人下載不跳警告的版本
- [ ] 選單列加一顆「設定 statusLine 收集器」：安全寫入 ~/.claude/settings.json（先備份、不覆蓋既有）
- [ ] LaunchAgent：開機自動常駐（或用「系統設定→登入項目」）
- [ ] （可選）歷史日切換、5 小時視窗、把 events 落地 SQLite 以利長期查詢

## 守則
- 收集器/伺服器**維持純標準函式庫**；新相依只在 menubar/打包引入。
- 收集器要**極快**且**永不拋例外**到 stdout（statusLine 只讀第一行）。
- 改動 Store 的 delta 邏輯後，務必跑 `make test`（內含斷言）。
- 環境：使用者為 macOS（zsh、Homebrew python）；該機負載偏高，工具要輕量輪詢。
