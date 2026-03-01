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

# /.../imkerutils/exquisite/ui/server.py -> /.../imkerutils/exquisite/assets
ASSETS_ROOT = Path(__file__).resolve().parents[1] / "assets"


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
            elif self.path.startswith("/assets/"):
                self._serve_asset()
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

    def _send_bytes(self, *, status: int, content_type: str, data: bytes, cache: str = "no-store") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(data)

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
    padding: 8px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    flex: 1;
    gap: 8px;
  }

  .logoRow {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    background: #000;
    padding: 20;
    border-radius: 25;
  }
  #projectLogo {
    height: 125px;
    width: auto;
    display: block;
  }

  /* Fixed “page” area above the prompt. */
  .viewport {
    position: relative;
    flex: 1;
    background: #000;
    border: 1px solid #333;
    border-radius: 8px;
    overflow: hidden;
  }

  .scroller {
    position: absolute;
    inset: 0;
    overflow: auto;
    background: #000;
  }

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
    display: none;
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

  /* -------- Modal popup -------- */
  .modalBackdrop {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.72);
    display: none;
    align-items: center;
    justify-content: center;
    padding: 18px;
    z-index: 9999;
  }
  .modalBackdrop.show {
    display: flex;
  }
  .modal {
    width: min(920px, 100%);
    background: #0b0b0b;
    border: 1px solid #333;
    border-radius: 12px;
    box-shadow: 0 18px 60px rgba(0,0,0,0.6);
    overflow: hidden;
  }
  .modalHeader {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 14px;
    border-bottom: 1px solid #222;
    background: #070707;
    color: #eee;
    font-weight: 800;
  }
  .modalBody {
    padding: 14px;
    color: #ffb3b3;
    white-space: pre-wrap;
    font-size: 13px;
    line-height: 1.35;
  }
  .modalActions {
    display: flex;
    gap: 10px;
    padding: 12px 14px;
    border-top: 1px solid #222;
    background: #070707;
  }
  .btnSecondary {
    background: #222;
    color: #eee;
    border: 1px solid #333;
  }
  .btnDonate {
    background: #ffcf40;
    color: #111;
  }
</style>
</head>

<body>
<div class="wrap">

  <div class="logoRow">
    <img id="projectLogo" src="/assets/images/logo_trimmed_silver.png" alt="Exquisite"/>
  </div>

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

<!-- Modal (error popup) -->
<div id="modalBackdrop" class="modalBackdrop" role="dialog" aria-modal="true" aria-label="Error">
  <div class="modal">
    <div class="modalHeader">
      <div id="modalTitle">Step rejected</div>
      <button id="modalCloseBtn" class="btnSecondary">Close</button>
    </div>
    <div id="modalBody" class="modalBody"></div>
    <div id="modalActions" class="modalActions" style="display:none;">
      <button id="donateBtn" class="btnDonate">Donate (coming soon)</button>
      <button id="contactBtn" class="btnSecondary">Contact administrator</button>
    </div>
  </div>
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

  // Modal elements
  const modalBackdrop = document.getElementById("modalBackdrop");
  const modalTitle = document.getElementById("modalTitle");
  const modalBody = document.getElementById("modalBody");
  const modalActions = document.getElementById("modalActions");
  const modalCloseBtn = document.getElementById("modalCloseBtn");
  const donateBtn = document.getElementById("donateBtn");
  const contactBtn = document.getElementById("contactBtn");

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

  function isBillingish(text) {
    const s = String(text || "").toLowerCase();
    if (!s) return false;
    // keep this intentionally broad; you can tighten later
    const needles = [
      "bill", "billing", "payment", "pay", "paid",
      "card", "credit", "invoice", "limit", "quota",
      "hard limit", "soft limit", "plan", "upgrade",
      "insufficient funds"
    ];
    for (const n of needles) {
      if (s.indexOf(n) !== -1) return true;
    }
    return false;
  }

  function showModalError(title, message) {
    const msg = String(message || "");
    const billing = isBillingish(msg);

    modalTitle.textContent = title || "Error";
    modalBody.textContent = msg;

    if (billing) {
      // Add the required extra messaging
      modalBody.textContent =
        msg +
        "\\n\\n" +
        "⚠️ This looks like a billing / payment / quota issue.\\n" +
        "• Contact the EXQUISITE sytem administrators... if you know how to find them.\\n" +
        "• Donate: coming soon (we'll wire this to payments later).";

      modalActions.style.display = "flex";
    } else {
      modalActions.style.display = "none";
    }

    modalBackdrop.classList.add("show");
  }

  function hideModal() {
    modalBackdrop.classList.remove("show");
  }

  modalCloseBtn.addEventListener("click", function() {
    hideModal();
  });

  // Clicking outside closes too
  modalBackdrop.addEventListener("click", function(e) {
    if (e.target === modalBackdrop) hideModal();
  });

  donateBtn.addEventListener("click", function() {
    // Placeholder; you’ll wire real payments later.
    alert("Donate is not wired yet (coming soon).");
  });

  contactBtn.addEventListener("click", function() {
    // Placeholder; you’ll wire real contacts later.
    alert("Contact EXQUISITE system administrators to resolve billing/payment limits... If y'know, y'know.");
  });

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

  function summarizeStepError(out) {
    // Prefer structured field if present
    if (out && typeof out === "object") {
      if (out.rejection_reason) return String(out.rejection_reason);
      if (out.detail) return String(out.detail);
      if (out.error) return String(out.error);
      return JSON.stringify(out, null, 2);
    }
    return String(out || "");
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
      showModalError("Network error", "network error: " + String(e));
      btn.disabled = false;
      return;
    }

    // HTTP-level failure
    if (!r.ok) {
      setStatusIdle();
      const msg = "step HTTP error:\\n" + summarizeStepError(out);
      showModalError("Step rejected", msg);
      btn.disabled = false;
      return;
    }

    // App-level rejection (still HTTP 200)
    if (out && out.status === "rejected") {
      setStatusIdle();
      const msg = summarizeStepError(out) || "rejected_without_reason";
      showModalError("Step rejected", msg);
      btn.disabled = false;
      return;
    }

    // Success
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

        self._send_bytes(status=200, content_type="image/png", data=b, cache="no-store")

    def _serve_asset(self) -> None:
        # URL path like: /assets/images/logo_trimmed_silver.png
        rel = self.path[len("/assets/") :]
        rel = rel.split("?", 1)[0].split("#", 1)[0]
        rel = rel.lstrip("/")

        # prevent traversal
        try:
            target = (ASSETS_ROOT / rel).resolve()
            root = ASSETS_ROOT.resolve()
            if root not in target.parents and target != root:
                self.send_error(400, "bad asset path")
                return
        except Exception:
            self.send_error(400, "bad asset path")
            return

        if not target.exists() or not target.is_file():
            self.send_error(404)
            return

        ext = target.suffix.lower()
        if ext == ".png":
            ctype = "image/png"
        elif ext in (".jpg", ".jpeg"):
            ctype = "image/jpeg"
        elif ext == ".webp":
            ctype = "image/webp"
        elif ext == ".svg":
            ctype = "image/svg+xml"
        else:
            ctype = "application/octet-stream"

        data = target.read_bytes()
        # cache assets a bit; change to no-store if you keep editing logo
        self._send_bytes(status=200, content_type=ctype, data=data, cache="max-age=3600")

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