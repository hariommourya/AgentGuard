"""Local web console. Launch with python app.py."""
import os
import secrets
from contextlib import closing
from html import escape as h
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import guard

TOKEN = secrets.token_urlsafe(32)
STYLE = Path(__file__).with_name("style.css").read_text(encoding="utf8")


def page(db, key="", error=""):
    run = db.execute("SELECT * FROM runs WHERE id=?", (key,)).fetchone()
    case = run["scenario"] if run else "redirect"
    fixture = guard.CASES[case]
    rows = guard.MAIL + [fixture[1:]]
    events = list(db.execute("SELECT * FROM events WHERE run=? ORDER BY id", (key,)))
    token = f'<input type="hidden" name="token" value="{TOKEN}">'
    options = "".join(f'<option value="{k}" {"selected" if k == case else ""}>{v[0]}</option>' for k, v in guard.CASES.items())
    gemini = '<option value="gemini"' + (' selected' if run and run['engine']=='gemini' else '') + '>Gemini API</option>' if os.getenv("GEMINI_API_KEY") else ''
    inbox = "".join(f'<details open><summary><code>{mid}</code> {sub}</summary><small>{sender} · Untrusted email</small><p>{body}</p><small>{guard.classify(body)}</small></details>' for mid,sender,sub,body in rows)
    result = '<div class="empty">Run a comparison to see the proposed actions and policy decisions.</div>'
    if run:
        cards = ""
        for lane, title in [("Replay","Unguarded replay"),("AgentGuard","AgentGuard")]:
            selected = [e for e in events if e["lane"]==lane]
            outbound = sum(e["decision"]=="SIMULATED" for e in selected)
            cards += f'<article><h3>{title}</h3><strong>{outbound}</strong> mock outbound events'
            for e in selected:
                cards += f'<p><b class="{e["decision"]}">{e["decision"]}</b> <code>{e["tool"]}</code><br>{h(e["reason"])}</p>'
            cards += '</article>'
        table = ''.join('<tr>'+''.join(f'<td>{h(str(e[col]))}</td>' for col in ("id","lane","tool","source","decision","reason"))+'</tr>' for e in events)
        review = ''
        if any(e["decision"]=="HOLD" for e in events) and not any(e["decision"]=="DENIED" for e in events):
            review = f'<form method="post" action="/review">{token}<input type="hidden" name="run" value="{key}"><button>Dismiss held action</button></form>'
        result = f'<div class="pair">{cards}</div>{review}<h2>Inbox summary</h2><p>{h(run["summary"])}</p><small>Engine · {h(run["engine"])}</small><h2>Audit trail</h2><div class="scroll"><table><tr><th>ID</th><th>Lane</th><th>Tool</th><th>Source</th><th>Decision</th><th>Reason</th></tr>{table}</table></div>'
    history = ''.join(f'<li><a href="/?run={r["id"]}">{r["created"]} UTC · {guard.CASES[r["scenario"]][0]}</a></li>' for r in db.execute("SELECT * FROM runs ORDER BY rowid DESC LIMIT 10"))
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>AgentGuard | Action review</title><style>{STYLE}</style><header><b>◈ &nbsp; AgentGuard</b><small>Local demo console</small></header><main><h1>Inbox action review</h1><p>Compare the same proposed action with and without an authorization check.</p><section><small>AUTHORIZED USER TASK</small><h2>“{guard.TASK}”</h2><form method="post" action="/run">{token}<label>Scenario<select name="case">{options}</select></label><label>Summary engine<select name="engine"><option value="local">Offline fixture</option>{gemini}</select></label><button>Run comparison →</button></form></section><p role="alert">{h(error)}</p><div class="layout"><aside><h2>Evidence inbox</h2>{inbox}</aside><section><h2>Action comparison</h2>{result}</section></div><h2>Recent runs</h2><ul>{history or "<li>No runs yet.</li>"}</ul></main></html>'''


class Handler(BaseHTTPRequestHandler):
    def render(self, key="", error="", status=200):
        with closing(guard.connect()) as db:
            body = page(db, key, error).encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path != "/":
            return self.send_error(404)
        self.render(parse_qs(url.query).get("run", [""])[0])

    def do_POST(self):
        length = self.headers.get("Content-Length", "")
        if not length.isdigit() or len(length)>5 or int(length)>4096:
            return self.send_error(400)
        fields = parse_qs(self.rfile.read(int(length)).decode("ascii", "replace"))
        def field(name):
            return fields.get(name, [""])[0]
        if field("token") != TOKEN:
            return self.send_error(403)
        with closing(guard.connect()) as db:
            if self.path == "/run" and field("case") in guard.CASES and field("engine") in ("local","gemini"):
                try:
                    key = guard.run(db, field("case"), field("engine"))
                except (OSError, KeyError, IndexError, ValueError):
                    return self.render(error="Summary unavailable. Check the Gemini key, model and connection, or select Offline fixture.", status=502)
            elif self.path == "/review":
                key = field("run")
                if not db.execute("SELECT 1 FROM runs WHERE id=?", (key,)).fetchone():
                    return self.send_error(404)
                guard.dismiss(db, key)
            else:
                return self.send_error(400)
        self.send_response(303)
        self.send_header("Location", "/?run="+key)
        self.end_headers()


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("Open http://127.0.0.1:8765   |   Ctrl+C to stop", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

