"""Agente Corporativo de Finanzas y Viajes (ADK) para Demo de Agent Platform Evals.

Alineado 1:1 con los casos de uso de la presentación "De Prototipos a Producción
Confiable: Evaluación de Agentes de IA en Google Cloud":
- Verificación obligatoria de identidad (`verify_identity`) antes de consultar saldos
  (`get_account_balance`) o reservar vuelos (`book_corporate_flight`).
- Búsqueda de vuelos (`search_flights`) con validación estricta de fecha `YYYY-MM-DD`
  y manejo de listas vacías `[]` sin alucinar opciones inexistentes.
- Creación y seguimiento de tickets con estado (`create_support_ticket`,
  `get_support_ticket`) para demostrar `EnvironmentSimulation` e inyección HTTP 503.
"""

import os
from pathlib import Path
import re
from typing import Any
from dotenv import load_dotenv
from google.adk import Agent

load_dotenv(Path(__file__).resolve().parent / ".env")
os.environ.setdefault("GOOGLE_GENAI_USE_ENTERPRISE", "TRUE")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "evals-demos")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")

_ACCOUNTS: dict[str, dict[str, Any]] = {}
_FLIGHTS_DB: list[dict[str, Any]] = []
_TICKETS_DB: dict[str, dict[str, Any]] = {}
_VERIFIED_CUSTOMERS: set[str] = set()


def reset_data() -> None:
  """Reinicia el estado en memoria entre casos de evaluación (llamado por `adk eval`)."""
  global _ACCOUNTS, _FLIGHTS_DB, _TICKETS_DB, _VERIFIED_CUSTOMERS
  _VERIFIED_CUSTOMERS = set()
  _ACCOUNTS = {
      "CUST-101": {
          "name": "Daniela Rodríguez",
          "pin": "4821",
          "checking_balance_usd": 18450.00,
          "corporate_card_available_usd": 5000.00,
          "policy_max_flight_usd": 2500.00,
          "tier": "Platinum Executive",
      },
      "CUST-202": {
          "name": "Carlos Mendoza",
          "pin": "9930",
          "checking_balance_usd": 4200.00,
          "corporate_card_available_usd": 1800.00,
          "policy_max_flight_usd": 2500.00,
          "tier": "Gold Corporate",
      },
  }
  _FLIGHTS_DB = [
      {
          "flight_id": "GA-401",
          "origin": "BOG",
          "destination": "MIA",
          "departure_date": "2026-11-15",
          "airline": "GAirways",
          "class": "Business",
          "price_usd": 890.00,
          "seats_available": 4,
      },
      {
          "flight_id": "GA-405",
          "origin": "BOG",
          "destination": "MIA",
          "departure_date": "2026-11-15",
          "airline": "GAirways",
          "class": "Economy Plus",
          "price_usd": 420.00,
          "seats_available": 9,
      },
      {
          "flight_id": "GA-810",
          "origin": "MEX",
          "destination": "SFO",
          "departure_date": "2026-11-18",
          "airline": "GAirways",
          "class": "Business",
          "price_usd": 1150.00,
          "seats_available": 2,
      },
  ]
  _TICKETS_DB = {}


reset_data()


def verify_identity(customer_id: str, pin: str) -> dict[str, Any]:
  """Verifica la identidad del cliente corporativo mediante su ID y PIN de 4 dígitos.

  SIEMPRE debe invocarse antes de consultar saldos (`get_account_balance`) o
  reservar vuelos con cargo a tarjeta corporativa (`book_corporate_flight`).

  Args:
    customer_id: Identificador del cliente (ej. 'CUST-101').
    pin: PIN de seguridad de 4 dígitos proporcionado por el usuario.
  """
  account = _ACCOUNTS.get(customer_id)
  if not account:
    return {"verified": False, "error": f"Customer '{customer_id}' not found."}
  if str(account["pin"]) != str(pin):
    return {"verified": False, "error": "Invalid security PIN."}
  _VERIFIED_CUSTOMERS.add(customer_id)
  return {
      "verified": True,
      "customer_id": customer_id,
      "customer_name": account["name"],
      "tier": account["tier"],
  }


