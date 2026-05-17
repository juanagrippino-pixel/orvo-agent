from app.prompts import (
    ORVO_KNOWLEDGE,
    CLASSIFY_PROMPT,
    REPUESTOS_SYSTEM,
    ORVO_SYSTEM,
    HUMAN_HANDOFF_SYSTEM,
    QUALIFICATION_INSTRUCTIONS,
    OBJECTION_HANDLING,
    LEAD_INTELLIGENCE_PROMPT,
    build_system_prompt,
)


def test_orvo_knowledge_tiene_precio_y_links():
    assert "99 USD" in ORVO_KNOWLEDGE
    assert "calendly" in ORVO_KNOWLEDGE.lower()
    assert "orvo.space" in ORVO_KNOWLEDGE
    assert "demo-repuestos.html" in ORVO_KNOWLEDGE
    assert "Oli" in ORVO_KNOWLEDGE


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


def test_build_system_prompt_con_perfil_vacio():
    result = build_system_prompt("base prompt aquí", {})
    assert "base prompt aquí" in result
    assert "Nada todavía" in result


def test_build_system_prompt_inyecta_nombre_y_negocio():
    result = build_system_prompt("base", {"name": "Martín", "business_type": "taller mecánico"})
    assert "Martín" in result
    assert "taller mecánico" in result
    assert "Nada todavía" not in result


def test_build_system_prompt_no_muestra_campos_vacios():
    result = build_system_prompt("base", {"name": "Ana", "business_type": None})
    assert "Ana" in result
    assert "None" not in result


def test_lead_intelligence_prompt_tiene_criterios_hot():
    assert "is_hot" in LEAD_INTELLIGENCE_PROMPT.lower() or "hot" in LEAD_INTELLIGENCE_PROMPT.lower()
    assert "precio" in LEAD_INTELLIGENCE_PROMPT.lower()
    assert len(LEAD_INTELLIGENCE_PROMPT.strip()) > 100


def test_qualification_instructions_tiene_preguntas_clave():
    assert "tipo de negocio" in QUALIFICATION_INSTRUCTIONS.lower()
    assert len(QUALIFICATION_INSTRUCTIONS.strip()) > 100


def test_objection_handling_cubre_objecion_precio():
    assert "caro" in OBJECTION_HANDLING.lower() or "presupuesto" in OBJECTION_HANDLING.lower()
    assert "calendly" in OBJECTION_HANDLING.lower() or "demo" in OBJECTION_HANDLING.lower()
    assert len(OBJECTION_HANDLING.strip()) > 100


def test_todos_los_prompts_nuevos_tienen_contenido_sustancial():
    for prompt in [QUALIFICATION_INSTRUCTIONS, OBJECTION_HANDLING, LEAD_INTELLIGENCE_PROMPT]:
        assert len(prompt.strip()) > 100, f"Prompt demasiado corto: {prompt[:50]}"
