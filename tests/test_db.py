import pytest
from langchain_core.messages import HumanMessage, AIMessage


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    import db
    db.init_db()


def test_load_messages_retorna_lista_vacia_si_no_hay_historial():
    from db import load_messages
    assert load_messages("+5491155551234") == []


def test_save_and_load_messages_round_trip():
    from db import save_messages, load_messages
    msgs = [HumanMessage(content="Hola"), AIMessage(content="Hola! Soy Orvo.")]
    save_messages("+5491155551234", msgs)
    loaded = load_messages("+5491155551234")
    assert len(loaded) == 2
    assert loaded[0].content == "Hola"
    assert loaded[1].content == "Hola! Soy Orvo."
    assert isinstance(loaded[0], HumanMessage)
    assert isinstance(loaded[1], AIMessage)


def test_save_messages_sobreescribe_historial_existente():
    from db import save_messages, load_messages
    save_messages("+5491155551234", [HumanMessage(content="Primer mensaje")])
    save_messages("+5491155551234", [HumanMessage(content="A"), AIMessage(content="B")])
    loaded = load_messages("+5491155551234")
    assert len(loaded) == 2


def test_load_lead_retorna_dict_vacio_si_no_existe():
    from db import load_lead
    assert load_lead("+5491155551234") == {}


def test_save_lead_crea_nuevo_lead():
    from db import save_lead, load_lead
    save_lead("+5491155551234", {"name": "Martín", "business_type": "distribuidora"})
    lead = load_lead("+5491155551234")
    assert lead["name"] == "Martín"
    assert lead["business_type"] == "distribuidora"


def test_save_lead_no_sobreescribe_nombre_con_none():
    from db import save_lead, load_lead
    save_lead("+5491155551234", {"name": "Martín"})
    save_lead("+5491155551234", {"name": None, "business_type": "taller"})
    lead = load_lead("+5491155551234")
    assert lead["name"] == "Martín"
    assert lead["business_type"] == "taller"


def test_save_lead_una_vez_hot_siempre_hot():
    from db import save_lead, load_lead
    save_lead("+5491155551234", {"is_hot": True, "hot_reason": "preguntó precio"})
    save_lead("+5491155551234", {"is_hot": False})
    lead = load_lead("+5491155551234")
    assert lead["is_hot"] == 1


def test_is_juan_notified_retorna_false_inicialmente():
    from db import is_juan_notified
    assert is_juan_notified("+5491155551234") is False


def test_mark_juan_notified_activa_el_flag():
    from db import mark_juan_notified, is_juan_notified
    mark_juan_notified("+5491155551234")
    assert is_juan_notified("+5491155551234") is True


def test_mark_juan_notified_funciona_sin_lead_previo():
    from db import mark_juan_notified, is_juan_notified
    mark_juan_notified("+5491199999999")
    assert is_juan_notified("+5491199999999") is True
