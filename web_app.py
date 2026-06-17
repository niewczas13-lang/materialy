from __future__ import annotations

import argparse
import html
import json
import mimetypes
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import unicodedata
import uuid
import warnings
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

warnings.filterwarnings("ignore", message="'cgi' is deprecated.*", category=DeprecationWarning)
import cgi

from ftth_bom.engine import run_analysis
from ftth_bom.exporters import export_result


ROOT = Path(__file__).resolve().parent
INPUTS = ROOT / "inputs"
OUTPUTS = ROOT / "outputs"
UPLOADS = OUTPUTS / "uploads"
CATALOG = next(INPUTS.glob("KATALOGI*.xlsx"), None)
BELL = next(INPUTS.glob("*BELL*.xlsx"), None)


@dataclass
class AnalysisJob:
    job_id: str
    task_name: str
    state: str = "running"
    percent: int = 0
    message: str = "Start"
    result_html: str = ""
    error: str = ""
    created_at: float = 0.0


class AppState:
    last_html = ""
    jobs: dict[str, AnalysisJob] = {}
    lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = unquote(urlparse(self.path).path)
        if path.startswith("/outputs/"):
            self._serve_file(ROOT / path.lstrip("/"))
            return
        if path.startswith("/status/"):
            self._serve_status(path.rsplit("/", 1)[-1])
            return
        if path.startswith("/result/"):
            self._serve_result(path.rsplit("/", 1)[-1])
            return
        self._send_html(render_page(AppState.last_html))

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/analyze":
            self.send_error(404)
            return
        if CATALOG is None or BELL is None:
            self._send_html(render_page("<p class='error'>Brakuje katalogu lub pliku BELL w folderze inputs.</p>"))
            return
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", "")},
        )
        file_item = form["gpkg"] if "gpkg" in form else None
        if not has_upload_file(file_item):
            self._send_html(render_page("<p class='error'>Wybierz plik GPKG.</p>"))
            return
        filename = safe_upload_name(file_item.filename)
        temp_dir = Path(tempfile.mkdtemp(prefix="ftth_bom_upload_"))
        upload_path = temp_dir / filename
        try:
            with upload_path.open("wb") as target:
                shutil.copyfileobj(file_item.file, target, length=1024 * 1024)
        except Exception as exc:
            shutil.rmtree(temp_dir, ignore_errors=True)
            self._send_html(render_page(f"<p class='error'>Błąd analizy: {html.escape(str(exc))}</p>"))
            return

        job_id = create_job(upload_path.stem)
        thread = threading.Thread(target=run_analysis_job, args=(job_id, upload_path, temp_dir), daemon=True)
        thread.start()
        self.send_response(303)
        self.send_header("Location", f"/result/{job_id}")
        self.end_headers()

    def _send_html(self, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict[str, object], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_status(self, job_id: str) -> None:
        snapshot = job_snapshot(job_id)
        if snapshot is None:
            self._send_json({"state": "missing", "percent": 0, "message": "Nie znaleziono analizy."}, status=404)
            return
        self._send_json(snapshot)

    def _serve_result(self, job_id: str) -> None:
        job = get_job(job_id)
        if job is None:
            self._send_html(render_page("<p class='error'>Nie znaleziono analizy.</p>"))
            return
        if job.state == "done":
            self._send_html(render_page(job.result_html))
            return
        if job.state == "error":
            self._send_html(render_page(f"<p class='error'>Błąd analizy: {html.escape(job.error)}</p>"))
            return
        self._send_html(render_page(render_progress_page(job_id)))

    def _serve_file(self, path: Path) -> None:
        try:
            resolved = path.resolve()
            if not str(resolved).startswith(str(OUTPUTS.resolve())) or not resolved.exists():
                self.send_error(404)
                return
            data = resolved.read_bytes()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(resolved))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", attachment_header(resolved.name))
        self.end_headers()
        self.wfile.write(data)


