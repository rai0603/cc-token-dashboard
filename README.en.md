# CC Token Dashboard

> Live-monitor the token output of **every running Claude Code terminal** on your Mac.
> Lives in the macOS menu bar; open it for per-project breakdowns and a full dashboard with line/bar/doughnut charts.

<p>
  <img alt="platform" src="https://img.shields.io/badge/platform-macOS%2011%2B-black">
  <img alt="python" src="https://img.shields.io/badge/python-3.9%2B-blue">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-green">
</p>

中文版 → [README.md](README.md)

![dashboard](docs/dashboard.png)

---

## What it is

A single-file Python tool that answers one question: **"How many tokens is each of my open Claude Code sessions actually burning right now?"**

It plays three roles (one program, different subcommands):

| Role | Subcommand | Description |
|------|------------|-------------|
| Collector | `status` | A Claude Code **statusLine** — reads JSON from stdin and records an accurate token snapshot |
| Full dashboard | `serve` | Browser page: KPIs + live line chart + bar + doughnut + per-project table |
| Menu bar | `menubar` | macOS menu-bar widget (needs `rumps`); click to open the full page |

Main program: [`src/cc_token_dashboard.py`](src/cc_token_dashboard.py). `status` / `serve` are **pure standard library** with zero external deps; only `menubar` and packaging pull in extras.

---

## Why the numbers are accurate (core design)

The `output_tokens` that Claude Code writes into the conversation JSONL are mostly **mid-stream values** (often `1`), so aggregating them undercounts by 10–100× (see [anthropics/claude-code#22686](https://github.com/anthropics/claude-code/issues/22686)).

This tool **does not read that JSONL**. It uses the **statusLine**: on every status update Claude Code feeds `context_window.total_output_tokens / total_input_tokens` to the statusLine command, and that value matches API billing **1:1** — the accurate source.

> Implication: the statusLine only ticks **while a session is running** → that's exactly the "live monitor of currently-running terminals" behavior, not a bug.

---

## Install

Requirements: macOS 11+, `python3` (Homebrew recommended).

### A. No build (easiest)

```bash
pip3 install rumps          # once
make quick-app              # builds dist/quick/CCTokenDashboard.app
```

Drag the `.app` into Applications; on first launch right-click → "Open" to pass Gatekeeper. Relies on the system `python3` + `rumps`.

### B. Self-contained (no system Python, distributable)

```bash
make app                    # py2app build → dist/CCTokenDashboard.app + .dmg
```

Bundles its own Python.framework; built locally so it isn't quarantined and can be double-clicked. The build also drops a **loose script copy** into `Contents/Resources/` for the collector to use.

### C. Run from source

```bash
make run                    # browser dashboard at http://127.0.0.1:8787
make menubar                # menu-bar app (pip3 install rumps first)
```

---

## Wire up the data source (statusLine collector)

The app only *displays*; tokens are written by the collector to `~/.claude/token-dashboard/events.jsonl`. The two are independent.

Open the dashboard and follow the "set up statusLine collector" panel to merge the JSON into `~/.claude/settings.json` (the command path is pre-filled). Manually:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /path/to/cc-token-dashboard/src/cc_token_dashboard.py status"
  }
}
```

> Already have a custom statusLine? Append `python3 …/cc_token_dashboard.py status` to your existing script to collect at the same time.

Then go back to any Claude Code session and keep working — data starts flowing and the page refreshes every few seconds.

---

## How projects are separated

The collector derives the project from the **current working directory** (`workspace.current_dir`), walking up to find a project-root marker (`.git` / `.claude` / `package.json`, …) so subdirectories map back to the project itself.

So even if you always launch `claude` from your home directory, the moment you ask it to work inside a project, those tokens are **attributed to that project automatically** — no need to `cd` at launch, no env vars.

---

## Common commands

```
make test                smoke test (no Claude Code needed; includes assertions)
make run                 browser dashboard
make menubar             menu-bar app (needs rumps)
make quick-app           no-build .app → dist/quick/
make app                 self-contained .app + .dmg → dist/
make install-statusline  print the settings.json snippet
make clean
```

---

## Data flow

```
Claude Code (every status update)
   │  stdin: { session_id, workspace.{project_dir,current_dir},
   │           model.display_name, cost.total_cost_usd,
   │           context_window.{total_output_tokens,total_input_tokens,used_percentage} }
   ▼
status collector  ── atomic append (<4KB per record, multi-terminal safe) ──▶  events.jsonl
   ▼
Store (shared by serve / menubar): incremental reads, per-session delta, today's totals, per-minute series
   ▼
/api/stats (JSON) → front-end Chart.js polls every 3s
```

---

## Known limitations

- Numbers only update while a session is **actively running** (statusLine tick); granularity follows Claude Code's tick rate.
- The line chart loads Chart.js from a CDN by default (can be inlined for offline use).
- Historical tokens can't be re-classified retroactively (past ticks don't know which project they belonged to).

## Roadmap

- [ ] codesign + notarytool (needs an Apple Developer ID) for a warning-free download
- [ ] Menu-bar "one-click set up statusLine collector" (safe write into settings.json)
- [ ] Auto-start on login (LaunchAgent)
- [ ] History date switching / 5-hour window / SQLite persistence for long-term queries

---

## Contributing

Issues and PRs welcome — please read [CONTRIBUTING.md](CONTRIBUTING.md) first. If you touch the collector's delta logic, always run `make test`.

## License

[MIT](LICENSE) © 2026 陳建文 (Rai)
