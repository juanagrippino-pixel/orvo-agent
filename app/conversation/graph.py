import os
import requests
from typing import Annotated
from typing_extensions import TypedDict
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, BaseMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from app.conversation.models import get_llm
from app.conversation.prompts import (
    CLASSIFY_PROMPT,
    REPUESTOS_SYSTEM,
    ORVO_SYSTEM,
    HUMAN_HANDOFF_SYSTEM,
    LEAD_INTELLIGENCE_PROMPT,
    build_system_prompt,
)


class OrvoState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    route: str
    needs_human: bool
    lead_profile: dict
    hot_lead: bool
    juan_notified: bool
    hot_reason: str
    phone: str


class RouteDecision(BaseModel):
    route: str


class LeadIntelligence(BaseModel):
    name: str | None = None
    business_type: str | None = None
    size: str | None = None
    pain_point: str | None = None
    is_hot: bool = False
    hot_reason: str | None = None


def classify_node(state: OrvoState) -> dict:
    llm = get_llm()
    classifier = llm.with_structured_output(RouteDecision)
    decision = classifier.invoke(
        [SystemMessage(content=CLASSIFY_PROMPT)] + state["messages"]
    )
    route = decision.route if decision.route in ("repuestos", "orvo", "human") else "orvo"
    return {"route": route}


def repuestos_bot(state: OrvoState) -> dict:
    llm = get_llm()
    system = build_system_prompt(REPUESTOS_SYSTEM, state.get("lead_profile") or {})
    response = llm.invoke([SystemMessage(content=system)] + state["messages"])
    return {"messages": [response]}


def orvo_bot(state: OrvoState) -> dict:
    llm = get_llm()
    system = build_system_prompt(ORVO_SYSTEM, state.get("lead_profile") or {})
    response = llm.invoke([SystemMessage(content=system)] + state["messages"])
    return {"messages": [response]}


def human_handoff(state: OrvoState) -> dict:
    llm = get_llm()
    system = build_system_prompt(HUMAN_HANDOFF_SYSTEM, state.get("lead_profile") or {})
    response = llm.invoke([SystemMessage(content=system)] + state["messages"])
    return {"messages": [response], "needs_human": True}


def route_decision(state: OrvoState) -> str:
    return state.get("route", "orvo") or "orvo"


def lead_intelligence_node(state: OrvoState) -> dict:
    llm = get_llm()
    extractor = llm.with_structured_output(LeadIntelligence)
    result = extractor.invoke(
        [SystemMessage(content=LEAD_INTELLIGENCE_PROMPT)] + state["messages"]
    )
    current = dict(state.get("lead_profile") or {})
    for field in ("name", "business_type", "size", "pain_point"):
        val = getattr(result, field)
        if val is not None:
            current[field] = val
    return {
        "lead_profile": current,
        "hot_lead": result.is_hot,
        "hot_reason": result.hot_reason or "",
    }


def notify_juan_node(state: OrvoState) -> dict:
    phone = state.get("phone", "desconocido")
    profile = state.get("lead_profile") or {}
    last_msg = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_msg = msg.content[:200]
            break
    text = (
        f"🔥 Lead caliente — Orvo IA\n\n"
        f"👤 Nombre: {profile.get('name') or 'No capturado'}\n"
        f"🏢 Negocio: {profile.get('business_type') or 'No capturado'}\n"
        f"👥 Tamaño: {profile.get('size') or 'No capturado'}\n"
        f"💬 Dolor: {profile.get('pain_point') or 'No capturado'}\n"
        f"📱 WhatsApp: {phone}\n\n"
        f"Razón: {state.get('hot_reason') or ''}\n\n"
        f"Último: \"{last_msg}\"\n\n"
        f"Agendar: https://calendly.com/juanagrippino/website-services"
    )
    phone_id = os.environ.get("WHATSAPP_PHONE_ID", "")
    token = os.environ.get("WHATSAPP_TOKEN", "")
    numero_juan = os.environ.get("NUMERO_JUAN", "")
    if phone_id and token and numero_juan:
        url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "messaging_product": "whatsapp",
            "to": numero_juan,
            "type": "text",
            "text": {"body": text},
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"[notify_juan] Error {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[notify_juan] Exception: {e}")
    return {}


def should_notify_juan(state: OrvoState) -> str:
    if state.get("hot_lead") and not state.get("juan_notified"):
        return "notify_juan"
    return END


def _build_graph():
    graph = StateGraph(OrvoState)
    graph.add_node("classify", classify_node)
    graph.add_node("repuestos_bot", repuestos_bot)
    graph.add_node("orvo_bot", orvo_bot)
    graph.add_node("human_handoff", human_handoff)
    graph.add_node("lead_intelligence", lead_intelligence_node)
    graph.add_node("notify_juan", notify_juan_node)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        route_decision,
        {"repuestos": "repuestos_bot", "orvo": "orvo_bot", "human": "human_handoff"},
    )
    graph.add_edge("repuestos_bot", "lead_intelligence")
    graph.add_edge("orvo_bot", "lead_intelligence")
    graph.add_edge("human_handoff", "lead_intelligence")
    graph.add_conditional_edges(
        "lead_intelligence",
        should_notify_juan,
        {"notify_juan": "notify_juan", END: END},
    )
    graph.add_edge("notify_juan", END)
    return graph.compile()


orvo_app = _build_graph()
