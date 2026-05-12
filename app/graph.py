from typing import Annotated
from typing_extensions import TypedDict
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from app.models import get_llm
from app.prompts import CLASSIFY_PROMPT, REPUESTOS_SYSTEM, ORVO_SYSTEM, HUMAN_HANDOFF_SYSTEM


class OrvoState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    route: str
    needs_human: bool


class RouteDecision(BaseModel):
    route: str


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
    response = llm.invoke([SystemMessage(content=REPUESTOS_SYSTEM)] + state["messages"])
    return {"messages": [response]}


def orvo_bot(state: OrvoState) -> dict:
    llm = get_llm()
    response = llm.invoke([SystemMessage(content=ORVO_SYSTEM)] + state["messages"])
    return {"messages": [response]}


def human_handoff(state: OrvoState) -> dict:
    llm = get_llm()
    response = llm.invoke([SystemMessage(content=HUMAN_HANDOFF_SYSTEM)] + state["messages"])
    return {"messages": [response], "needs_human": True}


def route_decision(state: OrvoState) -> str:
    return state.get("route", "orvo") or "orvo"


def _build_graph():
    graph = StateGraph(OrvoState)

    graph.add_node("classify", classify_node)
    graph.add_node("repuestos_bot", repuestos_bot)
    graph.add_node("orvo_bot", orvo_bot)
    graph.add_node("human_handoff", human_handoff)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        route_decision,
        {
            "repuestos": "repuestos_bot",
            "orvo": "orvo_bot",
            "human": "human_handoff",
        },
    )
    graph.add_edge("repuestos_bot", END)
    graph.add_edge("orvo_bot", END)
    graph.add_edge("human_handoff", END)

    return graph.compile()


orvo_app = _build_graph()
