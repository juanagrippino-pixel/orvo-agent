from server import _first_inbound_message


def test_first_inbound_message_scans_past_non_inbound_entries_in_same_messages_batch():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"id": "placeholder-without-sender", "type": "unknown"},
                                {
                                    "from": "5491100000000",
                                    "id": "wamid.inbound",
                                    "type": "text",
                                    "text": {"body": "Necesito stock"},
                                },
                            ]
                        }
                    }
                ]
            }
        ]
    }

    assert _first_inbound_message(payload) == {
        "from": "5491100000000",
        "id": "wamid.inbound",
        "type": "text",
        "text": {"body": "Necesito stock"},
    }
