from __future__ import annotations

import ast
from pathlib import Path


def test_conversation_domain_exports_current_whatsapp_agent_modules():
    import app.conversation.db as conversation_db
    import app.conversation.graph as conversation_graph
    import app.conversation.models as conversation_models
    import app.conversation.prompts as conversation_prompts

    assert conversation_graph.orvo_app is not None
    assert hasattr(conversation_graph, "OrvoState")
    assert conversation_models.get_llm is not None
    assert conversation_prompts.ORVO_SYSTEM
    assert hasattr(conversation_db, "save_messages")


def test_legacy_conversation_imports_remain_compatibility_shims():
    import app.graph as legacy_graph
    import app.models as legacy_models
    import app.prompts as legacy_prompts
    import db as legacy_db
    from app.conversation import db as conversation_db
    from app.conversation import graph as conversation_graph
    from app.conversation import models as conversation_models
    from app.conversation import prompts as conversation_prompts

    assert legacy_graph.orvo_app is conversation_graph.orvo_app
    assert legacy_models.get_llm is conversation_models.get_llm
    assert legacy_prompts.ORVO_SYSTEM == conversation_prompts.ORVO_SYSTEM
    assert legacy_db.save_messages is conversation_db.save_messages


def test_brain_modules_do_not_import_conversation_domain():
    brain_root = Path(__file__).resolve().parents[1] / "app" / "brain"
    offenders: list[str] = []
    for module_path in sorted(brain_root.rglob("*.py")):
        tree = ast.parse(module_path.read_text(), filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("app.conversation"):
                        offenders.append(f"{module_path.relative_to(brain_root)} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("app.conversation"):
                    offenders.append(f"{module_path.relative_to(brain_root)} imports {node.module}")
    assert offenders == []
