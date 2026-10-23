# Deep Technical Diagnosis: Corporate Concierge Agent Evaluation

## 1. Executive Synthesis
The `corporate_concierge_agent` demonstrates exceptionally high reliability and strict adherence to corporate constraints, achieving a perfect `1.0` average in LLM-judged `trajectory_accuracy` and `corporate_policy_compliance`, alongside a `100%` deterministic `tool_success_rate`. However, a misalignment exists between the agent’s strictly defined operational bounds and the expected "helpfulness" standard defined in the `general_quality` rubric, which pulled the average quality score down to `0.67`. Furthermore, infrastructural metrics indicate inefficiencies in context management, specifically a `0.0%` cache hit rate, leading to elevated token costs and latency.

This report synthesizes the evaluation metrics, links them to the underlying implementation in `agent.py`, and provides concrete optimization strategies using ADK Design Patterns.

---

## 2. Metric Diagnosis & Source Code Analysis

### 2.1. Trajectory Accuracy & Tool Execution (High Performance)
**Metrics Analyzed:** `trajectory_accuracy` (LLM-judged: 1.0), `tool_success_rate` (Deterministic: 1.0)

The agent excels at tool selection and sequencing. The deterministic `tool_success_rate` of `1.0` confirms that all tool invocations were syntactically correct and successfully processed without throwing Python exceptions. 

This is corroborated by the LLM-judged `trajectory_accuracy`, which evaluates the logical path taken by the agent. In `case_001_saldo_cust101`, the agent correctly sequenced `verify_identity` before `get_account_balance`, aligning perfectly with Rule 1 of `_FIXED_INSTRUCTION` in `agent.py`: *"Antes de llamar a `get_account_balance`... SIEMPRE debes haber verificado la identidad"*. The LLM judge's explanation explicitly validates this: *"The agent verified the user's identity and retrieved the account balance without taking any detours..."*

**Synthesis:** The functional boundaries established in `agent.py` via tools like `verify_identity` and `search_flights` are highly effective, resulting in zero hallucinations regarding tool choice.

### 2.2. Quality vs. Policy Compliance Misalignment (The 0.0 Outlier)
**Metrics Analyzed:** `general_quality` (LLM-judged: 0.67 average), `corporate_policy_compliance` (LLM-judged: 1.0)

While cases 001 and 002 achieved perfect 1.0 scores across all LLM-judged metrics, `case_003_ruta_sin_vuelos_bog_nrt` exposed a critical conflict between the agent's system prompt and the `general_quality` rubric. 

In this case, the user requests flights from BOG to NRT. The tool `search_flights` deterministically returns `[]`. The agent responds: *"No se encontraron vuelos corporativos disponibles para la ruta de Bogotá (BOG) a Tokio Narita (NRT)..."* 

*   **Why it scored 1.0 on `corporate_policy_compliance`:** The LLM judge notes that the agent *"es exacta frente a la realidad del mercado y las herramientas al no inventar vuelos directos inexistentes"*. This maps directly to Rule 3 in `agent.py`'s `_FIXED_INSTRUCTION`: *"CERO ALUCINACIONES ANTE LISTAS VACÍAS... NUNCA inventes vuelos, horarios ni precios."*
*   **Why it scored 0.0 on `general_quality`:** The LLM judge expects proactive concierge behavior, stating: *"While it directly addresses the query... it lacks helpfulness and actionable details. A professional corporate concierge should explain why flights are unavailable... and offer alternative routing options."*

**Synthesis:** Because `general_quality` is an LLM-judged rubric based on semantic expectations of "helpfulness" rather than rigid code compliance, the agent was penalized for strictly following its instructions. The prompt prioritizes safety (avoiding hallucinations) at the cost of proactive customer service.

### 2.3. Caching and Latency Inefficiencies
**Metrics Analyzed:** `cache_efficiency.cache_hit_rate` (Deterministic: 0.0), `latency_metrics.average_turn_latency_seconds` (Deterministic: 4.82s)

