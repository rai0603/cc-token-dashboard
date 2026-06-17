#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code Token 即時儀表板（單一檔案，純 Python 標準函式庫，零安裝）

一個檔案，兩個角色：

  1) 收集器（給 Claude Code 的 statusLine 用）
        python3 cc_token_dashboard.py status
     在 ~/.claude/settings.json 把 statusLine.command 指到這支程式的 status 子指令。
     Claude Code 會在每次狀態更新時，把含 context_window 的 JSON 從 stdin 餵進來；
     本程式擷取「準確的」累計 token 快照寫進 events.jsonl，同時印出一行狀態列。
     多個終端機同時跑各自的工作階段都會各自寫入同一個 events.jsonl。

  2) 儀表板伺服器（預設）
        python3 cc_token_dashboard.py                 # 等同 serve
        python3 cc_token_dashboard.py serve --port 8787
     讀 events.jsonl，提供 /api/stats，瀏覽器即時顯示：
       - 本日產出 / 輸入 token、花費、進行中工作階段
       - 各專案產出長條圖、產出占比圈圖
       - 各專案產出「即時」折線圖（多專案同一張圖、每分鐘或累積）

為什麼不直接讀 ~/.claude/projects 的 JSONL？
  Claude Code 寫進 JSONL 的 output_tokens 多半只是串流中途值（常常是 1），會嚴重低估
  （社群實測差 10～100 倍，見 anthropics/claude-code #22686）。statusLine 收到的
  context_window.total_output_tokens 才是與 API 1:1 的準確累計值，所以本工具走 statusLine。
