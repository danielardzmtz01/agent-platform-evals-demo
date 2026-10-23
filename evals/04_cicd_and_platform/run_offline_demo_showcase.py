#!/usr/bin/env python3
"""Showcase Interactivo de Terminal para Demo en Vivo (4 Etapas en 1 Comando).

Ejecuta en tiempo real el motor de evaluación de ADK (`TrajectoryEvaluator`,
`ResponseEvaluator`, `financial_compliance_score`, `EnvironmentSimulation`) y
simula la salida visual de `Agent Platform Evals` (Rúbricas Adaptativas,
`hallucinations_v1` oración por oración y `GenerateLossClusters`), permitiendo
presentar toda la historia de las 16 diapositivas en vivo en <5 segundos,
incluso sin depender de la red del cliente.
"""

from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "evals" / "01_trajectory"))
sys.path.insert(0, str(_REPO_ROOT))

from corporate_concierge_agent import agent as concierge_agent  # noqa: E402
import financial_compliance  # noqa: E402
from google.adk.evaluation.eval_case import IntermediateData  # noqa: E402
from google.adk.evaluation.eval_case import Invocation  # noqa: E402
from google.adk.evaluation.eval_metrics import EvalMetric  # noqa: E402
from google.adk.evaluation.eval_metrics import ToolTrajectoryCriterion  # noqa: E402
from google.adk.evaluation.trajectory_evaluator import TrajectoryEvaluator  # noqa: E402
from google.genai import types as genai_types  # noqa: E402
from tabulate import tabulate  # noqa: E402


def _make_inv(user_text: str, tools: list[tuple[str, dict]], reply: str) -> Invocation:
  return Invocation(
      invocation_id="demo-inv",
      user_content=genai_types.Content(
          role="user", parts=[genai_types.Part.from_text(text=user_text)]
      ),
      final_response=genai_types.Content(
          role="model", parts=[genai_types.Part.from_text(text=reply)]
      ),
      intermediate_data=IntermediateData(
          tool_uses=[
              genai_types.FunctionCall(name=n, args=a) for n, a in tools
          ]
      ),
  )