def has_upload_file(file_item: object) -> bool:
    return file_item is not None and bool(getattr(file_item, "filename", ""))


def safe_upload_name(filename: str) -> str:
    name = Path(filename).name if filename else "projekt.gpkg"
    if not name.lower().endswith(".gpkg"):
        name = f"{Path(name).stem}.gpkg"
    return name


def create_job(task_name: str) -> str:
    job_id = uuid.uuid4().hex
    with AppState.lock:
        AppState.jobs[job_id] = AnalysisJob(job_id=job_id, task_name=task_name, created_at=time.time())
    return job_id


def get_job(job_id: str) -> AnalysisJob | None:
    with AppState.lock:
        return AppState.jobs.get(job_id)


def update_job(
    job_id: str,
    *,
    percent: int | None = None,
    message: str | None = None,
    state: str | None = None,
    result_html: str | None = None,
    error: str | None = None,
) -> None:
    with AppState.lock:
        job = AppState.jobs.get(job_id)
        if job is None:
            return
        if percent is not None:
            job.percent = max(job.percent, min(100, int(percent)))
        if message is not None:
            job.message = message
        if state is not None:
            job.state = state
        if result_html is not None:
            job.result_html = result_html
        if error is not None:
            job.error = error


def job_snapshot(job_id: str) -> dict[str, object] | None:
    with AppState.lock:
        job = AppState.jobs.get(job_id)
        if job is None:
            return None
        return {
            "job_id": job.job_id,
            "task_name": job.task_name,
            "state": job.state,
            "percent": job.percent,
            "message": job.message,
            "result_url": f"/result/{job.job_id}" if job.state == "done" else "",
            "error": job.error,
        }


def run_analysis_job(job_id: str, upload_path: Path, temp_dir: Path) -> None:
    def progress(event: tuple[int, str]) -> None:
        percent, message = event
        update_job(job_id, percent=percent, message=message)

    try:
        update_job(job_id, percent=5, message="GPKG zapisane w lokalnym temp")
        result = run_analysis(
            gpkg_path=upload_path,
            catalog_path=CATALOG,
            bell_path=BELL,
            task_name=upload_path.stem,
            preferences_db=ROOT / "data" / "preferences.sqlite",
            local_copy=False,
            progress=progress,
        )
        progress((95, "Eksport XLSX/PDF"))
        export_result(result, OUTPUTS)
        result_html = render_result(result)
        AppState.last_html = result_html
        update_job(job_id, percent=100, message="Gotowe", state="done", result_html=result_html)
    except Exception as exc:
        update_job(job_id, state="error", error=str(exc), message="Błąd analizy")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def attachment_header(filename: str) -> str:
    fallback = unicodedata.normalize("NFKD", filename)
    fallback = "".join(ch for ch in fallback if not unicodedata.combining(ch))
    fallback = re.sub(r'[^A-Za-z0-9._ -]+', "_", fallback).strip(" ._")
    if not fallback:
        fallback = "download"
    encoded = quote(filename, safe="")
    return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{encoded}'


def output_href(path: Path) -> str:
    return f"/outputs/{quote(path.name)}"


def resolve_pid_file(pid_file: str | None) -> Path | None:
    if not pid_file:
        return None
    path = Path(pid_file)
    if not path.is_absolute():
        path = ROOT / path
    return path


def write_pid_file(pid_file: Path | None) -> None:
    if pid_file is None:
        return
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()), encoding="ascii")


def remove_pid_file(pid_file: Path | None) -> None:
    if pid_file is None:
        return
    try:
        if pid_file.exists():
            pid_file.unlink()
    except OSError:
        pass


