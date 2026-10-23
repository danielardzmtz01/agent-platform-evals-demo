#!/usr/bin/env python3
"""Servidor HTTP para la Demo Estilo GitHub Enterprise + Reporte agent-eval (Puerto 8086).

Sirve:
- GET /github.html : Portal estilo GitHub Enterprise (gbank-gairways/corporate-concierge-agent)
- GET /report.html : Reporte interactivo de agent-eval CLI
- GET /raw/<path>  : Archivos reales completos del repositorio de demo en texto plano / JSON
- POST /api/run-workflow : Ejecuta en tiempo real pytest, run_chaos_simulation.py o
  run_offline_demo_showcase.py y devuelve la salida real a la consola de GitHub Actions.
"""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import time

REPO_ROOT = Path(__file__).resolve().parent
REPORT_DIR = (
    REPO_ROOT
    / "corporate_concierge_agent"
    / "tests"
    / "eval"
    / "results"
    / "baseline_fintech"
)
VENV_PYTHON = str(REPO_ROOT / ".venv" / "bin" / "python")
VENV_PYTEST = str(REPO_ROOT / ".venv" / "bin" / "pytest")

ALLOWED_RAW_FILES = {
    "corporate_concierge_agent/agent.py",
    "evals/01_trajectory/corporate_travel_flow.evalset.json",
    "evals/01_trajectory/financial_compliance.py",
    "evals/01_trajectory/eval_config_in_order.json",
    "evals/02_autoraters_rubrics/eval_config_rubrics.json",
    "evals/03_simulation_chaos/dynamic_personas.evalset.json",
    "evals/03_simulation_chaos/run_chaos_simulation.py",
    "evals/04_cicd_and_platform/test_agent_evals_cicd.py",
    "corporate_concierge_agent/tests/eval/metrics/metric_definitions.json",
    "corporate_concierge_agent/tests/eval/dataset.jsonl",
    "corporate_concierge_agent/tests/eval/results/baseline_fintech/gemini_analysis.md",
    "corporate_concierge_agent/tests/eval/results/baseline_fintech/question_answer_log.md",
}


class DemoGitHubHandler(SimpleHTTPRequestHandler):
  """Manejador HTTP con soporte para archivos reales (/raw/), estáticos y workflows."""

  def __init__(self, *args, **kwargs):
    super().__init__(*args, directory=str(REPORT_DIR), **kwargs)

  def end_headers(self):
    self.send_header(
        "Cache-Control", "no-store, no-cache, must-revalidate, max-age=0"
    )
    self.send_header("Pragma", "no-cache")
    self.send_header("Expires", "0")
    super().end_headers()

  def do_GET(self):
    if self.path.startswith("/raw/"):
      rel_path = self.path[len("/raw/") :].split("?")[0].lstrip("/")
      if rel_path in ALLOWED_RAW_FILES:
        target = (REPO_ROOT / rel_path).resolve()
        if target.exists() and target.is_file():
          content = target.read_bytes()
          self.send_response(200)
          self.send_header("Content-Type", "text/plain; charset=utf-8")
          self.send_header("Content-Length", str(len(content)))
          self.end_headers()
          self.wfile.write(content)
          return
      self.send_error(404, f"Raw file '{rel_path}' not found")
      return
    super().do_GET()

  def do_POST(self):
    if self.path == "/api/run-workflow":
      length = int(self.headers.get("Content-Length", "0"))
      raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
      try:
        payload = json.loads(raw_body)
      except json.JSONDecodeError:
        payload = {}

      wf = payload.get("workflow", "pytest")
      if wf == "chaos":
        cmd = [VENV_PYTHON, "evals/03_simulation_chaos/run_chaos_simulation.py"]
        cmd_display = "$ .venv/bin/python evals/03_simulation_chaos/run_chaos_simulation.py\n"
      elif wf == "showcase":
        cmd = [
            VENV_PYTHON,
            "evals/04_cicd_and_platform/run_offline_demo_showcase.py",
        ]
        cmd_display = "$ .venv/bin/python evals/04_cicd_and_platform/run_offline_demo_showcase.py\n"
      else:
        cmd = [
            VENV_PYTEST,
            "evals/04_cicd_and_platform/test_agent_evals_cicd.py",
            "-v",
            "-k",
            "not live",
        ]
        cmd_display = "$ .venv/bin/pytest evals/04_cicd_and_platform/test_agent_evals_cicd.py -v\n"

      t0 = time.time()
      env = dict(os.environ)
      proc = subprocess.run(
          cmd,
          cwd=str(REPO_ROOT),
          env=env,
          capture_output=True,
          text=True,
          timeout=30,
          check=False,
      )
      duration = round(time.time() - t0, 2)
      response_data = {
          "workflow": wf,
          "returncode": proc.returncode,
          "duration_s": duration,
          "output": cmd_display + (proc.stdout or "") + (proc.stderr or ""),
      }
      body = json.dumps(response_data, ensure_ascii=False).encode("utf-8")
      self.send_response(200)
      self.send_header("Content-Type", "application/json; charset=utf-8")
      self.send_header("Content-Length", str(len(body)))
      self.end_headers()
      self.wfile.write(body)
      return

    self.send_error(404, "Endpoint not found")


def main():
  server = ThreadingHTTPServer(("0.0.0.0", 8086), DemoGitHubHandler)
  print("Serving GitHub Enterprise Demo UI & agent-eval report on 0.0.0.0:8086...")
  server.serve_forever()


if __name__ == "__main__":
  main()