def run_showcase() -> None:
  print("\n" + "━" * 88)
  print("🚀 DEMO EN VIVO: EVALUACIÓN DE AGENTES EN GOOGLE CLOUD (ADK + AGENT PLATFORM EVALS)")
  print("━" * 88)

  # ---------------------------------------------------------------------------
  # ETAPA 1: PILAR 1 - EVALUACIÓN DE TRAYECTORIA (SLIDE 6)
  # ---------------------------------------------------------------------------
  print("\n📌 [ETAPA 1 / SLIDE 6] PILAR 1: EVALUACIÓN DE TRAYECTORIA (EXACT vs. IN_ORDER + COMPLIANCE)")
  expected = [
      _make_inv(
          "Soy CUST-101 (PIN 4821), consulta mi saldo.",
          [
              ("verify_identity", {"customer_id": "CUST-101", "pin": "4821"}),
              ("get_account_balance", {"customer_id": "CUST-101"}),
          ],
          "Saldo verificado: $18,450.00 USD.",
      )
  ]
  actual_v1_buggy = [
      _make_inv(
          "Soy CUST-101 (PIN 4821), consulta mi saldo.",
          [("get_account_balance", {"customer_id": "CUST-101"})],
          "Tu saldo es $18,450.00 USD.",
      )
  ]
  actual_v2_exploratory = [
      _make_inv(
          "Soy CUST-101 (PIN 4821), consulta mi saldo.",
          [
              ("verify_identity", {"customer_id": "CUST-101", "pin": "4821"}),
              (
                  "search_flights",
                  {
                      "origin": "BOG",
                      "destination": "MIA",
                      "departure_date": "2026-11-15",
                  },
              ),
              ("get_account_balance", {"customer_id": "CUST-101"}),
          ],
          "Saldo verificado: $18,450.00 USD.",
      )
  ]
  actual_v3_optimal = expected

  exact_eval = TrajectoryEvaluator(
      eval_metric=EvalMetric(
          metric_name="tool_trajectory_avg_score",
          threshold=1.0,
          criterion=ToolTrajectoryCriterion(
              threshold=1.0, match_type=ToolTrajectoryCriterion.MatchType.EXACT
          ),
      )
  )
  inorder_eval = TrajectoryEvaluator(
      eval_metric=EvalMetric(
          metric_name="tool_trajectory_avg_score",
          threshold=1.0,
          criterion=ToolTrajectoryCriterion(
              threshold=1.0,
              match_type=ToolTrajectoryCriterion.MatchType.IN_ORDER,
          ),
      )
  )
  comp_metric = EvalMetric(
      metric_name="financial_compliance_score", threshold=1.0
  )

  rows_stage1 = []
  for label, candidate in [
      ("Agente v1 (Omite verify_identity)", actual_v1_buggy),
      ("Agente v2 (Paso exploratorio extra)", actual_v2_exploratory),
      ("Agente v3 (Ruta óptima regulada)", actual_v3_optimal),
  ]:
    r_ex = exact_eval.evaluate_invocations(candidate, expected)
    r_in = inorder_eval.evaluate_invocations(candidate, expected)
    r_cp = financial_compliance.financial_compliance_score(
        comp_metric, candidate, expected, None
    )
    def _fmt(res):
      icon = "🟢" if res.overall_eval_status.name == "PASSED" else "🔴"
      return f"{res.overall_score:.1f} ({icon} {res.overall_eval_status.name})"

    rows_stage1.append([
        label,
        _fmt(r_ex),
        _fmt(r_in),
        _fmt(r_cp),
    ])

  print(
      tabulate(
          rows_stage1,
          headers=[
              "Versión del Agente",
              "EXACT Match",
              "IN_ORDER Match",
              "Financial Compliance",
          ],
          tablefmt="fancy_grid",
      )
  )

  # ---------------------------------------------------------------------------
  # ETAPA 2: PILAR 2 - RÚBRICAS ADAPTATIVAS Y GROUNDEDNESS (SLIDES 7 Y 8)
  # ---------------------------------------------------------------------------
  print("\n📌 [ETAPA 2 / SLIDES 7 & 8] RÚBRICAS ADAPTATIVAS Y DETECCIÓN DE ALUCINACIONES (hallucinations_v1)")
  concierge_agent.reset_data()
  empty_tool_output = concierge_agent.search_flights("BOG", "NRT", "2026-11-20")
  print(f"   🔍 Salida real de herramienta `search_flights('BOG', 'NRT', '2026-11-20')`: {empty_tool_output}")

  sentences_audit = [
      [
          "1. 'Consulté la disponibilidad de vuelos entre Bogotá (BOG) y Tokio (NRT) para el 2026-11-20.'",
          "🟢 SUPPORTED",
          "Respaldado por args y retorno de search_flights.",
      ],
      [
          "2. 'Actualmente no existen vuelos directos disponibles en el sistema para esa fecha.'",
          "🟢 SUPPORTED",
          "Respaldado por 'flights': [] en el payload JSON.",
      ],
      [
          "3. [Agente v1 Buggy] 'Sin embargo, puedes tomar el vuelo GA-902 a las 14:30 por $1,120 USD.'",
          "🔴 UNSUPPORTED (Alucinación)",
          "Fallo detectado: 'flights' está vacío []; GA-902 no existe.",
      ],
  ]
  print(
      tabulate(
          sentences_audit,
          headers=[
              "Oración Segmentada (Sentence Segmenter)",
              "Veredicto (Sentence Validator)",
              "Evidencia en Traza JSON",
          ],
          tablefmt="fancy_grid",
      )
  )

  # ---------------------------------------------------------------------------
  # ETAPA 3: DIAGNÓSTICO INTELIGENTE - AUTO-LOSS CLUSTERING (SLIDE 13)
  # ---------------------------------------------------------------------------
  print("\n📌 [ETAPA 3 / SLIDE 13] AGENT PLATFORM EVALS: AUTO-LOSS CLUSTERING (`GenerateLossClusters`)")
  loss_clusters = [
      [
          "🔴 Clúster 1 (42% de fallos)",
          "search_flights recibe fechas '15/11/2026' en vez de 'YYYY-MM-DD'",
          "Reforzar docstring ISO 8601 en search_flights y system_instruction",
          "100% Resuelto en v3",
      ],
      [
          "🟠 Clúster 2 (28% de fallos)",
          "Omisión de verify_identity antes de get_account_balance",
          "Regla obligatoria #1 en system_instruction + compuerta pytest",
          "100% Resuelto en v3",
      ],
      [
          "🟡 Clúster 3 (15% de fallos)",
          "Alucinación de vuelos cuando search_flights devuelve lista vacía []",
          "Instrucción explícita de manejo de [] + métrica hallucinations_v1",
          "100% Resuelto en v3",
      ],
  ]
  print(
      tabulate(
          loss_clusters,
          headers=[
              "Clúster de Causa Raíz",
              "Patrón Detectado por AutoRaters",
              "Acción de Ingeniería Aplicada",
              "Estado Post-Fix",
          ],
          tablefmt="fancy_grid",
      )
  )
  print("\n✅ Demo completada con éxito. Ejecuta `.venv/bin/pytest -v` para ver la compuerta CI/CD en acción.\n")


if __name__ == "__main__":
  run_showcase()
