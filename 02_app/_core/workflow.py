import pandas as pd
from typing import Dict, Tuple, Any
from _core.config import config
from _core.search import execute_searches
from _core.llm_processing import (
    create_queries,
    analyze_documents,
    reflect_task_status,
    check_relevance,
)
from _core.logger import custom_logger


class ResearchWorkflow:
    def __init__(
        self,
        docs: pd.DataFrame,
        workflow_config: Dict[str, Any],
        model_config: Dict[str, Any],
        iterative_workflow: bool = False,
    ):
        self.docs = docs
        self.config = config
        self.workflow_config = workflow_config
        self.model_config = model_config
        self.iterative_workflow = iterative_workflow
        self.logger = custom_logger
        self._initialize_state()

    def _initialize_state(self) -> None:
        """Initialize the workflow state"""
        self.previous_queries = []
        self.previous_chunk_ids = []
        self.previous_doc_ids = []
        self.previous_considerations = []
        self.previous_analysis_results = []
        self.final_docs = None
        self.iteration = 0

    def run_iteration(
        self,
        user_query: str,
        iteration: int,
        status_callback=None,
    ) -> Tuple[bool, pd.DataFrame]:
        """Run a single iteration of the research workflow"""

        # Step 1: Create search queries
        status_callback("🧠 Erstelle Suchanfragen...", step_increment=1)

        search_queries = create_queries(
            user_query,
            model_id=self.model_config["create_queries"],
            max_queries=self.workflow_config["max_queries"],
            previous_queries=self.previous_queries,
            previous_considerations=self.previous_considerations,
            first_iteration=(iteration == 0),
        )
        self.previous_queries.extend(search_queries)

        if len(search_queries) == 0:
            status_callback("❌ Keine Suchanfragen erstellt", step_increment=0)
            return (
                False,
                self.final_docs if self.final_docs is not None else pd.DataFrame(),
            )
        
        # Always include the original user query as well.
        search_queries.extend([user_query])

        # Step 2: Execute searches
        status_callback(
            f"🔍 Führe {len(search_queries)} Suchanfragen aus...", step_increment=1
        )

        search_results = execute_searches(
            search_queries,
            limit=self.workflow_config["search_limit"],
            auto_limit=self.workflow_config["auto_limit"],
        )
        search_results.drop_duplicates(subset=["uuid"], inplace=True)
        search_results = search_results[
            ~search_results.uuid.isin(self.previous_chunk_ids)
        ]
        self.previous_chunk_ids.extend(search_results.uuid.unique().tolist())

        if len(search_results) == 0:
            status_callback("❌ Keine neuen Suchergebnisse gefunden", step_increment=0)
            return (
                False,
                self.final_docs if self.final_docs is not None else pd.DataFrame(),
            )

        # Step 3: Check relevance
        status_callback(
            f"⚖️ Prüfe Relevanz von {len(search_results)} Dokumenten...",
            step_increment=1,
        )

        relevance_checks = check_relevance(
            user_query, search_results, model_id=self.model_config["check_relevance"]
        )
        relevant_doc_ids = relevance_checks.identifier.unique()
        relevant_doc_ids = [
            x for x in relevant_doc_ids if x not in self.previous_doc_ids
        ]
        self.previous_doc_ids.extend(relevant_doc_ids)

        if len(relevant_doc_ids) == 0:
            status_callback("❌ Keine relevanten Dokumente gefunden", step_increment=0)
            return (
                False,
                self.final_docs if self.final_docs is not None else pd.DataFrame(),
            )

        # Step 4: Analyze documents
        status_callback(
            f"📊 Analysiere {len(relevant_doc_ids)} relevante Dokumente im Volltext...",
            step_increment=1,
        )

        analysis_results = analyze_documents(
            user_query=user_query,
            document_ids=relevant_doc_ids,
            data=self.docs,
            model_id=self.model_config["analyze_documents"],
        )
        self.previous_analysis_results.extend(analysis_results)

        # Update final docs
        if iteration == 0:
            self.final_docs = self.docs[
                self.docs["identifier"].isin(relevant_doc_ids)
            ].copy()
            self.final_docs["analysis"] = analysis_results
        else:
            tmp_docs = self.docs[self.docs["identifier"].isin(relevant_doc_ids)].copy()
            tmp_docs["analysis"] = analysis_results
            self.final_docs = pd.concat([self.final_docs, tmp_docs])

        # We do not analyze the task status if the iterative workflow is not enabled or if it's the last iteration.
        if (
            not self.iterative_workflow
            or iteration == config["app"]["max_iterations"] - 1
        ):
            status_callback("✅ Iteration abgeschlossen", step_increment=1)
            return True, self.final_docs

        # Step 5: Reflect on task status
        status_callback("🤔 Bewerte Aufgabenstatus...", step_increment=1)

        finished, considerations = reflect_task_status(
            user_query,
            "\n\n".join(self.previous_analysis_results),
            model_id=self.model_config["reflect_task"],
        )
        self.previous_considerations.append(considerations)

        if finished:
            status_callback("✅ Aufgabe vollständig bearbeitet", step_increment=1)
        else:
            status_callback("🔄 Weitere Iteration erforderlich", step_increment=1)

        return finished or False, self.final_docs

    def get_results(self) -> Dict[str, Any]:
        """Get the results of the research workflow"""
        return {
            "search_queries": self.previous_queries,
            "search_results": self.previous_chunk_ids,
            "relevant_doc_ids": self.previous_doc_ids,
            "final_docs": self.final_docs,
        }
