"""极简 Chrome DevTools Protocol 客户端（截图 / 执行 JS）。"""
from __future__ import annotations

import base64
import json
import sys
import time
import urllib.request

from websockets.sync.client import connect


def target(port=9222, url_contains=None):
    data = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
    pages = [t for t in data if t.get("type") == "page"]
    if url_contains:
        pages = [t for t in pages if url_contains in t.get("url", "")] or pages
    return pages[0]


class CDP:
    def __init__(self, port=9222, url_contains=None):
        self.ws = connect(target(port, url_contains)["webSocketDebuggerUrl"], max_size=80 * 1024 * 1024)
        self.i = 0

    def cmd(self, method, params=None):
        self.i += 1
        mid = self.i
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})

    def eval(self, expr):
        r = self.cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("value")

    def navigate(self, url):
        self.cmd("Page.enable")
        self.cmd("Network.enable")
        self.cmd("Network.setCacheDisabled", {"cacheDisabled": True})
        self.cmd("Page.navigate", {"url": url})
        time.sleep(0.8)
        for _ in range(50):
            if self.eval("document.readyState") == "complete":
                break
            time.sleep(0.1)
        time.sleep(0.8)

    def viewport(self, w=1440, h=1000, scale=1):
        self.cmd("Emulation.setDeviceMetricsOverride", {
            "width": w, "height": h, "deviceScaleFactor": scale, "mobile": False,
        })

    def shot(self, path, full=False):
        params = {"format": "png", "captureBeyondViewport": bool(full)}
        if full:
            m = self.cmd("Page.getLayoutMetrics")
            cs = m.get("cssContentSize") or m.get("contentSize")
            params["clip"] = {"x": 0, "y": 0, "width": cs["width"], "height": cs["height"], "scale": 1}
        r = self.cmd("Page.captureScreenshot", params)
        with open(path, "wb") as f:
            f.write(base64.b64decode(r["data"]))
        return path


if __name__ == "__main__":
    action = sys.argv[1]
    if action == "shot":
        url, out = sys.argv[2], sys.argv[3]
        w = int(sys.argv[4]) if len(sys.argv) > 4 else 1440
        h = int(sys.argv[5]) if len(sys.argv) > 5 else 1000
        c = CDP()
        c.viewport(w, h)
        c.navigate(url)
        c.shot(out, full=(len(sys.argv) > 6 and sys.argv[6] == "full"))
        print(out)
    elif action == "snap":
        out = sys.argv[2]
        w = int(sys.argv[3]) if len(sys.argv) > 3 else 1440
        h = int(sys.argv[4]) if len(sys.argv) > 4 else 1000
        c = CDP()
        c.viewport(w, h)
        time.sleep(0.4)
        c.shot(out, full=(len(sys.argv) > 5 and sys.argv[5] == "full"))
        print(out)
    elif action == "eval":
        c = CDP()
        print(c.eval(sys.argv[2]))
    elif action == "open":
        c = CDP()
        c.viewport(1440, 1000)
        c.navigate(sys.argv[2])
        print(c.eval("document.title"))