"""

import argparse
import json
import os
import sys
import threading
import webbrowser
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ---------------------------------------------------------------------------
# 路徑與全域設定
# ---------------------------------------------------------------------------
SCRIPT_PATH = os.path.abspath(__file__)


def _display_script_path() -> str:
    """給使用者貼進 ~/.claude/settings.json 的腳本路徑。
    py2app 打包後 __file__ 會落在 zip 內（python3 無法直接執行），此時改指向
    app bundle 內的鬆散副本 Contents/Resources/cc_token_dashboard.py（status 模式
    純標準庫，系統 python3 即可執行）。開發時則維持原始鬆散檔路徑。"""
    p = SCRIPT_PATH
    marker = ".app/Contents/"
    idx = p.find(marker)
    if idx != -1:
        bundle = p[:idx + len(".app")]
        return os.path.join(bundle, "Contents", "Resources",
                            "cc_token_dashboard.py")
    return p


DISPLAY_SCRIPT_PATH = _display_script_path()
DATA_DIR = Path(os.environ.get(
    "CC_TOKEN_DASH_DIR",
    str(Path.home() / ".claude" / "token-dashboard"),
))
EVENTS = DATA_DIR / "events.jsonl"
POLL_MS = 3000          # 前端輪詢間隔（毫秒），可由 --interval 覆寫
ACTIVE_WINDOW_SEC = 90  # 最後一次 tick 在這個秒數內，視為「進行中」

# 從家目錄啟動 claude、再請它進某專案工作時，project_dir 永遠是家目錄，
# 但 current_dir 會跟著實際工作資料夾走。於是改抓 current_dir，再往上找
# 「專案根標記」把子目錄（如 .../專案/dist）歸回專案本身。
PROJECT_MARKERS = (".git", ".claude", "package.json", "pyproject.toml",
                   "Cargo.toml", "go.mod", "deno.json", "Makefile")


def project_name_for(work_dir: str) -> str:
    """從工作目錄推得專案名：往上找最近的專案根標記，取其資料夾名。
    找不到標記就退回該目錄本身的名字。永不拋例外、純 os.path（快）。"""
    try:
        cur = os.path.abspath(work_dir) if work_dir else ""
        if not cur:
            return "unknown"
        while cur and cur != os.path.dirname(cur):   # 走到檔案系統根為止
            for m in PROJECT_MARKERS:
                if os.path.exists(os.path.join(cur, m)):
                    return os.path.basename(cur) or "unknown"
            cur = os.path.dirname(cur)
        return os.path.basename(os.path.abspath(work_dir).rstrip("/")) or "unknown"
    except Exception:
        return os.path.basename((work_dir or "").rstrip("/")) or "unknown"


# ===========================================================================
# 角色一：statusLine 收集器
# ===========================================================================
def run_collector() -> None:
    """讀 stdin 的 statusLine JSON，記錄準確 token 快照，印出一行狀態列。"""
    raw = sys.stdin.read()
    line = "Claude Code"
    try:
        d = json.loads(raw) if raw.strip() else {}
    except Exception:
        d = {}

    try:
        cw = d.get("context_window") or {}
        cost = d.get("cost") or {}
        ws = d.get("workspace") or {}
        model = (d.get("model") or {}).get("display_name") \
            or (d.get("model") or {}).get("id") or "?"
        # 優先用「目前所在資料夾」(current_dir)，才能在「家目錄啟動 → 進專案工作」
        # 的用法下正確分流；退而求其次才用啟動目錄 project_dir。
        proj_dir = ws.get("current_dir") or d.get("cwd") \
            or ws.get("project_dir") or ""
        project = project_name_for(proj_dir)
        out = int(cw.get("total_output_tokens") or 0)
        inp = int(cw.get("total_input_tokens") or 0)
        usd = float(cost.get("total_cost_usd") or 0.0)
        sid = d.get("session_id") or "?"
        ctx = cw.get("used_percentage")

        rec = {
            "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "sid": sid,
            "project": project,
            "dir": proj_dir,
            "model": model,
            "out": out,
            "in": inp,
            "cost": round(usd, 6),
        }
        if ctx is not None:
            try:
                rec["ctx"] = round(float(ctx), 1)
            except Exception:
                pass

        # 只在拿得到 context_window 時才記錄（避免剛開啟、還沒有 token 資料的空 tick）
        if cw:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            payload = (json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8")
            # 單一 os.write，<4KB 在 POSIX 上是原子操作 → 多終端機同時寫不會交錯
            fd = os.open(str(EVENTS), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            try:
                os.write(fd, payload)
            finally:
                os.close(fd)

        ctx_s = f"{rec['ctx']}%" if "ctx" in rec else "?"
        line = (f"\U0001F4C2 {project}   \U0001F916 {model}   "
                f"\U0001F4AD {ctx_s} ctx   "
                f"\U0001F9E0 {out:,} out / {inp:,} in   "
                f"\U0001F4B8 ${usd:.2f}")
    except Exception as e:
        # 收集器絕不能拖垮狀態列；出錯就印簡短訊息
        line = f"Claude Code  (token-dashboard collector error: {e})"

    sys.stdout.write(line)  # statusLine 只讀 stdout 第一行


# ===========================================================================
# 角色二：彙整與伺服器
# ===========================================================================
class Store:
    """增量讀取 events.jsonl，依工作階段算 delta，彙整成「今日」統計與時間序列。"""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.offset = 0
        self.buf = b""
        self.sess_last = {}   # sid -> {"out","in","cost","ts"}（最後看到的累計值，跨日保留）
        self.day = self._today()
        self._reset_day()

    @staticmethod
    def _today() -> str:
        return datetime.now().astimezone().date().isoformat()

    def _reset_day(self) -> None:
        self.proj_out = {}        # project -> 今日產出 token
        self.proj_in = {}         # project -> 今日輸入 token
        self.proj_cost = {}       # project -> 今日花費 USD
        self.proj_sessions = {}   # project -> set(sid)
        self.series = {}          # project -> {"HH:MM": 該分鐘產出 token}
        self.model_out = {}       # model -> 今日產出 token
        self.total_out = 0
        self.total_in = 0
        self.total_cost = 0.0
        self.first_minute = None  # 今日第一筆活動的 "HH:MM"

    def _ensure_day(self) -> None:
        t = self._today()
        if t != self.day:
            self.day = t
            self._reset_day()  # sess_last 保留，跨日 delta 仍能正確接續

    def poll(self) -> None:
        with self.lock:
            self._ensure_day()
            self._read_new()

    def _read_new(self) -> None:
        try:
            size = EVENTS.stat().st_size
        except FileNotFoundError:
            return
        if size < self.offset:                 # 檔案被截斷／輪替 → 整個重讀
            self.offset, self.buf = 0, b""
            self.sess_last = {}
            self._reset_day()
        if size == self.offset:
            return
        with open(EVENTS, "rb") as f:
            f.seek(self.offset)
            chunk = f.read()
            self.offset = f.tell()
        self.buf += chunk
        parts = self.buf.split(b"\n")
        self.buf = parts.pop()                 # 最後一段可能是半行，留到下次
        for raw in parts:
            if not raw.strip():
                continue
            try:
                rec = json.loads(raw.decode("utf-8"))
            except Exception:
                continue
            self._ingest(rec)

    def _ingest(self, rec: dict) -> None:
        sid = rec.get("sid") or "?"
        try:
            ts = datetime.fromisoformat(rec["ts"]).astimezone()
        except Exception:
            return
        out = int(rec.get("out") or 0)
        inp = int(rec.get("in") or 0)
        cost = float(rec.get("cost") or 0.0)
        project = rec.get("project") or "unknown"
        model = rec.get("model") or "?"

        prev = self.sess_last.get(sid)
        if prev is None:
            d_out = d_in = 0          # 首見此工作階段：設基準，不灌入時間軸以免暴衝
            d_cost = 0.0
        else:
            d_out = max(0, out - prev["out"])
            d_in = max(0, inp - prev["in"])
            d_cost = max(0.0, cost - prev["cost"])
        self.sess_last[sid] = {"out": out, "in": inp, "cost": cost, "ts": ts}

        if ts.date().isoformat() != self.day:   # 只累計「今天」發生的增量
            return

        # 即使本次無增量，也標記該專案／工作階段今日活躍過
        self.proj_sessions.setdefault(project, set()).add(sid)
        if d_out == 0 and d_in == 0 and d_cost == 0.0:
            return

        self.total_out += d_out
        self.total_in += d_in
        self.total_cost += d_cost
        self.proj_out[project] = self.proj_out.get(project, 0) + d_out
        self.proj_in[project] = self.proj_in.get(project, 0) + d_in
        self.proj_cost[project] = self.proj_cost.get(project, 0.0) + d_cost
        self.model_out[model] = self.model_out.get(model, 0) + d_out

        minute = ts.strftime("%H:%M")
        bucket = self.series.setdefault(project, {})
        bucket[minute] = bucket.get(minute, 0) + d_out
        if self.first_minute is None or minute < self.first_minute:
            self.first_minute = minute

    def snapshot(self) -> dict:
        with self.lock:
            now = datetime.now().astimezone()

            # 連續分鐘軸：今日第一筆活動 → 現在（前端再依區間切片）
            labels = []
            if self.first_minute:
                sh, sm = map(int, self.first_minute.split(":"))
                cur = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
                end = now.replace(second=0, microsecond=0)
                steps = 0
                while cur <= end and steps <= 1500:   # 上限保護（約 25 小時）
                    labels.append(cur.strftime("%H:%M"))
                    cur += timedelta(minutes=1)
                    steps += 1

            series = {p: [m.get(lb, 0) for lb in labels] for p, m in self.series.items()}

            active = 0
            for v in self.sess_last.values():
                if (now - v["ts"]).total_seconds() <= ACTIVE_WINDOW_SEC:
                    active += 1

            projects = sorted(
                (
                    {
                        "name": p,
                        "out": self.proj_out.get(p, 0),
                        "in": self.proj_in.get(p, 0),
                        "cost": round(self.proj_cost.get(p, 0.0), 4),
                        "sessions": len(self.proj_sessions.get(p, set())),
                    }
                    for p in (set(self.proj_out) | set(self.proj_sessions))
                ),
                key=lambda x: x["out"],
                reverse=True,
            )

            return {
                "day": self.day,
                "updated": now.strftime("%H:%M:%S"),
                "has_data": bool(self.sess_last),
                "totals": {
                    "out": self.total_out,
                    "in": self.total_in,
                    "cost": round(self.total_cost, 4),
                },
                "active_sessions": active,
                "active_projects": len([p for p, v in self.proj_out.items() if v > 0]) or len(self.proj_sessions),
                "projects": projects,
                "models": [
                    {"name": k, "out": v}
                    for k, v in sorted(self.model_out.items(), key=lambda x: -x[1])
                ],
                "series": {"labels": labels, "projects": series},
            }


STORE = Store()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_a):       # 安靜，不要每次請求都印 log
        return

    def _send(self, body: bytes, ctype: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/stats"):
            STORE.poll()
            body = json.dumps(STORE.snapshot(), ensure_ascii=False).encode("utf-8")
            self._send(body, "application/json; charset=utf-8")
        elif self.path == "/" or self.path.startswith("/index"):
            html = (HTML
                    .replace("__POLL_MS__", str(POLL_MS))
                    .replace("__SCRIPT_PATH__", DISPLAY_SCRIPT_PATH)
                    .replace("__EVENTS_PATH__", str(EVENTS)))
            self._send(html.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self.send_response(404)
            self.end_headers()


def run_server(port: int, do_open: bool) -> None:
    STORE.poll()  # 啟動先把既有資料讀進來
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Claude Code Token 儀表板：{url}")
    print(f"資料來源：{EVENTS}")
    if not EVENTS.exists():
        print("（尚無資料：請先依儀表板畫面指示設定 statusLine 收集器，"
              "再到任一 Claude Code 工作階段操作）")
    if do_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n結束。")


# ===========================================================================
# 角色三：常駐選單列小工具（macOS，需 pip3 install rumps）
# ===========================================================================
def compact(n) -> str:
    """把大數字縮短成選單列好看的長度：1234 -> 1.2k，1200000 -> 1.2M。"""
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1_000:.0f}k"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


_server_thread = None


def ensure_server(port: int) -> None:
    """在背景啟動全功能儀表板伺服器（只會啟動一次；已佔用則略過）。"""
    global _server_thread
    if _server_thread and _server_thread.is_alive():
        return

    def _run():
        try:
            STORE.poll()
            ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
        except OSError:
            pass  # 連接埠可能已被另一個 serve 佔用，沒關係

    _server_thread = threading.Thread(target=_run, daemon=True)
    _server_thread.start()


def run_menubar(port: int, interval: int) -> None:
    """常駐 macOS 選單列：顯示本日產出，點開有明細與『開啟完整儀表板』。"""
    try:
        import rumps
    except ImportError:
        sys.stderr.write(
            "選單列模式需要 rumps（macOS）。請先安裝：\n"
            "    pip3 install rumps\n"
            "然後再執行： python3 "
            + os.path.basename(SCRIPT_PATH)
            + " menubar\n"
        )
        sys.exit(1)

    store = Store()  # 直接讀 events.jsonl，選單列本身不需要伺服器

    class App(rumps.App):
        def __init__(self):
            super().__init__("CC Token", title="CC …", quit_button="結束")
            self.mi_out = rumps.MenuItem("本日產出：—")
            self.mi_in = rumps.MenuItem("本日輸入：—")
            self.mi_cost = rumps.MenuItem("本日花費：—")
            self.mi_active = rumps.MenuItem("進行中：—")
            self.mi_updated = rumps.MenuItem("更新：—")
            self.hdr = rumps.MenuItem("── 各專案（本日產出）──")
            self.proj_items = [rumps.MenuItem("—") for _ in range(8)]
            self.menu = [
                self.mi_out, self.mi_in, self.mi_cost, self.mi_active, self.mi_updated,
                None,
                self.hdr, *self.proj_items,
                None,
                rumps.MenuItem("開啟完整儀表板", callback=self.open_full),
                rumps.MenuItem("立即重新整理", callback=self.manual_refresh),
            ]
            self._tick(None)  # 先更新一次，避免顯示「—」
            self._timer = rumps.Timer(self._tick, max(1, interval))
            self._timer.start()

        def _tick(self, _):
            try:
                store.poll()
                snap = store.snapshot()
            except Exception:
                return
            t = snap["totals"]
            active = snap["active_sessions"]
            self.title = f"{'🟢' if active > 0 else '⚪️'} {compact(t['out'])}"
            if snap["has_data"]:
                self.mi_out.title = f"本日產出：{t['out']:,} tokens"
            else:
                self.mi_out.title = "本日產出：尚無資料（請設定 statusLine）"
            self.mi_in.title = f"本日輸入：{t['in']:,}"
            self.mi_cost.title = f"本日花費：${t['cost']:.2f}"
            self.mi_active.title = f"進行中：{active} 工作階段 / {snap['active_projects']} 專案"
            self.mi_updated.title = f"更新：{snap['updated']}"
            projs = snap["projects"][:len(self.proj_items)]
            for i, item in enumerate(self.proj_items):
                if i < len(projs):
                    p = projs[i]
                    item.title = f"{p['name']}　{p['out']:,}"
                else:
                    item.title = "—"

        def open_full(self, _):
            ensure_server(port)
            import webbrowser as _wb
            _wb.open(f"http://127.0.0.1:{port}/")

        def manual_refresh(self, _):
            self._tick(None)

    App().run()


def main() -> None:
    global POLL_MS
    ap = argparse.ArgumentParser(description="Claude Code Token 即時儀表板")
    sub = ap.add_subparsers(dest="cmd")
    sp = sub.add_parser("serve", help="啟動儀表板（預設）")
    sp.add_argument("--port", type=int, default=8787)
    sp.add_argument("--interval", type=int, default=3, help="前端輪詢秒數（預設 3）")
    sp.add_argument("--no-open", action="store_true", help="不要自動開瀏覽器")
    sub.add_parser("status", help="作為 Claude Code statusLine 收集器（讀 stdin）")
    mp = sub.add_parser("menubar", help="常駐 macOS 選單列小工具（需 pip3 install rumps）")
    mp.add_argument("--port", type=int, default=8787, help="『開啟完整儀表板』使用的連接埠")
    mp.add_argument("--interval", type=int, default=3, help="選單列更新秒數（預設 3）")
    args = ap.parse_args()

    if args.cmd == "status":
        run_collector()
        return
    if args.cmd == "menubar":
        run_menubar(getattr(args, "port", 8787), getattr(args, "interval", 3))
        return
    POLL_MS = max(1, getattr(args, "interval", 3)) * 1000
    run_server(getattr(args, "port", 8787), not getattr(args, "no_open", False))


# ===========================================================================
# 前端（單頁；Chart.js 由 CDN 載入）
# ===========================================================================
HTML = r"""<!doctype html>
<html lang="zh-Hant" data-theme="terminal">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Code · Token 儀表板</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
  :root, [data-theme="terminal"]{
    --bg:#0b0f14; --panel:#121a23; --border:#1f2b38; --text:#d7e3ef; --muted:#7e90a2;
    --accent:#39d98a; --grid:#1b2735;
    --shadow:0 1px 0 rgba(255,255,255,.03), 0 10px 30px rgba(0,0,0,.45);
    --font: ui-monospace, SFMono-Regular, Menlo, "Cascadia Code", Consolas, monospace;
  }
  [data-theme="warm"]{
    --bg:#f3ebdf; --panel:#fbf6ee; --border:#e3d6c4; --text:#3a332b; --muted:#8a7d6c;
    --accent:#c6624a; --grid:#e7dccb;
    --shadow:0 1px 0 rgba(255,255,255,.5), 0 12px 30px rgba(120,90,50,.12);
    --font:"Noto Sans CJK TC","PingFang TC",-apple-system,system-ui,sans-serif;
  }
  [data-theme="light"]{
    --bg:#eef2f7; --panel:#ffffff; --border:#e2e8f0; --text:#0f172a; --muted:#64748b;
    --accent:#2563eb; --grid:#e8eef5;
    --shadow:0 1px 2px rgba(0,0,0,.04), 0 12px 28px rgba(2,6,23,.06);
    --font:-apple-system, system-ui, "Noto Sans CJK TC", sans-serif;
  }
  *{box-sizing:border-box}
  html,body{margin:0}
  body{background:var(--bg); color:var(--text); font-family:var(--font);
       padding:18px 20px 40px; -webkit-font-smoothing:antialiased;}
  header{display:flex; align-items:center; gap:16px; flex-wrap:wrap; margin-bottom:16px;}
  .brand{font-size:17px; font-weight:700; letter-spacing:.3px; display:flex; align-items:center; gap:9px;}
  .dot{width:9px; height:9px; border-radius:50%; background:#e0556b; transition:background .3s;
       box-shadow:0 0 0 0 rgba(57,217,138,.5);}
  .dot.on{background:var(--accent); animation:pulse 2s infinite;}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(57,217,138,.45)}70%{box-shadow:0 0 0 7px rgba(57,217,138,0)}100%{box-shadow:0 0 0 0 rgba(57,217,138,0)}}
  .meta{color:var(--muted); font-size:12.5px; display:flex; gap:14px;}
  .controls{margin-left:auto; display:flex; gap:14px; align-items:center; flex-wrap:wrap; font-size:12.5px; color:var(--muted);}
  .controls label{display:flex; gap:6px; align-items:center;}
  select, .controls input{background:var(--panel); color:var(--text); border:1px solid var(--border);
          border-radius:8px; padding:5px 8px; font-family:inherit; font-size:12.5px;}
  .chk{cursor:pointer; user-select:none;}
  .kpis{display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:16px;}
  .card{background:var(--panel); border:1px solid var(--border); border-radius:14px;
        padding:15px 17px; box-shadow:var(--shadow);}
  .card .k{font-size:12px; color:var(--muted); letter-spacing:.4px;}
  .card .v{font-size:30px; font-weight:700; margin-top:7px; line-height:1; font-variant-numeric:tabular-nums;}
  .card .s{font-size:11.5px; color:var(--muted); margin-top:6px;}
  .card .v .unit{font-size:14px; color:var(--muted); font-weight:600; margin-left:3px;}
  .panel{background:var(--panel); border:1px solid var(--border); border-radius:14px;
         padding:14px 16px 16px; box-shadow:var(--shadow);}
  .panel.wide{margin-bottom:16px;}
  .phead{display:flex; align-items:baseline; gap:10px; margin-bottom:8px;}
  .phead h3{margin:0; font-size:14px; font-weight:700;}
  .hint{color:var(--muted); font-size:11.5px;}
  .canvas-wrap{position:relative; width:100%;}
  .wide .canvas-wrap{height:320px;}
  .row2{display:grid; grid-template-columns:1.35fr 1fr; gap:16px;}
  .row2 .canvas-wrap{height:300px;}
  .empty{margin:18px 0; background:var(--panel); border:1px solid var(--border);
         border-radius:14px; padding:20px 22px; box-shadow:var(--shadow);}
  .empty h3{margin:0 0 10px;}
  .empty ol{margin:8px 0 0; padding-left:20px; line-height:1.85;}
  .empty code, pre{font-family:ui-monospace,Menlo,Consolas,monospace;}
  pre{background:rgba(127,144,162,.12); border:1px solid var(--border); border-radius:10px;
      padding:12px 14px; overflow:auto; font-size:12.5px; margin:8px 0;}
  .warn{background:#e0556b; color:#fff; padding:10px 14px; border-radius:10px; margin-bottom:14px; font-size:13px;}
  .hidden{display:none !important;}
  .ptable{width:100%; border-collapse:collapse; font-size:13px;}
  .ptable th,.ptable td{padding:9px 10px; border-bottom:1px solid var(--border); text-align:left; white-space:nowrap;}
  .ptable th{color:var(--muted); font-weight:600; font-size:11px; letter-spacing:.5px;}
  .ptable td.num,.ptable th.num{text-align:right; font-variant-numeric:tabular-nums;}
  .ptable tbody tr:hover{background:rgba(127,144,162,.08);}
  .pname{display:flex; align-items:center; gap:8px;}
  .swatch{width:10px; height:10px; border-radius:3px; display:inline-block; flex:0 0 auto;}
  @media (max-width:880px){ .kpis{grid-template-columns:repeat(2,1fr);} .row2{grid-template-columns:1fr;} }
</style>
</head>
<body>
  <header>
    <div class="brand"><span class="dot" id="live"></span> Claude Code · Token 儀表板</div>
    <div class="meta"><span id="day">今日 —</span><span id="updated">更新 —</span></div>
    <div class="controls">
      <label>主題
        <select id="theme">
          <option value="terminal">終端機</option>
          <option value="warm">暖色</option>
          <option value="light">淺色</option>
        </select>
      </label>
      <label>區間
        <select id="window">
          <option value="30">30 分</option>
          <option value="60" selected>1 小時</option>
          <option value="180">3 小時</option>
          <option value="0">今日</option>
        </select>
      </label>
      <label class="chk"><input type="checkbox" id="cumulative"> 累積</label>
    </div>
  </header>

  <section class="kpis">
    <div class="card"><div class="k">本日產出 TOKENS</div><div class="v" id="k_out">—</div><div class="s">所有專案 · 所有終端機</div></div>
    <div class="card"><div class="k">本日輸入 TOKENS</div><div class="v" id="k_in">—</div><div class="s">含 cache，僅供參考</div></div>
    <div class="card"><div class="k">本日花費</div><div class="v" id="k_cost">—</div><div class="s">Claude Code 估算（USD）</div></div>
    <div class="card"><div class="k">進行中</div><div class="v" id="k_active">—</div><div class="s">工作階段 / 今日專案數</div></div>
  </section>

  <section class="panel wide">
    <div class="phead"><h3>各專案產出（即時）</h3><span class="hint" id="line_hint"></span></div>
    <div class="canvas-wrap"><canvas id="lineChart"></canvas></div>
  </section>

  <div class="row2">
    <section class="panel">
      <div class="phead"><h3>各專案本日產出</h3></div>
      <div class="canvas-wrap"><canvas id="barChart"></canvas></div>
    </section>
    <section class="panel">
      <div class="phead"><h3>產出占比</h3></div>
      <div class="canvas-wrap"><canvas id="doughnutChart"></canvas></div>
    </section>
  </div>

  <section class="panel" style="margin-top:16px;">
    <div class="phead"><h3>各專案明細</h3><span class="hint">本日累計 · 含 cache 的輸入僅供參考</span></div>
    <div style="overflow:auto;">
      <table class="ptable">
        <thead><tr>
          <th>專案</th><th class="num">產出</th><th class="num">輸入</th>
          <th class="num">花費</th><th class="num">工作階段</th>
        </tr></thead>
        <tbody id="ptbody"></tbody>
      </table>
    </div>
  </section>

  <div id="empty" class="empty hidden">
    <h3>尚未收到資料 — 設定 statusLine 收集器（一次性）</h3>
    <p>把這支程式設成 Claude Code 的 statusLine，token 資料就會開始進來：</p>
    <ol>
      <li>編輯 <code>~/.claude/settings.json</code>，加入（或合併）以下設定：
        <pre id="cfg"></pre>
      </li>
      <li>重新啟動／回到任一 Claude Code 工作階段並開始操作。</li>
      <li>本頁每數秒會自動更新；資料寫在 <code id="evp"></code>。</li>
    </ol>
    <p class="hint">提示：若你已有自訂 statusLine，請改用此設定，或讓你原本的腳本最後加一行
      <code>python3 __SCRIPT_PATH__ status</code> 來同時收集。</p>
  </div>

<script>
const POLL_MS = __POLL_MS__;
const $ = (s) => document.querySelector(s);
const nf = new Intl.NumberFormat('en-US');
const root = document.documentElement;
const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => (
  {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// 設定區塊填上真實路徑
$('#cfg').textContent =
'{\n' +
'  "statusLine": {\n' +
'    "type": "command",\n' +
'    "command": "python3 __SCRIPT_PATH__ status"\n' +
'  }\n' +
'}';
$('#evp').textContent = "__EVENTS_PATH__";

// 主題
const themeSel = $('#theme');
themeSel.value = localStorage.getItem('cc_theme') || 'terminal';
root.setAttribute('data-theme', themeSel.value);
themeSel.onchange = () => {
  root.setAttribute('data-theme', themeSel.value);
  localStorage.setItem('cc_theme', themeSel.value);
  restyleCharts();
};

const cssvar = (n) => getComputedStyle(root).getPropertyValue(n).trim();
const tickColor = () => cssvar('--muted');
const gridColor = () => cssvar('--grid');

// 由專案名稱算出穩定顏色（三張圖共用）
function projColor(name){
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return `hsl(${h % 360} 68% 58%)`;
}

let lineChart, barChart, doughnutChart;

function initCharts(){
  lineChart = new Chart($('#lineChart'), {
    type:'line',
    data:{ labels:[], datasets:[] },
    options:{
      responsive:true, maintainAspectRatio:false, animation:false,
      interaction:{ mode:'index', intersect:false },
      plugins:{ legend:{ labels:{ color:tickColor(), boxWidth:12, usePointStyle:true } } },
      scales:{
        x:{ grid:{ color:gridColor() }, ticks:{ color:tickColor(), maxRotation:0, autoSkip:true, maxTicksLimit:12 } },
        y:{ grid:{ color:gridColor() }, ticks:{ color:tickColor() }, beginAtZero:true }
      }
    }
  });
  barChart = new Chart($('#barChart'), {
    type:'bar',
    data:{ labels:[], datasets:[{ data:[], backgroundColor:[], borderRadius:6 }] },
    options:{
      responsive:true, maintainAspectRatio:false, animation:false,
      plugins:{ legend:{ display:false } },
      scales:{
        x:{ grid:{ display:false }, ticks:{ color:tickColor(), autoSkip:false, maxRotation:35, minRotation:0 } },
        y:{ grid:{ color:gridColor() }, ticks:{ color:tickColor() }, beginAtZero:true }
      }
    }
  });
  doughnutChart = new Chart($('#doughnutChart'), {
    type:'doughnut',
    data:{ labels:[], datasets:[{ data:[], backgroundColor:[], borderWidth:0 }] },
    options:{
      responsive:true, maintainAspectRatio:false, animation:false, cutout:'58%',
      plugins:{ legend:{ position:'right', labels:{ color:tickColor(), boxWidth:12, usePointStyle:true } } }
    }
  });
}

function restyleCharts(){
  for (const ch of [lineChart, barChart, doughnutChart]){
    if (!ch) continue;
    const sc = ch.options.scales || {};
    for (const ax of ['x','y']){
      if (sc[ax]){
        if (sc[ax].grid && sc[ax].grid.color !== undefined) sc[ax].grid.color = gridColor();
        if (sc[ax].ticks) sc[ax].ticks.color = tickColor();
      }
    }
    const lg = ch.options.plugins && ch.options.plugins.legend;
    if (lg && lg.labels) lg.labels.color = tickColor();
    ch.update('none');
  }
}

function sliceRange(len, n){
  if (!n || n <= 0 || len <= n) return [0, len];
  return [len - n, len];
}
function cumulate(arr){ let s = 0; return arr.map(v => (s += v)); }

async function tick(){
  let data;
  try {
    const r = await fetch('/api/stats', { cache:'no-store' });
    data = await r.json();
  } catch (e) {
    $('#live').classList.remove('on');
    return;
  }
  $('#live').classList.add('on');
  $('#day').textContent = '今日 ' + (data.day || '—');
  $('#updated').textContent = '更新 ' + (data.updated || '—');
  $('#empty').classList.toggle('hidden', !!data.has_data);

  $('#k_out').textContent = nf.format(data.totals.out);
  $('#k_in').textContent = nf.format(data.totals.in);
  $('#k_cost').innerHTML = '<span class="unit">$</span>' + (data.totals.cost || 0).toFixed(2);
  $('#k_active').textContent = data.active_sessions + ' / ' + data.active_projects;

  // 折線圖：每個專案一條線
  const winN = parseInt($('#window').value, 10);
  const cum = $('#cumulative').checked;
  const allLabels = data.series.labels || [];
  const [a, b] = sliceRange(allLabels.length, winN);
  const labels = allLabels.slice(a, b);
  const projs = data.series.projects || {};
  const names = Object.keys(projs).sort();
  lineChart.data.labels = labels;
  lineChart.data.datasets = names.map((n) => {
    let arr = (projs[n] || []).slice(a, b);
    if (cum) arr = cumulate(arr);
    const col = projColor(n);
    return { label:n, data:arr, borderColor:col, backgroundColor:col,
             borderWidth:2, pointRadius:0, tension:.25, fill:false };
  });
  $('#line_hint').textContent = (cum ? '累積' : '每分鐘') + ' · ' + names.length + ' 專案';
  lineChart.update('none');

  // 長條圖 + 圈圖：前 12 大專案
  const top = data.projects.slice(0, 12);
  const tn = top.map((p) => p.name);
  const tv = top.map((p) => p.out);
  const tc = top.map((p) => projColor(p.name));
  barChart.data.labels = tn;
  barChart.data.datasets[0].data = tv;
  barChart.data.datasets[0].backgroundColor = tc;
  barChart.update('none');
  doughnutChart.data.labels = tn;
  doughnutChart.data.datasets[0].data = tv;
  doughnutChart.data.datasets[0].backgroundColor = tc;
  doughnutChart.update('none');

  // 各專案明細表
  const tb = $('#ptbody');
  tb.innerHTML = (data.projects || []).map((p) => {
    const c = projColor(p.name);
    return '<tr>'
      + '<td><span class="pname"><span class="swatch" style="background:' + c + '"></span>'
      + escapeHtml(p.name) + '</span></td>'
      + '<td class="num">' + nf.format(p.out) + '</td>'
      + '<td class="num">' + nf.format(p.in) + '</td>'
      + '<td class="num">$' + (p.cost || 0).toFixed(2) + '</td>'
      + '<td class="num">' + p.sessions + '</td>'
      + '</tr>';
  }).join('') || '<tr><td colspan="5" style="color:var(--muted)">尚無資料</td></tr>';
}

$('#window').onchange = tick;
$('#cumulative').onchange = tick;

window.addEventListener('load', () => {
  if (typeof Chart === 'undefined') {
    document.body.insertAdjacentHTML('afterbegin',
      '<div class="warn">無法載入 Chart.js（需要連線到 cdn.jsdelivr.net）。請確認網路，或改用內網可達的 CDN。</div>');
    return;
  }
  initCharts();
  restyleCharts();
  tick();
  setInterval(tick, POLL_MS);
});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
