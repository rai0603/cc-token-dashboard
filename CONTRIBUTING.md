# 貢獻指南 / Contributing

感謝你願意參與！本專案刻意維持小而精，請先讀完規範再動手。
Thanks for helping out! This project is intentionally small and focused — please read the rules before you start.

> English version follows the Chinese section below.

---

## 中文

### 開發環境

```bash
git clone https://github.com/rai0603/cc-token-dashboard
cd cc-token-dashboard
make test            # 不需 Claude Code 也能跑，必須全綠
make run             # 本機開儀表板 http://127.0.0.1:8787
```

需求：macOS 11+、Python 3.9+。`menubar` 與打包另需 `pip3 install rumps py2app`。

### 不可妥協的設計守則

1. **`status` / `serve` 維持純標準函式庫**：零外部相依。新套件只能在 `menubar` 或打包流程引入。
2. **收集器要極快、且永不拋例外到 stdout**：statusLine 只讀第一行，任何錯誤都要被 `try/except` 吞掉並以單行訊息呈現，絕不能拖垮使用者的狀態列。
3. **改動 Store 的 delta 邏輯後，務必跑 `make test`**（內含彙整斷言）。
4. **準確度只能靠 statusLine**：請勿改成直接讀 `~/.claude/projects` 的 conversation JSONL 來統計 token——那會低估 10～100 倍（見 README「為什麼準」）。
5. **先有證據才動手**：修 bug 請附最小重現或 failing test；別只修症狀。

### 送 PR 流程

1. 從 `main` 開分支：`git checkout -b fix/簡述` 或 `feat/簡述`。
2. 改動範圍聚焦，避免順手重構（scope 外的留 TODO）。
3. `make test` 全綠；若改到打包，請實跑 `make app` 確認 `.app` 能開。
4. commit 訊息建議格式：
   - `fix: <症狀> — root cause: <根因>`
   - `feat: <新增能力>`
   - `docs:` / `refactor:` / `chore:`
5. 開 PR，描述「改了什麼、為什麼、怎麼驗證」。

### 回報 issue

請附：macOS 版本、Python 版本、重現步驟、預期 vs 實際。涉及收集器的問題，附上 `~/.claude/token-dashboard/events.jsonl` 的相關片段（**記得移除敏感路徑/專案名**）會很有幫助。

---

## English

### Dev setup

```bash
git clone https://github.com/rai0603/cc-token-dashboard
cd cc-token-dashboard
make test            # runs without Claude Code; must stay green
make run             # local dashboard at http://127.0.0.1:8787
```

Requirements: macOS 11+, Python 3.9+. `menubar` and packaging also need `pip3 install rumps py2app`.

### Non-negotiable design rules

1. **Keep `status` / `serve` pure standard library** — zero external deps. New packages may only enter via `menubar` or the packaging path.
2. **The collector must be fast and never raise to stdout.** statusLine reads only the first line; wrap everything in `try/except` and degrade to a one-line message. It must never break the user's status bar.
3. **Run `make test` after any change to the Store's delta logic** (it ships with aggregation assertions).
4. **Accuracy depends on statusLine.** Do not switch to reading `~/.claude/projects` conversation JSONL for token counts — it undercounts by 10–100× (see "Why the numbers are accurate" in the README).
5. **Evidence first.** For bug fixes, include a minimal repro or a failing test; fix the root cause, not the symptom.

### Pull request flow

1. Branch from `main`: `git checkout -b fix/short-desc` or `feat/short-desc`.
2. Keep changes focused; leave a TODO instead of opportunistic refactors.
3. `make test` green; if you touch packaging, actually run `make app` and confirm the `.app` opens.
4. Suggested commit format:
   - `fix: <symptom> — root cause: <cause>`
   - `feat: <capability>`
   - `docs:` / `refactor:` / `chore:`
5. Open the PR describing what changed, why, and how you verified it.

### Filing issues

Include: macOS version, Python version, repro steps, expected vs actual. For collector issues, a relevant snippet of `~/.claude/token-dashboard/events.jsonl` helps a lot — **strip any sensitive paths/project names first**.
