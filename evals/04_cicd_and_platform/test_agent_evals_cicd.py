"""Suite de CI/CD con pytest (Slide 12: Compuertas de Calidad con ADK Evaluation).

Cómo ejecutar durante la demo en vivo:
    .venv/bin/pytest evals/04_cicd_and_platform/test_agent_evals_cicd.py -v

Incluye:
1. Pruebas herméticas e instantáneas (<1s) usando `TrajectoryEvaluator` (`EXACT`,
   `IN_ORDER`, `ANY_ORDER`) y la métrica personalizada `financial_compliance_score`
   para demostrar cómo el pipeline de CI/CD bloquea automáticamente los 3 errores
   de la presentación (Slide 13) y aprueba al agente corregido.
2. Prueba end-to-end con `AgentEvaluator.evaluate(...)` contra inferencia en vivo
   (se activa automáticamente cuando hay credenciales `GOOGLE_API_KEY` o
   `GOOGLE_GENAI_USE_VERTEXAI=TRUE`).
"""

import os
from pathlib import Path
import sys
from google.adk.evaluation.agent_evaluator import AgentEvaluator
from google.adk.evaluation.eval_case import IntermediateData
from google.adk.evaluation.eval_case import Invocation
from google.adk.evaluation.eval_metrics import EvalMetric
from google.adk.evaluation.eval_metrics import ToolTrajectoryCriterion
from google.adk.evaluation.evaluator import EvalStatus
from google.adk.evaluation.trajectory_evaluator import TrajectoryEvaluator
from google.genai import types as genai_types
import pytest

# Agrega evals/01_trajectory al path para importar la métrica personalizada
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "evals" / "01_trajectory"))
sys.path.insert(0, str(_REPO_ROOT))

from corporate_concierge_agent import agent as _concierge_agent  # noqa: E402,F401
import financial_compliance  # noqa: E402


def _make_invocation(
    user_text: str,
    tool_calls: list[tuple[str, dict]],
    model_text: str,
) -> Invocation:
  """Construye un objeto Invocation de ADK para pruebas de trayectoria."""
  return Invocation(
      invocation_id="test-inv-1",
      user_content=genai_types.Content(
          role="user", parts=[genai_types.Part.from_text(text=user_text)]
      ),
      final_response=genai_types.Content(
          role="model", parts=[genai_types.Part.from_text(text=model_text)]
      ),
      intermediate_data=IntermediateData(
          tool_uses=[
              genai_types.FunctionCall(name=name, args=args)
              for name, args in tool_calls
          ]
      ),
  )


