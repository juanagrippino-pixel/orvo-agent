from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel


def make_state(messages=None, route="orvo", needs_human=False):
    from app.graph import OrvoState
    return OrvoState(
        messages=messages or [HumanMessage(content="Hola")],
        route=route,
        needs_human=needs_human,
    )


def test_route_decision_repuestos():
    from app.graph import route_decision
    state = make_state(route="repuestos")
    assert route_decision(state) == "repuestos"


def test_route_decision_orvo():
    from app.graph import route_decision
    state = make_state(route="orvo")
    assert route_decision(state) == "orvo"


def test_route_decision_human():
    from app.graph import route_decision
    state = make_state(route="human")
    assert route_decision(state) == "human"


def test_route_decision_vacio_default_orvo():
    from app.graph import route_decision
    state = make_state(route="")
    assert route_decision(state) == "orvo"


def test_classify_node_actualiza_route_a_repuestos():
    class FakeDecision(BaseModel):
        route: str = "repuestos"

    mock_classifier = MagicMock()
    mock_classifier.invoke.return_value = FakeDecision(route="repuestos")
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_classifier

    with patch("app.graph.get_llm", return_value=mock_llm):
        from app.graph import classify_node
        state = make_state(messages=[HumanMessage(content="tengo una distribuidora de repuestos")])
        result = classify_node(state)
        assert result["route"] == "repuestos"


def test_classify_node_fallback_a_orvo_si_ruta_invalida():
    class FakeDecision(BaseModel):
        route: str = "invalida"

    mock_classifier = MagicMock()
    mock_classifier.invoke.return_value = FakeDecision(route="invalida")
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_classifier

    with patch("app.graph.get_llm", return_value=mock_llm):
        from app.graph import classify_node
        state = make_state()
        result = classify_node(state)
        assert result["route"] == "orvo"


def test_repuestos_bot_retorna_mensaje_sin_flag_human():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="Mostrador 24/7 cuesta $99 USD/mes.")

    with patch("app.graph.get_llm", return_value=mock_llm):
        from app.graph import repuestos_bot
        state = make_state()
        result = repuestos_bot(state)
        assert "messages" in result
        assert "needs_human" not in result


def test_orvo_bot_retorna_mensaje_sin_flag_human():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="Orvo crea agentes de IA para PyMEs.")

    with patch("app.graph.get_llm", return_value=mock_llm):
        from app.graph import orvo_bot
        state = make_state()
        result = orvo_bot(state)
        assert "messages" in result
        assert "needs_human" not in result


def test_human_handoff_siempre_activa_needs_human():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="Juan te va a contactar pronto.")

    with patch("app.graph.get_llm", return_value=mock_llm):
        from app.graph import human_handoff
        state = make_state()
        result = human_handoff(state)
        assert result.get("needs_human") is True
        assert "messages" in result


def test_graph_compila_sin_errores():
    from app.graph import orvo_app
    assert orvo_app is not None
