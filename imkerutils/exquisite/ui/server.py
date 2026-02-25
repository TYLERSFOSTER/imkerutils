# imkerutils/exquisite/ui/server.py
from __future__ import annotations

import json
import os
import traceback
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs

from PIL import Image

from imkerutils.exquisite.api.openai_client import OpenAITileGeneratorClient
from imkerutils.exquisite.pipeline.session import ExquisiteSession

ExtendMode = str  # "x_ltr" | "x_rtl" | "y_ttb" | "y_btt"
VIEWPORT_PX = 1024


class ReuseHTTPServer(HTTPServer):
    allow_reuse_address = True


@dataclass(frozen=True)
class ViewState:
    mode: ExtendMode
    canvas_w: int
    canvas_h: int
    step_index: int


class ExquisiteHandler(BaseHTTPRequestHandler):
    session: ExquisiteSession | None = None

    def log_message(self, fmt: str, *args) -> None:
        super().log_message(fmt, *args)

    def do_GET(self) -> None:
        try:
            if self.path == "/":
                self._serve_index()
            elif self.path.startswith("/canvas.png"):
                self._serve_canvas()
            elif self.path == "/state.json":
                self._serve_state()
            else:
                self.send_error(404)
        except Exception:
            traceback.print_exc()
            self._send_json(500, {"error": "handler_crash", "where": "do_GET"})

    def do_POST(self) -> None:
        try:
            if self.path == "/step":
                self._handle_step()
            else:
                self.send_error(404)
        except Exception:
            traceback.print_exc()
            self._send_json(500, {"error": "handler_crash", "where": "do_POST"})

    # ------------------------
    # helpers

    def _read_form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        data = parse_qs(raw)
        return {k: (v[0] if v else "") for k, v in data.items()}

    def _send_json(self, status: int, payload: dict) -> None:
        b = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def _send_html(self, html: str) -> None:
        b = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    # ------------------------
    # routes

    def _serve_index(self) -> None:
        # IMPORTANT:
        # - NOT an f-string.
        # - Avoid JS template literals (`...${}...`) so braces never collide with Python formatting.
        html = """\
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Exquisite</title>
<style>
  body {
    margin: 0;
    background: #111;
    color: #eee;
    display: flex;
    flex-direction: column;
    height: 100vh;
    font-family: -apple-system, system-ui, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
  }

  /* Full-bleed layout: closer to window edges */
  .wrap {
    width: 100%;
    margin: 0;
    padding: 8px;            /* small breathing room; set to 0 if you want true edge-to-edge */
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    flex: 1;
    gap: 8px;
  }

  /* Fixed “page” area above the prompt. */
  .viewport {
    position: relative;
    flex: 1;
    background: #000;
    border: 1px solid #333;
    border-radius: 8px;
    overflow: hidden; /* rounds corners for scroller content */
  }

  /* Browser-native scrolling container */
  .scroller {
    position: absolute;
    inset: 0;
    overflow: auto;
    background: #000;
  }

  /* Scale image by HEIGHT so it fills viewport height */
  img#canvasImg {
    display: block;
    height: 100%;
    width: auto;
    image-rendering: auto;
  }

  .hud {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    background: #111;
  }

  textarea {
    flex: 1;
    height: 96px;
    resize: vertical;
    background: #0b0b0b;
    color: #eee;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 10px;
    font-size: 14px;
    line-height: 1.3;
    box-sizing: border-box;
  }

  button {
    background: #2d7;
    color: #000;
    border: none;
    padding: 10px 14px;
    font-weight: 800;
    cursor: pointer;
    border-radius: 8px;
    white-space: nowrap;
    align-self: flex-start;
  }
  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  /* Status strip (spinner + elapsed time) */
  .statusbar {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border: 1px solid #333;
    border-radius: 8px;
    background: #0b0b0b;
    font-size: 12px;
    color: #aaa;
  }

  .spinner {
    width: 14px;
    height: 14px;
    border: 2px solid #333;
    border-top-color: #2d7;
    border-radius: 50%;
    animation: spin 0.9s linear infinite;
    display: none; /* hidden unless running */
  }

  .statusbar.running .spinner {
    display: inline-block;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .meta {
    padding: 8px 10px;
    font-size: 12px;
    color: #aaa;
    white-space: pre;
    border: 1px solid #333;
    border-radius: 8px;
    background: #0b0b0b;
  }

  .err {
    padding: 8px 10px;
    font-size: 12px;
    color: #ff7a7a;
    white-space: pre-wrap;
    border: 1px solid #442;
    border-radius: 8px;
    background: #150b0b;
  }
</style>
</head>

<body>
<div class="wrap">

  <div class="viewport">
    <div id="scroller" class="scroller">
      <img id="canvasImg" src="/canvas.png?cb=0" />
    </div>
  </div>

  <div class="hud">
    <textarea id="prompt" placeholder="Prompt (describe what to add in the NEW region)."></textarea>
    <button id="runBtn">Run step</button>
  </div>

  <div id="statusbar" class="statusbar">
    <div id="spinner" class="spinner"></div>
    <div id="statusText">Idle.</div>
  </div>

  <div id="meta" class="meta"></div>
  <div id="err" class="err"></div>

</div>

<script>
  const scroller = document.getElementById("scroller");
  const img = document.getElementById("canvasImg");
  const meta = document.getElementById("meta");
  const err = document.getElementById("err");
  const btn = document.getElementById("runBtn");
  const promptEl = document.getElementById("prompt");

  const statusbar = document.getElementById("statusbar");
  const statusText = document.getElementById("statusText");

  let timerHandle = null;
  let t0 = 0;

  function setStatusIdle() {
    statusbar.classList.remove("running");
    statusText.textContent = "Idle.";
    if (timerHandle !== null) {
      clearInterval(timerHandle);
      timerHandle = null;
    }
  }

  function setStatusRunning(label) {
    statusbar.classList.add("running");
    t0 = Date.now();
    statusText.textContent = label + " (0.0s)";
    if (timerHandle !== null) clearInterval(timerHandle);
    timerHandle = setInterval(function() {
      const dt = (Date.now() - t0) / 1000.0;
      statusText.textContent = label + " (" + dt.toFixed(1) + "s)";
    }, 100);
  }

  function autoFeed(mode) {
    const maxScrollLeft = scroller.scrollWidth - scroller.clientWidth;
    const maxScrollTop  = scroller.scrollHeight - scroller.clientHeight;

    if (mode === "x_ltr") {
      if (maxScrollLeft <= 0) scroller.scrollLeft = 0;
      else scroller.scrollLeft = maxScrollLeft;
      scroller.scrollTop = 0;
      return;
    }

    if (mode === "x_rtl") {
      scroller.scrollLeft = 0;
      scroller.scrollTop = 0;
      return;
    }

    if (mode === "y_ttb") {
      scroller.scrollLeft = 0;
      if (maxScrollTop <= 0) scroller.scrollTop = 0;
      else scroller.scrollTop = maxScrollTop;
      return;
    }

    if (mode === "y_btt") {
      scroller.scrollLeft = 0;
      scroller.scrollTop = 0;
      return;
    }
  }

  async function refresh() {
    err.textContent = "";
    const r = await fetch("/state.json", {cache: "no-store"});
    const st = await r.json();
    if (!r.ok) {
      err.textContent = "state.json error:\\n" + JSON.stringify(st, null, 2);
      return;
    }

    img.src = "/canvas.png?cb=" + Date.now();

    meta.textContent =
      "mode: " + st.mode + "\\n" +
      "canvas: " + st.canvas_w + "×" + st.canvas_h + "\\n" +
      "step_index: " + st.step_index;

    requestAnimationFrame(function() {
      requestAnimationFrame(function() {
        autoFeed(st.mode);
      });
    });
  }

  btn.addEventListener("click", async function() {
    btn.disabled = true;
    err.textContent = "";
    setStatusRunning("Running step");

    const body = new URLSearchParams();
    body.set("prompt", promptEl.value || "");

    let r = null;
    let out = {};
    try {
      r = await fetch("/step", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: body.toString(),
      });
      out = await r.json().catch(function() { return {}; });
    } catch (e) {
      setStatusIdle();
      err.textContent = "network error: " + String(e);
      btn.disabled = false;
      return;
    }

    if (!r.ok) {
      setStatusIdle();
      err.textContent = "step error:\\n" + JSON.stringify(out, null, 2);
      btn.disabled = false;
      return;
    }

    await refresh();
    setStatusIdle();
    btn.disabled = false;
  });

  refresh().then(function() {
    setStatusIdle();
  }).catch(function(e) {
    setStatusIdle();
    err.textContent = "refresh crash: " + String(e);
  });
</script>
</body>
</html>
"""
        html = html.replace("__VIEWPORT_PX__", str(VIEWPORT_PX))
        self._send_html(html)

    def _serve_state(self) -> None:
        if not self.session:
            self._send_json(500, {"error": "no_session"})
            return

        canvas_path = self.session.state.canvas_path
        img = Image.open(canvas_path)
        w, h = img.size

        mode = self.session.state.mode
        step_index = self.session.state.step_index_current

        st = ViewState(mode=mode, canvas_w=w, canvas_h=h, step_index=step_index)
        self._send_json(200, st.__dict__)

    def _serve_canvas(self) -> None:
        if not self.session:
            self.send_error(500)
            return

        canvas_path = self.session.state.canvas_path
        img = Image.open(canvas_path).convert("RGB")

        buf = BytesIO()
        img.save(buf, format="PNG")
        b = buf.getvalue()

        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def _handle_step(self) -> None:
        if not self.session:
            self._send_json(500, {"error": "no_session"})
            return

        form = self._read_form()
        prompt = (form.get("prompt") or "").strip()

        client = OpenAITileGeneratorClient()

        if not hasattr(self.session, "execute_step_real"):
            self._send_json(
                500,
                {
                    "error": "missing_execute_step_real",
                    "detail": "ExquisiteSession has no execute_step_real(). You likely have only Phase B mock wired.",
                    "found": [name for name in dir(self.session) if "execute_step" in name],
                },
            )
            return

        try:
            result = self.session.execute_step_real(prompt=prompt, client=client)
        except Exception as e:
            traceback.print_exc()
            self._send_json(500, {"error": "execute_step_real_exception", "detail": str(e)})
            return

        payload = {"ok": True}
        for k in ["status", "step_index", "canvas_before_size", "canvas_after_size", "rejection_reason", "step_dir"]:
            if hasattr(result, k):
                payload[k] = getattr(result, k)

        self._send_json(200, payload)


def run_server(*, initial_canvas: Path, mode: ExtendMode = "x_ltr", host: str = "127.0.0.1", port: int = 8000) -> None:
    env_port = os.environ.get("EXQUISITE_PORT")
    if env_port:
        try:
            port = int(env_port)
        except ValueError:
            pass

    session = ExquisiteSession.create(initial_canvas_path=initial_canvas, mode=mode)
    ExquisiteHandler.session = session

    server = ReuseHTTPServer((host, port), ExquisiteHandler)
    print(f"Running at http://{host}:{port}")
    server.serve_forever()