from app.prompts import (
    ORVO_KNOWLEDGE,
    CLASSIFY_PROMPT,
    REPUESTOS_SYSTEM,
    ORVO_SYSTEM,
    HUMAN_HANDOFF_SYSTEM,
)


def test_orvo_knowledge_tiene_precio_y_links():
    assert "99 USD" in ORVO_KNOWLEDGE
    assert "calendly" in ORVO_KNOWLEDGE.lower()
    assert "orvo.space" in ORVO_KNOWLEDGE
    assert "demo-repuestos.html" in ORVO_KNOWLEDGE


def test_classify_prompt_define_las_tres_rutas():
    assert '"repuestos"' in CLASSIFY_PROMPT
    assert '"orvo"' in CLASSIFY_PROMPT
    assert '"human"' in CLASSIFY_PROMPT


def test_repuestos_system_tiene_link_demo():
    assert "demo-repuestos.html" in REPUESTOS_SYSTEM
    assert "99 USD" in REPUESTOS_SYSTEM


def test_orvo_system_tiene_calendly():
    assert "calendly" in ORVO_SYSTEM.lower()


def test_human_handoff_system_tiene_contacto():
    assert "calendly" in HUMAN_HANDOFF_SYSTEM.lower()


def test_todos_los_prompts_tienen_contenido_sustancial():
    for prompt in [ORVO_KNOWLEDGE, CLASSIFY_PROMPT, REPUESTOS_SYSTEM, ORVO_SYSTEM, HUMAN_HANDOFF_SYSTEM]:
        assert len(prompt.strip()) > 100, f"Prompt demasiado corto: {prompt[:50]}"
