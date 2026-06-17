# Changelog

本檔格式依循 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，版本遵循 [SemVer](https://semver.org/lang/zh-TW/)。
This project follows [Keep a Changelog](https://keepachangelog.com/) and [SemVer](https://semver.org/).

## [Unreleased]

## [1.0.0] - 2026-06-17

首個開源版本 / First open-source release.

### Added
- 三角色單檔工具：`status`（statusLine 收集器）/ `serve`（全功能儀表板）/ `menubar`（選單列）。
  Single-file tool with three roles: `status` collector, `serve` dashboard, `menubar` widget.
- 準確 token 來源改採 statusLine 的 `context_window`，避開 conversation JSONL 的低估問題。
  Accurate token source via the statusLine `context_window`, avoiding the JSONL undercount.
- 前端：KPI、即時折線（多專案／可切區間／累積）、長條、圈圖、各專案明細表、三主題。
  Front-end: KPIs, live line/bar/doughnut charts, per-project table, three themes.
- 多終端機原子 append 寫入 `events.jsonl`；Store 增量讀檔 + 每 session delta + 今日彙整。
  Multi-terminal atomic append; incremental Store reads, per-session delta, daily totals.
- 打包：`make quick-app`（免編譯）與 `make app`（py2app 自包含 .app + .dmg）。
  Packaging: `make quick-app` (no build) and `make app` (self-contained .app + .dmg).
- 煙霧測試 `make test`（含彙整斷言）。Smoke test with aggregation assertions.

### Fixed
- 專案分流改用 `workspace.current_dir` 並往上找專案根標記，修正「家目錄啟動時所有
  session 都被歸成同一個專案」的問題。
  Project attribution now uses `workspace.current_dir` + root-marker walk-up, fixing
  the "everything collapses into one project when launched from home" issue.
- 自包含 `.app` 的「設定收集器」指令原本指向 zip 內 `.pyc`（無法執行）；改為指向
  bundle 內鬆散副本，打包時複製到 `Contents/Resources/`。
  The self-contained `.app`'s setup command pointed at a `.pyc` inside a zip (not runnable);
  it now points at a loose copy placed in `Contents/Resources/` during build.

[Unreleased]: https://github.com/rai0603/cc-token-dashboard/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/rai0603/cc-token-dashboard/releases/tag/v1.0.0