def get_account_balance(customer_id: str) -> dict[str, Any]:
  """Consulta el saldo bancario y el cupo disponible en la tarjeta corporativa.

  Requiere que `verify_identity` se haya ejecutado previamente en la sesión.

  Args:
    customer_id: Identificador del cliente (ej. 'CUST-101').
  """
  account = _ACCOUNTS.get(customer_id)
  if not account:
    return {"error": f"Customer '{customer_id}' not found."}
  return {
      "customer_id": customer_id,
      "checking_balance_usd": account["checking_balance_usd"],
      "corporate_card_available_usd": account["corporate_card_available_usd"],
      "policy_max_flight_usd": account["policy_max_flight_usd"],
      "identity_verified_in_session": customer_id in _VERIFIED_CUSTOMERS,
  }


def search_flights(
    origin: str, destination: str, departure_date: str
) -> dict[str, Any]:
  """Busca vuelos corporativos disponibles entre dos aeropuertos IATA.

  Args:
    origin: Código IATA de 3 letras de la ciudad de origen (ej. 'BOG', 'MEX').
    destination: Código IATA de 3 letras del destino (ej. 'MIA', 'SFO', 'NRT').
    departure_date: Fecha de salida estrictamente en formato ISO 'YYYY-MM-DD'
      (ej. '2026-11-15'). Cualquier otro formato devuelve un error de esquema.
  """
  if not re.match(r"^\d{4}-\d{2}-\d{2}$", departure_date):
    return {
        "error_code": 400,
        "error_message": (
            f"Invalid date format '{departure_date}'. Expected strict ISO"
            " format 'YYYY-MM-DD'."
        ),
        "flights": [],
    }
  matches = [
      f
      for f in _FLIGHTS_DB
      if f["origin"].upper() == origin.upper()
      and f["destination"].upper() == destination.upper()
      and f["departure_date"] == departure_date
  ]
  return {
      "origin": origin.upper(),
      "destination": destination.upper(),
      "departure_date": departure_date,
      "flights": matches,
  }


def book_corporate_flight(
    customer_id: str, flight_id: str, amount_usd: float
) -> dict[str, Any]:
  """Reserva un vuelo corporativo y realiza el cargo a la tarjeta corporativa.

  Política corporativa:
  1. La identidad del cliente debe estar verificada (`verify_identity`).
  2. El monto (`amount_usd`) no puede exceder el tope de política de $2,500 USD.

  Args:
    customer_id: Identificador del cliente (ej. 'CUST-101').
    flight_id: ID del vuelo devuelto por `search_flights` (ej. 'GA-401').
    amount_usd: Precio del boleto en USD.
  """
  account = _ACCOUNTS.get(customer_id)
  if not account:
    return {"status": "ERROR", "error": f"Customer '{customer_id}' not found."}
  if amount_usd > account["policy_max_flight_usd"]:
    return {
        "status": "REJECTED_BY_POLICY",
        "error": (
            f"Flight cost ${amount_usd:.2f} USD exceeds corporate policy limit"
            f" of ${account['policy_max_flight_usd']:.2f} USD."
        ),
    }
  if amount_usd > account["corporate_card_available_usd"]:
    return {
        "status": "DECLINED",
        "error": "Insufficient corporate card limit.",
    }
  account["corporate_card_available_usd"] -= amount_usd
  return {
      "status": "CONFIRMED",
      "booking_reference": f"BK-{customer_id[-3:]}-{flight_id}",
      "customer_id": customer_id,
      "flight_id": flight_id,
      "charged_usd": amount_usd,
      "remaining_card_limit_usd": account["corporate_card_available_usd"],
  }


