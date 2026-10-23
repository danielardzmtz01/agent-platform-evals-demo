# Demo End-to-End: Evaluación de Agentes en Google Cloud (ADK + Agent Platform Evals)

Proyecto ejecutable alineado 1:1 con la presentación **"De Prototipos a Producción Confiable: Evaluación de Agentes de IA en Google Cloud"**.

## Estructura del Proyecto

- `corporate_concierge_agent/`: Agente ADK de Finanzas y Viajes Corporativos (`verify_identity`, `get_account_balance`, `search_flights`, `book_corporate_flight`, `create_support_ticket`, `get_support_ticket`).
- `evals/01_trajectory/`:
  - `balance_security_check.test.json`: Unit test (`.test.json`) para `pytest` y `adk eval`.
  - `corporate_travel_flow.evalset.json`: Suite multi-caso (`.evalset.json`) con los 3 escenarios críticos de Slide 6 y Slide 13.
  - `eval_config_exact.json` y `eval_config_in_order.json`: Configuraciones `EXACT` e `IN_ORDER`.
  - `financial_compliance.py`: Métrica personalizada determinista (`custom_metrics`).
- `evals/02_autoraters_rubrics/eval_config_rubrics.json`: Configuración de `hallucinations_v1`, `rubric_based_final_response_quality_v1` y `rubric_based_tool_use_quality_v1`.
- `evals/03_simulation_chaos/`:
  - `dynamic_personas.evalset.json` y `eval_config_user_sim.json`: Escenarios multi-turno con `LlmBackedUserSimulator` (`NOVICE`, `EXPERT`, `EVALUATOR`).
  - `run_chaos_simulation.py`: Demostración de `EnvironmentSimulation` (inyección `HTTP 503` y mocking con estado `MOCK_STRATEGY_TOOL_SPEC`).
- `evals/04_cicd_and_platform/`:
  - `test_agent_evals_cicd.py`: Compuerta de CI/CD en `pytest` (Slide 12).
  - `run_offline_demo_showcase.py`: Showcase interactivo en terminal de los 4 bloques de la presentación (<2 segundos).
- `notebook_agent_platform_evals_demo.ipynb`: Notebook interactivo de principio a fin.

## Configuración Activa (GCP Project `evals-demos`)

El archivo `.env` ya está configurado automáticamente para el proyecto **`evals-demos`**:

```dotenv
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=evals-demos
GOOGLE_CLOUD_LOCATION=global
DEMO_AGENT_MODEL=gemini-3.5-flash
```

## Comandos Rápidos para la Demo

```bash
cd /usr/local/google/home/danielardzmtz/demos/agent_platform_evals_demo

# 1. Showcase completo instantáneo (Tablas de Trayectoria, Groundedness y Auto-Loss Clustering)
.venv/bin/python evals/04_cicd_and_platform/run_offline_demo_showcase.py

# 2. Compuerta de CI/CD con pytest (Slide 12)
.venv/bin/pytest evals/04_cicd_and_platform/test_agent_evals_cicd.py -v

# 3. Chaos Engineering & Environment Simulation HTTP 503 (Slide 10)
.venv/bin/python evals/03_simulation_chaos/run_chaos_simulation.py

# 4. Interfaz Visual ADK Web (Slide 12 - requiere GOOGLE_API_KEY o GOOGLE_GENAI_USE_VERTEXAI=TRUE)
.venv/bin/adk web . --port 8000

# 5. CLI de ADK Eval con Trayectoria + Custom Metric (Slides 6 y 12)
PYTHONPATH=evals/01_trajectory .venv/bin/adk eval corporate_concierge_agent \
  evals/01_trajectory/corporate_travel_flow.evalset.json \
  --config_file_path evals/01_trajectory/eval_config_in_order.json \
  --print_detailed_results
```
