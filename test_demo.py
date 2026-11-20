import tempfile
from io import BytesIO
from unittest.mock import Mock
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

import app
import guard


class DemoTests(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.object(guard, "DB", Path(folder) / "test.db"))
        self.db = self.enterContext(closing(guard.connect()))

    def test_three_fixtures(self):
        for case in guard.CASES:
            key = guard.run(self.db, case, "local")
            rows = self.db.execute("SELECT * FROM events WHERE run=?", (key,)).fetchall()
            self.assertEqual(sum(r["decision"] == "HOLD" for r in rows), int(case != "clean"))
            self.assertFalse(any(r["tool"] == "mock_outbox" for r in rows))
            self.assertEqual(rows[-1]["tool"], "show_summary")
        self.assertEqual(guard.classify(guard.CASES["subtle"][-1]), "No keyword match")

    def test_default_deny(self):
        for action, source in [("forward_inbox","user"), ("unknown","user"), ("read_demo_inbox","email/M03")]:
            self.assertEqual(guard.gate(action, source)[0], "HOLD")

    def test_browser_workflow(self):
        def request(path, fields=None):
            data = urlencode(fields or {}).encode()
            method = "POST" if fields else "GET"
            head = f"{method} {path} HTTP/1.0\r\nContent-Length: {len(data)}\r\n\r\n"
            sock = Mock()
            sock.makefile.return_value = BytesIO(head.encode() + data)
            app.Handler(sock, ("127.0.0.1", 0), Mock())
            return b"".join(c.args[0] for c in sock.sendall.call_args_list).decode()

        self.assertIn(app.TOKEN, request("/"))
        reply = request("/run", dict(token=app.TOKEN, case="redirect", engine="local"))
        self.assertIn("303 See Other", reply)
        path = reply.split("Location: ")[1].split("\r\n")[0]
        key = path.split("=")[-1]
        self.assertIn("Dismiss held action", request(path))
        for _ in range(2):
            self.assertIn("303 See Other", request("/review", dict(token=app.TOKEN, run=key)))
            self.assertIn("DENIED", request(path))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events WHERE decision='DENIED'").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()

