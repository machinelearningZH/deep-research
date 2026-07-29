from __future__ import annotations

from types import ModuleType, SimpleNamespace
from typing import Any

import pandas as pd
import pytest


@pytest.fixture
def workflow_module(load_app_module):
    search_module = ModuleType("_core.search")
    search_module.execute_searches = lambda *args, **kwargs: None

    processing_module = ModuleType("_core.llm_processing")
    processing_module.create_queries = lambda *args, **kwargs: []
    processing_module.analyze_documents = lambda *args, **kwargs: []
    processing_module.reflect_task_status = lambda *args, **kwargs: (None, None)
    processing_module.check_relevance = lambda *args, **kwargs: pd.DataFrame()

    logger_module = ModuleType("_core.logger")
    logger_module.custom_logger = SimpleNamespace()

    return load_app_module(
        "_core/workflow.py",
        stubs={
            "_core.search": search_module,
            "_core.llm_processing": processing_module,
            "_core.logger": logger_module,
        },
    )


def _workflow(workflow_module: Any, *, iterative: bool = False):
    docs = pd.DataFrame(
        [
            {
                "identifier": "doc-1",
                "title": "First",
                "text": "First text",
                "date": "2025-01-01",
                "link": "https://example.com/1",
            },
            {
                "identifier": "doc-2",
                "title": "Second",
                "text": "Second text",
                "date": "2025-01-02",
                "link": "https://example.com/2",
            },
        ]
    )
    workflow_config = {"max_queries": 3, "search_limit": 10, "auto_limit": 2}
    model_config = {
        "create_queries": "query-model",
        "check_relevance": "relevance-model",
        "analyze_documents": "analysis-model",
        "reflect_task": "reflection-model",
    }
    return workflow_module.ResearchWorkflow(
        docs,
        workflow_config,
        model_config,
        iterative_workflow=iterative,
    )


def test_run_iteration_updates_state_and_reflects_when_more_research_is_needed(
    monkeypatch: pytest.MonkeyPatch,
    workflow_module: Any,
) -> None:
    workflow = _workflow(workflow_module, iterative=True)
    observed: dict[str, Any] = {}

    monkeypatch.setattr(
        workflow_module,
        "create_queries",
        lambda *args, **kwargs: ["generated query"],
    )

    def fake_search(queries, **kwargs):
        observed["queries"] = queries
        observed["search_kwargs"] = kwargs
        return pd.DataFrame(
            [
                ("doc-1", "chunk one", "uuid-1"),
                ("doc-1", "duplicate", "uuid-1"),
                ("doc-2", "chunk two", "uuid-2"),
            ],
            columns=["identifier", "chunk_text", "uuid"],
        )

    def fake_relevance(user_query, search_results, **kwargs):
        observed["searched_uuids"] = search_results["uuid"].tolist()
        return pd.DataFrame({"identifier": ["doc-1", "doc-2"]})

    monkeypatch.setattr(workflow_module, "execute_searches", fake_search)
    monkeypatch.setattr(workflow_module, "check_relevance", fake_relevance)
    monkeypatch.setattr(
        workflow_module,
        "analyze_documents",
        lambda **kwargs: ["analysis one", "analysis two"],
    )
    monkeypatch.setattr(
        workflow_module,
        "reflect_task_status",
        lambda *args, **kwargs: (False, "Investigate another angle"),
    )

    statuses: list[str] = []
    finished, final_docs = workflow.run_iteration(
        "original question",
        iteration=0,
        status_callback=lambda message, **kwargs: statuses.append(message),
    )

    assert finished is False
    assert observed["queries"] == ["generated query", "original question"]
    assert observed["search_kwargs"] == {"limit": 10, "auto_limit": 2}
    assert observed["searched_uuids"] == ["uuid-1", "uuid-2"]
    assert final_docs[["identifier", "analysis"]].to_dict("records") == [
        {"identifier": "doc-1", "analysis": "analysis one"},
        {"identifier": "doc-2", "analysis": "analysis two"},
    ]
    assert workflow.get_results()["search_queries"] == ["generated query"]
    assert workflow.get_results()["search_results"] == ["uuid-1", "uuid-2"]
    assert workflow.previous_considerations == ["Investigate another angle"]
    assert statuses[-1] == "🔄 Weitere Iteration erforderlich"


def test_run_iteration_returns_accumulated_docs_when_search_has_no_new_chunks(
    monkeypatch: pytest.MonkeyPatch,
    workflow_module: Any,
) -> None:
    workflow = _workflow(workflow_module)
    existing_docs = workflow.docs.iloc[[0]].assign(analysis=["existing analysis"])
    workflow.final_docs = existing_docs
    workflow.previous_chunk_ids = ["uuid-1"]

    monkeypatch.setattr(
        workflow_module,
        "create_queries",
        lambda *args, **kwargs: ["another query"],
    )
    monkeypatch.setattr(
        workflow_module,
        "execute_searches",
        lambda *args, **kwargs: pd.DataFrame(
            [("doc-1", "already seen", "uuid-1")],
            columns=["identifier", "chunk_text", "uuid"],
        ),
    )

    def unexpected_relevance_call(*args, **kwargs):
        pytest.fail("Relevance should not run when every chunk was already processed")

    monkeypatch.setattr(
        workflow_module,
        "check_relevance",
        unexpected_relevance_call,
    )

    statuses: list[str] = []
    finished, final_docs = workflow.run_iteration(
        "original question",
        iteration=1,
        status_callback=lambda message, **kwargs: statuses.append(message),
    )

    assert finished is False
    assert final_docs is existing_docs
    assert workflow.previous_chunk_ids == ["uuid-1"]
    assert statuses[-1] == "❌ Keine neuen Suchergebnisse gefunden"
