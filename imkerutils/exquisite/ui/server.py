from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs
from io import BytesIO

from PIL import Image

from imkerutils.exquisite.pipeline.session import ExquisiteSession
from imkerutils.exquisite.api.openai_client import OpenAITileGeneratorClient
from imkerutils.exquisite.geometry.tile_mode import ExtendMode


HOST = "127.0.0.1"
PORT = 8000


class ExquisiteHandler(BaseHTTPRequestHandler):

    session: ExquisiteSession | None = None

    def do_GET(self):
        if self.path == "/":
            self._serve_index()
        elif self.path == "/canvas.png":
            self._serve_canvas()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/step":
            self._handle_step()
        else:
            self.send_error(404)

    # ------------------------

    def _serve_index(self):
        html = """
        <html>
        <body>
        <h1>Exquisite</h1>
        <img src="/canvas.png" width="512"/><br/><br/>
        <form method="POST" action="/step">
            Prompt:<br/>
            <textarea name="prompt" rows="4" cols="50"></textarea><br/><br/>
            <button type="submit">Run Step</button>
        </form>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _serve_canvas(self):
        if not self.session:
            self.send_error(500)
            return

        img = Image.open(self.session.state.canvas_path)
        buf = BytesIO()
        img.save(buf, format="PNG")

        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.end_headers()
        self.wfile.write(buf.getvalue())

    def _handle_step(self):
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length).decode("utf-8")
        data = parse_qs(body)
        prompt = data.get("prompt", [""])[0]

        client = OpenAITileGeneratorClient()

        result = self.session.execute_step_real(
            prompt=prompt,
            client=client,
        )

        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()


def run_server(initial_canvas: Path, mode: ExtendMode = "x_ltr"):
    session = ExquisiteSession.create(
        initial_canvas_path=initial_canvas,
        mode=mode,
    )

    ExquisiteHandler.session = session

    server = HTTPServer((HOST, PORT), ExquisiteHandler)
    print(f"Running at http://{HOST}:{PORT}")
    server.serve_forever()