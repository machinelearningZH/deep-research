import pandas as pd
from typing import List
import weaviate
import weaviate.classes as wvc
import atexit
from _core.logger import custom_logger
from _core.config import config
from _core.embeddings import st_encoder as encoder


def initialize_weaviate(collection_name: str = None):
    """
    Connect to local Weaviate on Docker and return the specified collection.

    Args:
        collection_name (str, optional): Collection name. Uses config if None.

    Returns:
        weaviate.collections.Collection: The collection object.
    """
    if collection_name is None:
        collection_name = config["weaviate"]["collection_name"]

    client = weaviate.connect_to_local(
        port=config["weaviate"]["port"], grpc_port=config["weaviate"]["grpc_port"]
    )
    collection = client.collections.get(collection_name)

    # Register cleanup function
    def cleanup_weaviate():
        try:
            client.close()
        except Exception as e:
            custom_logger.error(f"Error closing Weaviate client: {e}")
            raise

    atexit.register(cleanup_weaviate)

    return collection


collection = initialize_weaviate()


def hybrid_search(query: str, limit: int, auto_limit: int):
    """
    Perform hybrid search using embeddings and keywords.

    Args:
        query (str): Search query.
        limit (int): Max results.
        auto_limit (int): Max auto-expanded results.

    Returns:
        list[tuple[str, str, str]]: Tuples of (identifier, text, uuid).
    """
    embeddings = encoder.embed([query])
    if embeddings is None or len(embeddings) == 0:
        return []

    response = collection.query.hybrid(
        query=query,
        query_properties=["text", "title"],
        vector=embeddings[0],
        limit=limit,
        auto_limit=auto_limit,
        fusion_type=wvc.query.HybridFusion.RELATIVE_SCORE,
    )
    return [
        (item.properties["identifier"], item.properties["text"], str(item.uuid))
        for item in response.objects
    ]


def execute_searches(
    queries: List[str],
    limit: int,
    auto_limit: int,
) -> pd.DataFrame:
    """
    Run hybrid search for each query and aggregate results.

    Args:
        queries (List[str]): List of queries.
        limit (int): Max results per query.
        auto_limit (int): Auto limit for hybrid search.

    Returns:
        pd.DataFrame: Aggregated search results.
    """
    results = []
    for query in queries:
        search_results = hybrid_search(query, limit=limit, auto_limit=auto_limit)
        results.extend(search_results)
    return pd.DataFrame(results, columns=["identifier", "chunk_text", "uuid"])
