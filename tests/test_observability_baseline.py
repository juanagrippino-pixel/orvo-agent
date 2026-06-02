import ast
import logging
from pathlib import Path


def _print_calls(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(), filename=str(path))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]


def test_runtime_paths_do_not_use_print_for_observability():
    repo = Path(__file__).resolve().parents[1]
    runtime_paths = [
        repo / "server.py",
        repo / "app" / "conversation" / "graph.py",
        *sorted((repo / "app" / "brain").rglob("*.py")),
    ]

    offenders = {str(path.relative_to(repo)): _print_calls(path) for path in runtime_paths if _print_calls(path)}

    assert offenders == {}


def test_webhook_payload_shape_error_logs_request_correlation(caplog):
    import server

    payload_missing_text_body = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"from": "+5491112345678", "type": "text"},
                            ]
                        }
                    }
                ]
            }
        ]
    }

    with caplog.at_level(logging.WARNING, logger="server"):
        response = server.app.test_client().post(
            "/webhook",
            json=payload_missing_text_body,
            headers={"X-Request-ID": "req-webhook-shape"},
        )

    assert response.status_code == 200
    warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert any(record.event == "webhook_payload_shape_error" for record in warnings)
    assert any(record.request_id == "req-webhook-shape" for record in warnings)


def test_whatsapp_send_without_credentials_logs_metadata_not_message_body(monkeypatch, caplog):
    import server

    monkeypatch.setattr(server, "WHATSAPP_PHONE_ID", "")
    monkeypatch.setattr(server, "WHATSAPP_TOKEN", "")

    with caplog.at_level(logging.INFO, logger="server"):
        server._send("+5491112345678", "mensaje sensible que no debe quedar en logs")

    records = [record for record in caplog.records if record.event == "whatsapp_send_skipped_missing_credentials"]
    assert records
    assert records[0].phone_hash
    assert "mensaje sensible" not in records[0].getMessage()