def render_page(content: str = "") -> str:
    return f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FTTH BOM</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; color: #1f2933; background: #f5f7fa; }}
    header {{ background: #12355b; color: #fff; padding: 18px 28px; }}
    main {{ padding: 22px 28px; max-width: 1400px; margin: 0 auto; }}
    form {{ display: flex; gap: 12px; align-items: center; background: #fff; padding: 16px; border: 1px solid #d8e0ea; }}
    button {{ background: #0f766e; color: #fff; border: 0; padding: 10px 14px; cursor: pointer; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; margin: 18px 0; font-size: 13px; }}
    th, td {{ border: 1px solid #d8e0ea; padding: 7px; vertical-align: top; }}
    th {{ background: #1f4e78; color: #fff; position: sticky; top: 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin: 16px 0; }}
    .metric {{ background: #fff; border: 1px solid #d8e0ea; padding: 12px; }}
    .warn {{ background: #fff2cc; }}
    .error {{ background: #fde2e2; padding: 12px; border: 1px solid #f5a6a6; }}
    a.button {{ display: inline-block; background: #12355b; color: #fff; padding: 10px 12px; text-decoration: none; margin-right: 8px; }}
    .progress-panel {{ background: #fff; border: 1px solid #d8e0ea; padding: 16px; margin-top: 18px; max-width: 760px; }}
    .progress-track {{ height: 18px; background: #e5edf5; border: 1px solid #c8d5e2; overflow: hidden; }}
    .progress-bar {{ width: 0%; height: 100%; background: #0f766e; transition: width .25s ease; }}
    .progress-meta {{ display: flex; justify-content: space-between; gap: 12px; margin-top: 10px; font-size: 14px; }}
  </style>
</head>
<body>
  <header><h1>FTTH BOM - lokalna analiza GPKG</h1></header>
  <main>
    <form action="/analyze" method="post" enctype="multipart/form-data">
      <input type="file" name="gpkg" accept=".gpkg" required>
      <button type="submit">Analizuj projekt</button>
      <span>Katalog: {html.escape(CATALOG.name if CATALOG else 'brak')} | BELL: {html.escape(BELL.name if BELL else 'brak')}</span>
    </form>
    {content}
  </main>
</body>
</html>"""


def render_progress_page(job_id: str) -> str:
    escaped_job = html.escape(job_id)
    return f"""
    <section class="progress-panel">
      <h2>Analiza w toku</h2>
      <div class="progress-track"><div id="progress-bar" class="progress-bar"></div></div>
      <div class="progress-meta">
        <strong id="progress-percent">0%</strong>
        <span id="progress-message">Start</span>
      </div>
    </section>
    <script>
      const jobId = "{escaped_job}";
      const statusUrl = "/status/{escaped_job}";
      async function pollStatus() {{
        try {{
          const response = await fetch(statusUrl, {{ cache: "no-store" }});
          const data = await response.json();
          const percent = Math.max(0, Math.min(100, Number(data.percent || 0)));
          document.getElementById("progress-bar").style.width = percent + "%";
          document.getElementById("progress-percent").textContent = percent + "%";
          document.getElementById("progress-message").textContent = data.message || "";
          if (data.state === "done" && data.result_url) {{
            window.location.href = data.result_url;
            return;
          }}
          if (data.state === "error") {{
            document.getElementById("progress-message").textContent = data.error || "Błąd analizy";
            return;
          }}
        }} catch (error) {{
          document.getElementById("progress-message").textContent = "Czekam na status analizy...";
        }}
        window.setTimeout(pollStatus, 1000);
      }}
      pollStatus();
    </script>
    """


def render_result(result) -> str:
    links = ""
    if result.xlsx_path:
        links += f'<a class="button" href="{html.escape(output_href(result.xlsx_path))}">Pobierz XLSX</a>'
    if result.pdf_path:
        links += f'<a class="button" href="{html.escape(output_href(result.pdf_path))}">Pobierz PDF</a>'
    metrics = f"""
    <div class="grid">
      <div class="metric"><strong>F/X</strong><br>{html.escape(", ".join(result.project.f_numbers) or "brak")}</div>
      <div class="metric"><strong>HH</strong><br>{result.project.hh_total}</div>
      <div class="metric"><strong>Slupy uzyte</strong><br>{len(result.project.used_poles)}</div>
      <div class="metric"><strong>Pozycje BOM</strong><br>{len(result.order_rows)}</div>
      <div class="metric"><strong>DO POTWIERDZENIA</strong><br>{sum(1 for row in result.order_rows if row.status == "DO POTWIERDZENIA")}</div>
    </div>
    <p>{links}</p>
    """
    bom_rows = "".join(
        "<tr class='{cls}'><td>{lp}</td><td>{status}</td><td>{cat}</td><td>{sap}</td><td>{name}</td><td>{unit}</td><td>{qty}</td><td>{basis}</td></tr>".format(
            cls="warn" if row.status == "DO POTWIERDZENIA" else "",
            lp=row.lp,
            status=html.escape(row.status),
            cat=html.escape(row.category),
            sap=html.escape(row.sap),
            name=html.escape(row.name),
            unit=html.escape(row.unit),
            qty=html.escape(str(row.qty_order)),
            basis=html.escape(row.basis),
        )
        for row in result.order_rows
    )
    issues_rows = "".join(
        f"<tr><td>{html.escape(issue.topic)}</td><td>{html.escape(issue.description)}</td><td>{html.escape(issue.recommendation)}</td></tr>"
        for issue in result.issues
    )
    sap_rows = "".join(
        f"<tr><td>{html.escape(row.sap)}</td><td>{html.escape(row.name)}</td><td>{html.escape(row.unit)}</td><td>{html.escape(str(row.qty_order))}</td><td>{html.escape(row.status)}</td></tr>"
        for row in result.sap_rows
    )
    pole_rows = "".join(
        "<tr><td>{layer}</td><td>{pole}</td><td>{model}</td><td>{cables}</td><td>{distance}</td></tr>".format(
            layer=html.escape(pole.source_layer),
            pole=html.escape(pole.pole_id),
            model=html.escape(pole.model),
            cables=html.escape("; ".join(pole.matched_cables)),
            distance=html.escape(str(pole.distance_m)),
        )
        for pole in result.project.used_poles[:80]
    )
    return metrics + f"""
    <h2>Lista materiałów</h2>
    <table><thead><tr><th>Lp</th><th>Status</th><th>Kategoria</th><th>SAP</th><th>Nazwa</th><th>JM</th><th>Ilość</th><th>Podstawa</th></tr></thead><tbody>{bom_rows}</tbody></table>
    <h2>Do wyjaśnienia</h2>
    <table><thead><tr><th>Temat</th><th>Opis</th><th>Rekomendacja</th></tr></thead><tbody>{issues_rows}</tbody></table>
    <h2>Slupy uzyte</h2>
    <table><thead><tr><th>Warstwa</th><th>Id slupa</th><th>Model</th><th>Kable</th><th>Odleglosc m</th></tr></thead><tbody>{pole_rows}</tbody></table>
    <h2>SAP copy - szkic</h2>
    <table><thead><tr><th>SAP</th><th>Nazwa</th><th>JM</th><th>Ilość</th><th>Status</th></tr></thead><tbody>{sap_rows}</tbody></table>
    """


def main() -> int:
    parser = argparse.ArgumentParser(description="Lokalna web aplikacja FTTH BOM.")
    parser.add_argument("--host", default="127.0.0.1", help="Adres nasluchu, np. 127.0.0.1 lokalnie albo 0.0.0.0 po LAN.")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--pid-file", default=None, help="Opcjonalna sciezka do pliku PID dla STOP_APKE.bat.")
    args = parser.parse_args()
    OUTPUTS.mkdir(exist_ok=True)
    pid_file = resolve_pid_file(args.pid_file)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    write_pid_file(pid_file)
    print(f"FTTH BOM dziala pod adresem http://127.0.0.1:{args.port}")
    if args.host in {"0.0.0.0", ""}:
        print(f"Tryb LAN wlaczony: wejdz z drugiego komputera przez http://TWOJ_ADRES_IP:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nZatrzymano.")
    finally:
        server.server_close()
        remove_pid_file(pid_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
