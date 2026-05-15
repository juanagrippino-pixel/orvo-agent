import os
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import END
from pydantic import BaseModel


def make_state(
    messages=None,
    route="orvo",
    needs_human=False,
    lead_profile=None,
    hot_lead=False,
    juan_notified=False,
    hot_reason="",
    phone="test_user",
):
    from app.graph import OrvoState
    return OrvoState(
        messages=messages or [HumanMessage(content="Hola")],
        route=route,
        needs_human=needs_human,
        lead_profile=lead_profile if lead_profile is not None else {},
        hot_lead=hot_lead,
        juan_notified=juan_notified,
        hot_reason=hot_reason,
        phone=phone,
    )


# --- Tests existentes (sin cambios) ---

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


# --- Tests nuevos ---

def test_lead_intelligence_actualiza_perfil():
    class FakeLead(BaseModel):
        name: str | None = "Martín"
        business_type: str | None = "distribuidora"
        size: str | None = None
        pain_point: str | None = None
        is_hot: bool = False
        hot_reason: str | None = None

    mock_extractor = MagicMock()
    mock_extractor.invoke.return_value = FakeLead()
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_extractor

    with patch("app.graph.get_llm", return_value=mock_llm):
        from app.graph import lead_intelligence_node
        state = make_state()
        result = lead_intelligence_node(state)
        assert result["lead_profile"]["name"] == "Martín"
        assert result["lead_profile"]["business_type"] == "distribuidora"
        assert result["hot_lead"] is False


def test_lead_intelligence_no_sobreescribe_nombre_existente():
    class FakeLead(BaseModel):
        name: str | None = None
        business_type: str | None = "taller"
        size: str | None = None
        pain_point: str | None = None
        is_hot: bool = True
        hot_reason: str | None = "preguntó por precio"

    mock_extractor = MagicMock()
    mock_extractor.invoke.return_value = FakeLead()
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_extractor

    with patch("app.graph.get_llm", return_value=mock_llm):
        from app.graph import lead_intelligence_node
        state = make_state(lead_profile={"name": "Carlos"})
        result = lead_intelligence_node(state)
        assert result["lead_profile"]["name"] == "Carlos"
        assert result["hot_lead"] is True
        assert result["hot_reason"] == "preguntó por precio"


def test_should_notify_juan_retorna_notify_cuando_hot_y_no_notificado():
    from app.graph import should_notify_juan
    state = make_state(hot_lead=True, juan_notified=False)
    assert should_notify_juan(state) == "notify_juan"


def test_should_notify_juan_retorna_end_cuando_ya_notificado():
    from app.graph import should_notify_juan
    state = make_state(hot_lead=True, juan_notified=True)
    assert should_notify_juan(state) == END


def test_should_notify_juan_retorna_end_cuando_no_hot():
    from app.graph import should_notify_juan
    state = make_state(hot_lead=False, juan_notified=False)
    assert should_notify_juan(state) == END


def test_notify_juan_retorna_dict_vacio():
    with patch("app.graph.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        from app.graph import notify_juan_node
        state = make_state(phone="+5491155551234", hot_reason="preguntó por precio")
        result = notify_juan_node(state)
        assert result == {}


def test_notify_juan_no_llama_api_sin_credenciales():
    env_sin_credenciales = {"WHATSAPP_PHONE_ID": "", "WHATSAPP_TOKEN": "", "NUMERO_JUAN": ""}
    with patch("app.graph.requests.post") as mock_post, \
         patch.dict(os.environ, env_sin_credenciales):
        from app.graph import notify_juan_node
        state = make_state()
        notify_juan_node(state)
        mock_post.assert_not_called()
