"""Reciprocal Rank Fusion (RRF) for combining Graph and Semantic retrieval results."""


from app.models.entities import NormalizedSearchResult


class RRFComposer:
    """Computes Reciprocal Rank Fusion over multiple ranked result lists."""

    def __init__(self, k: int = 60):
        self.k = k

    def fuse(
        self,
        graph_results: list[NormalizedSearchResult],
        semantic_results: list[NormalizedSearchResult],
        top_k: int = 10,
    ) -> list[NormalizedSearchResult]:
        """Combine graph and semantic ranked results into a single deduplicated list ordered by RRF score.

        Formula: RRF_score(item) = sum( 1 / (k + rank_i) ) for each list i where item occurs.
        Ranks are 1-indexed.
        """
        scores: dict[str, float] = {}
        sources: dict[str, set[str]] = {}
        items: dict[str, NormalizedSearchResult] = {}

        def get_dedup_key(item: NormalizedSearchResult) -> str:
            if item.qualified_name:
                return f"{item.file_path}::{item.qualified_name}::{item.start_line}"
            return f"{item.file_path}::{item.start_line}-{item.end_line}"

        # Process Graph results
        for rank, item in enumerate(graph_results, start=1):
            key = get_dedup_key(item)
            rrf_delta = 1.0 / (self.k + rank)
            scores[key] = scores.get(key, 0.0) + rrf_delta
            if key not in sources:
                sources[key] = set()
            sources[key].add("graph")

            if key not in items:
                items[key] = item
            else:
                # Merge metadata if needed
                if not items[key].qualified_name and item.qualified_name:
                    items[key].qualified_name = item.qualified_name

        # Process Semantic results
        for rank, item in enumerate(semantic_results, start=1):
            key = get_dedup_key(item)
            rrf_delta = 1.0 / (self.k + rank)
            scores[key] = scores.get(key, 0.0) + rrf_delta
            if key not in sources:
                sources[key] = set()
            sources[key].add("semantic")

            if key not in items:
                items[key] = item
            else:
                # Retain richer content if available
                if len(item.content) > len(items[key].content):
                    items[key].content = item.content

        fused: list[NormalizedSearchResult] = []
        for key, item in items.items():
            src_set = sources[key]
            provenance = "both" if len(src_set) > 1 else list(src_set)[0]
            
            fused_item = item.model_copy(deep=True)
            fused_item.source = provenance
            fused_item.rrf_score = round(scores[key], 6)
            fused.append(fused_item)

        # Sort descending by RRF score
        fused.sort(key=lambda x: x.rrf_score, reverse=True)
        return fused[:top_k]