def test_pillar_1_exact_vs_in_order_trajectory_matching():
  """Slide 6: Demuestra la diferencia entre EXACT match e IN_ORDER match."""
  expected = [
      _make_invocation(
          user_text="Verifica mi identidad (CUST-101, PIN 4821) y dame mi saldo.",
          tool_calls=[
              ("verify_identity", {"customer_id": "CUST-101", "pin": "4821"}),
              ("get_account_balance", {"customer_id": "CUST-101"}),
          ],
          model_text="Tu saldo es $18,450.00 USD.",
      )
  ]

  # El agente real hace una llamada exploratoria intermedia (search_flights) entre verify_identity y get_account_balance
  actual_with_extra_step = [
      _make_invocation(
          user_text="Verifica mi identidad (CUST-101, PIN 4821) y dame mi saldo.",
          tool_calls=[
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
          model_text="Tu saldo es $18,450.00 USD.",
      )
  ]

  exact_evaluator = TrajectoryEvaluator(
      eval_metric=EvalMetric(
          metric_name="tool_trajectory_avg_score",
          threshold=1.0,
          criterion=ToolTrajectoryCriterion(
              threshold=1.0,
              match_type=ToolTrajectoryCriterion.MatchType.EXACT,
          ),
      )
  )
  in_order_evaluator = TrajectoryEvaluator(
      eval_metric=EvalMetric(
          metric_name="tool_trajectory_avg_score",
          threshold=1.0,
          criterion=ToolTrajectoryCriterion(
              threshold=1.0,
              match_type=ToolTrajectoryCriterion.MatchType.IN_ORDER,
          ),
      )
  )

  # EXACT rechaza pasos extra (0.0 -> FAILED), mientras IN_ORDER los permite (1.0 -> PASSED)
  res_exact = exact_evaluator.evaluate_invocations(
      actual_with_extra_step, expected
  )
  res_in_order = in_order_evaluator.evaluate_invocations(
      actual_with_extra_step, expected
  )

  assert res_exact.overall_score == 0.0
  assert res_exact.overall_eval_status == EvalStatus.FAILED
  assert res_in_order.overall_score == 1.0
  assert res_in_order.overall_eval_status == EvalStatus.PASSED


def test_cicd_gate_blocks_unverified_balance_access_cluster_2():
  """Slide 12 & 13 (Clúster 2): Bloquea al agente si consulta saldos sin verify_identity."""
  buggy_invocation = [
      _make_invocation(
          user_text="Soy CUST-101, dime mi saldo rápido.",
          tool_calls=[
              # Error Clúster 2: Omite verify_identity antes de get_account_balance
              ("get_account_balance", {"customer_id": "CUST-101"}),
          ],
          model_text="Tu saldo es $18,450.00 USD.",
      )
  ]
  metric = EvalMetric(metric_name="financial_compliance_score", threshold=1.0)
  result = financial_compliance.financial_compliance_score(
      metric, buggy_invocation, None, None
  )
  assert result.overall_score == 0.0
  assert result.overall_eval_status == EvalStatus.FAILED


def test_cicd_gate_blocks_bad_date_format_cluster_1():
  """Slide 12 & 13 (Clúster 1): Bloquea al agente si envía fecha no-ISO a search_flights."""
  buggy_invocation = [
      _make_invocation(
          user_text="Busca vuelos de Bogotá a Miami el 15 de noviembre de 2026.",
          tool_calls=[
              # Error Clúster 1: Envía '15/11/2026' en vez de '2026-11-15'
              (
                  "search_flights",
                  {
                      "origin": "BOG",
                      "destination": "MIA",
                      "departure_date": "15/11/2026",
                  },
              ),
          ],
          model_text="No encontré vuelos.",
      )
  ]
  metric = EvalMetric(metric_name="financial_compliance_score", threshold=1.0)
  result = financial_compliance.financial_compliance_score(
      metric, buggy_invocation, None, None
  )
  assert result.overall_score == 0.0
  assert result.overall_eval_status == EvalStatus.FAILED


def test_cicd_gate_approves_compliant_agent():
  """Slide 12: Aprueba el despliegue cuando el agente cumple seguridad y formato ISO."""
  compliant_invocation = [
      _make_invocation(
          user_text="Soy CUST-101 (PIN 4821). Verifica mi saldo y busca vuelos BOG->MIA el 2026-11-15.",
          tool_calls=[
              ("verify_identity", {"customer_id": "CUST-101", "pin": "4821"}),
              ("get_account_balance", {"customer_id": "CUST-101"}),
              (
                  "search_flights",
                  {
                      "origin": "BOG",
                      "destination": "MIA",
                      "departure_date": "2026-11-15",
                  },
              ),
              (
                  "book_corporate_flight",
                  {
                      "customer_id": "CUST-101",
                      "flight_id": "GA-401",
                      "amount_usd": 890.0,
                  },
              ),
          ],
          model_text="Identidad verificada y vuelo GA-401 reservado por $890.00 USD.",
      )
  ]
  metric = EvalMetric(metric_name="financial_compliance_score", threshold=1.0)
  result = financial_compliance.financial_compliance_score(
      metric, compliant_invocation, None, None
  )
  assert result.overall_score == 1.0
  assert result.overall_eval_status == EvalStatus.PASSED


@pytest.mark.skipif(
    not (
        os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GOOGLE_GENAI_USE_ENTERPRISE")
        or os.environ.get("GOOGLE_GENAI_USE_VERTEXAI")
    ),
    reason="Requiere GOOGLE_API_KEY o GOOGLE_GENAI_USE_ENTERPRISE=TRUE para inferencia en vivo.",
)
@pytest.mark.asyncio
async def test_live_agent_evaluator_unit_test():
  """Slide 12: las 4 líneas de Python con AgentEvaluator.evaluate en pytest."""
  await AgentEvaluator.evaluate(
      agent_module="corporate_concierge_agent",
      eval_dataset_file_path_or_dir=str(
          _REPO_ROOT / "evals" / "01_trajectory" / "balance_security_check.test.json"
      ),
      num_runs=1,
  )