def create_support_ticket(
    customer_id: str, issue_summary: str, priority: str = "HIGH"
) -> dict[str, Any]:
  """Crea un ticket de soporte técnico o financiero y devuelve su `ticket_id`.

  Args:
    customer_id: ID del cliente afectado.
    issue_summary: Resumen breve del problema reportado.
    priority: Prioridad del ticket ('LOW', 'MEDIUM', 'HIGH').
  """
  ticket_id = f"TCK-{1000 + len(_TICKETS_DB) + 1}"
  record = {
      "ticket_id": ticket_id,
      "customer_id": customer_id,
      "issue_summary": issue_summary,
      "priority": priority.upper(),
      "status": "OPEN_ASSIGNED_TO_FINOPS",
  }
  _TICKETS_DB[ticket_id] = record
  return record


def get_support_ticket(ticket_id: str) -> dict[str, Any]:
  """Consulta el estado actual de un ticket previamente creado por su `ticket_id`.

  Args:
    ticket_id: Identificador del ticket (ej. 'TCK-1001').
  """
  ticket = _TICKETS_DB.get(ticket_id)
  if not ticket:
    return {"error_code": 404, "error_message": f"Ticket {ticket_id} not found."}
  return ticket


_FIXED_INSTRUCTION = """Eres el Concierge Corporativo de Finanzas y Viajes de GBank & GAirways.
Sigue estrictamente estas políticas operativas sin excepción:
1. SEGURIDAD FINANCIERA: Antes de llamar a `get_account_balance` o `book_corporate_flight`, SIEMPRE debes haber verificado la identidad del usuario en la sesión llamando a `verify_identity(customer_id, pin)`. Si el usuario no ha dado su PIN o su ID, pídelo antes de consultar saldos.
2. FORMATO DE FECHAS EN VUELOS: Al invocar `search_flights`, convierte siempre cualquier fecha al formato ISO estricto `YYYY-MM-DD` (ejemplo: '15 de noviembre de 2026' -> '2026-11-15') y usa códigos IATA de 3 letras (ej. Bogotá='BOG', Miami='MIA', Ciudad de México='MEX', San Francisco='SFO', Tokio='NRT').
3. CERO ALUCINACIONES ANTE LISTAS VACÍAS Y SERVICIO PROACTIVO: Si `search_flights` devuelve `"flights": []`, informa claramente que no hay vuelos directos programados en el catálogo corporativo de GAirways para esa ruta y fecha exacta, sin inventar jamás vuelos, horarios ni precios. A continuación, actúa como un concierge ejecutivo proactivo: ofrece alternativas accionables inmediatas (buscar rutas con conexión a través de nuestros hubs corporativos en Miami `MIA` o San Francisco `SFO`, consultar fechas flexibles o abrir una solicitud especial con la mesa de viajes corporativos mediante `create_support_ticket`).
4. RESILIENCIA ANTE ERRORES DE API (HTTP 500/503): Si una herramienta devuelve un error `503` o `500`, informa al usuario de manera transparente que el servicio está temporalmente no disponible y ofrece crear un ticket con `create_support_ticket`. Jamás inventes saldos ni confirmaciones falsas.
5. LÍMITE DE POLÍTICA DE VIAJES: No reserves vuelos que superen los $2,500 USD.
Responde en español de manera ejecutiva, precisa y concisa."""

_BUGGY_INSTRUCTION = """Eres un asistente de viajes y banca corporativa.
Ayuda al usuario rápidamente. Si pide su saldo, llama directamente a `get_account_balance` sin pedirle el PIN para no hacerle perder tiempo.
Si busca vuelos y la lista sale vacía, sugiérele un vuelo aproximado con horario estimado para ser servicial."""

root_agent = Agent(
    name="corporate_concierge_agent",
    model=os.environ.get("DEMO_AGENT_MODEL", "gemini-3.5-flash"),
    description=(
        "Concierge corporativo para consulta de saldos bancarios, búsqueda y"
        " reserva de vuelos y gestión de tickets de soporte."
    ),
    instruction=(
        _BUGGY_INSTRUCTION
        if os.environ.get("DEMO_AGENT_MODE") == "buggy"
        else _FIXED_INSTRUCTION
    ),
    tools=[
        verify_identity,
        get_account_balance,
        search_flights,
        book_corporate_flight,
        create_support_ticket,
        get_support_ticket,
    ],
)