The deterministic token counting reveals that the agent generated `3357.3` fresh prompt tokens on average, with a `0.0` cache hit rate. Consequently, `latency_metrics.llm_latency_seconds` sits at an average of `4.79s`, representing nearly 100% of the total latency (since tool execution latency is virtually zero at `0.0008s`).

**Synthesis:** In `agent.py`, the massive `_FIXED_INSTRUCTION` block (which contains detailed operating procedures) is being passed into the dynamic `instruction` parameter of the `Agent` class. Because this prompt is injected as fresh context on every turn rather than utilizing a static system prefix, the Google Cloud infrastructure cannot leverage prefix caching. This leads to redundant token processing costs (`0.0050 USD` estimated cost) and elevated Time to First Token (TTFT).

---

## 3. Recommended Next Steps

Based on the ADK Design Patterns reference, I recommend the following actionable optimizations for the development team.

### Recommendation 1: Fix Instruction/Rubric Alignment for Ambiguous Scenarios
*   **Optimization Pillar:** Offload / Prompt Engineering
*   **ADK Pattern:** *Agent doesn't clarify ambiguous requests / Low general_quality due to rubric failures on clarification*
*   **Action:** We must resolve the conflict between the strict non-hallucination instruction and the helpfulness rubric. Update `_FIXED_INSTRUCTION` in `agent.py` to instruct the agent to offer valid alternative strategies when a tool returns empty data, without hallucinating specific data.
*   **Code Change:**
    ```python
    # In agent.py, update _FIXED_INSTRUCTION Rule 3:
    _FIXED_INSTRUCTION = """...
    3. CERO ALUCINACIONES ANTE LISTAS VACÍAS: Si `search_flights` devuelve `"flights": []`, informa claramente que no hay vuelos directos. NUNCA inventes vuelos, horarios ni precios. SIN EMBARGO, debes actuar como un concierge proactivo: sugiere amablemente al usuario buscar opciones con escalas o verificar fechas alternativas.
    ..."""
    ```
*   **Expected Metric Impact:** Should raise the `general_quality` score for edge-case scenarios (like `case_003`) from 0.0 to 1.0, pulling the overall average up to >= 0.90, without sacrificing `corporate_policy_compliance`.

### Recommendation 2: Enable Prompt Caching for System Instructions
*   **Optimization Pillar:** Cache
*   **ADK Pattern:** *Low cache hit rate, high cost*
*   **Action:** Move the heavy, static ruleset (`_FIXED_INSTRUCTION`) into the `global_instruction` parameter of the `Agent` definition. This ensures the LLM backend treats it as a static prefix, caching it across turns.
*   **Code Change:**
    ```python
    # In agent.py, modify the Agent instantiation:
    root_agent = Agent(
        name="corporate_concierge_agent",
        model=os.environ.get("DEMO_AGENT_MODEL", "gemini-3.5-flash"),
        description="Concierge corporativo para consulta de saldos y viajes.",
        # Move the heavy static text to global_instruction to enable caching
        global_instruction=(
            _BUGGY_INSTRUCTION 
            if os.environ.get("DEMO_AGENT_MODE") == "buggy" 
            else _FIXED_INSTRUCTION
        ),
        # Keep instruction for lightweight, dynamic per-session context if needed
        instruction="Por favor atiende al siguiente usuario.", 
        tools=[
            verify_identity,
            get_account_balance,
            search_flights,
            book_corporate_flight,
            create_support_ticket,
            get_support_ticket,
        ],
    )
    ```
*   **Expected Metric Impact:** Will increase `cache_efficiency.cache_hit_rate` from 0.0 to >80% on multi-turn conversations (like `case_001` which took 3 LLM calls). This will decrease `token_usage.estimated_cost_usd` and reduce `latency_metrics.total_latency_seconds` by minimizing prompt processing time.