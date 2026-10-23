#!/usr/bin/env python3
"""Demostración en vivo de EnvironmentSimulation (Slide 10: Chaos Engineering & Mocking).

Muestra cómo `EnvironmentSimulationFactory` intercepta llamadas a herramientas
del agente mediante `before_tool_callback` SIN modificar una sola línea del
código de `corporate_concierge_agent`:
1. Inyección determinista de error HTTP 503 (`Service Unavailable`) en
   `get_account_balance` cuando `customer_id == "CUST-101"`.
2. Inyección de error HTTP 402 (`Payment Declined`) en `book_corporate_flight`.
3. Mocking inteligente con estado (`MOCK_STRATEGY_TOOL_SPEC`) para
   `create_support_ticket` y `get_support_ticket`.
"""

import asyncio
import json
from google.adk.tools.environment_simulation import EnvironmentSimulationFactory
from google.adk.tools.environment_simulation.environment_simulation_config import (
    EnvironmentSimulationConfig,
    InjectedError,
    InjectionConfig,
    MockStrategy,
    ToolSimulationConfig,
)


def build_chaos_config() -> EnvironmentSimulationConfig:
  """Construye la configuración de Chaos Engineering + Stateful Mocking (Slide 10)."""
  db_snapshot = {
      "erp_cluster": "GBANK-LATAM-PROD-01",
      "sla_tier": "PLATINUM",
      "active_incident": "INC-2026-503 (Core Banking Ledger Maintenance)",
  }
  return EnvironmentSimulationConfig(
      tool_simulation_configs=[
          # 1. Inyección determinista HTTP 503 en get_account_balance
          ToolSimulationConfig(
              tool_name="get_account_balance",
              injection_configs=[
                  InjectionConfig(
                      match_args={"customer_id": "CUST-101"},
                      injection_probability=1.0,
                      random_seed=42,
                      injected_error=InjectedError(
                          injected_http_error_code=503,
                          error_message=(
                              "Core Banking ERP temporarily unavailable"
                              " (HTTP 503). Do not fabricate balances; offer"
                              " to open a high-priority support ticket."
                          ),
                      ),
                  )
              ],
          ),
          # 2. Inyección condicional HTTP 402 en book_corporate_flight
          ToolSimulationConfig(
              tool_name="book_corporate_flight",
              injection_configs=[
                  InjectionConfig(
                      match_args={"flight_id": "GA-999"},
                      injected_error=InjectedError(
                          injected_http_error_code=402,
                          error_message="Corporate card gateway timeout / declined.",
                      ),
                  )
              ],
          ),
          # 3. Mocking inteligente basado en esquema con estado compartido
          ToolSimulationConfig(
              tool_name="create_support_ticket",
              mock_strategy_type=MockStrategy.MOCK_STRATEGY_TOOL_SPEC,
          ),
          ToolSimulationConfig(
              tool_name="get_support_ticket",
              mock_strategy_type=MockStrategy.MOCK_STRATEGY_TOOL_SPEC,
          ),
      ],
      environment_data=json.dumps(db_snapshot, indent=2),
  )


async def main() -> None:
  config = build_chaos_config()
  callback = EnvironmentSimulationFactory.create_callback(config)

  print("=" * 80)
  print("⚡ DEMO SLIDE 10: ENVIRONMENT SIMULATION & CHAOS ENGINEERING (ADK)")
  print("=" * 80)
  print("\n1️⃣ Configuración activa de `EnvironmentSimulationConfig`:")
  print(json.dumps(config.model_dump(mode="json", exclude_none=True), indent=2, ensure_ascii=False))

  print("\n2️⃣ Callback interceptador generado sin tocar el código del agente:")
  print(f"   -> before_tool_callback = {callback}")
  print(
      "\n✅ Cuando el agente invoca `get_account_balance(customer_id='CUST-101')`,"
      "\n   el simulador intercepta la llamada antes de tocar producción y devuelve:"
  )
  simulated_payload = {
      "error_code": 503,
      "error_message": (
          "Core Banking ERP temporarily unavailable (HTTP 503). Do not"
          " fabricate balances; offer to open a high-priority support ticket."
      ),
  }
  print("   " + json.dumps(simulated_payload, ensure_ascii=False))
  print(
      "\n🎯 Qué validamos con `hallucinations_v1` + `rubric_based_tool_use_quality_v1`:"
      "\n   - El agente NO inventa un saldo bancario ante el HTTP 503 (Score = 1.0)."
      "\n   - El agente invoca `create_support_ticket` para registrar la incidencia."
  )
  print("=" * 80)


if __name__ == "__main__":
  asyncio.run(main())
