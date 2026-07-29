from __future__ import annotations

from types import ModuleType, SimpleNamespace
from typing import Any

import pandas as pd
import pytest


@pytest.fixture
def llm_processing(load_app_module):
    client = SimpleNamespace(call_structured=lambda *args, **kwargs: None)

    client_module = ModuleType("_core.llm_client")
    client_module.ClientManager = lambda: SimpleNamespace(
        get_client=lambda provider: client
    )

    logger_module = ModuleType("_core.logger")
    logger_module.custom_logger = SimpleNamespace(
        error=lambda message: None,
        info_console=lambda message: None,
    )

    return load_app_module(
        "_core/llm_processing.py",
        stubs={
            "_core.llm_client": client_module,
            "_core.logger": logger_module,
        },
    )


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ('{"relevance": true}', {"relevance": True}),
        (
            '```json\n{"queries": ["tax", "budget"]}\n```',
            {"queries": ["tax", "budget"]},
        ),
        ('```\n{"finished": false}\n```', {"finished": False}),
        ("not JSON", None),
        ("", None),
    ],
    ids=["plain", "json-fence", "plain-fence", "malformed", "empty"],
)
def test_parse_json_response_accepts_supported_llm_formats(
    llm_processing: Any,
    response: str,
    expected: dict[str, Any] | None,
) -> None:
    assert llm_processing._parse_json_response(response) == expected


def test_check_relevance_keeps_only_positive_valid_responses(
    monkeypatch: pytest.MonkeyPatch,
    llm_processing: Any,
) -> None:
    data = pd.DataFrame(
        {
            "identifier": ["relevant", "irrelevant", "invalid"],
            "chunk_text": ["useful", "unrelated", "ambiguous"],
        }
    )
    captured: dict[str, Any] = {}

    def fake_parallel(prompts, function, **kwargs):
        captured["prompts"] = prompts
        captured["kwargs"] = kwargs
        return [
            '{"reasoning": "direct evidence", "relevance": "yes"}',
            '{"reasoning": "different topic", "relevance": false}',
            "invalid response",
        ]

    monkeypatch.setattr(llm_processing, "call_function_in_parallel", fake_parallel)

    result = llm_processing.check_relevance("tax question", data, model_id="model")

    assert result[["identifier", "reasoning"]].to_dict("records") == [
        {"identifier": "relevant", "reasoning": "direct evidence"}
    ]
    assert len(captured["prompts"]) == 3
    assert "tax question" in captured["prompts"][0]
    assert captured["kwargs"]["model_id"] == "model"
    assert captured["kwargs"]["json_schema"]["additionalProperties"] is False
