"""Unit tests for Reciprocal Rank Fusion (RRF) calculation and deduplication."""

from app.models.entities import NormalizedSearchResult
from app.retrieval.rrf import RRFComposer


def test_rrf_manually_verifiable_example():
    """Verify standard RRF score formula: RRF_score = sum( 1 / (k + rank) ) with k=60.

    Item A: Graph rank 1 (index 0) -> 1 / (60 + 1) = 1 / 61 = 0.016393
    Item B: Graph rank 2 (index 1), Semantic rank 1 (index 0) -> 1/62 + 1/61 = 0.032522
    Item C: Semantic rank 2 (index 1) -> 1 / (60 + 2) = 1 / 62 = 0.016129

    Expected order: Item B (0.032522, source='both'), Item A (0.016393, source='graph'), Item C (0.016129, source='semantic').
    """
    composer = RRFComposer(k=60)

    item_a = NormalizedSearchResult(
        id="item_a",
        source="graph",
        repository_id="repo1",
        file_path="src/a.py",
        symbol_name="FuncA",
        qualified_name="module.FuncA",
        start_line=1,
        end_line=10,
        content="def FuncA(): pass",
        score=1.0,
    )

    item_b_graph = NormalizedSearchResult(
        id="item_b_g",
        source="graph",
        repository_id="repo1",
        file_path="src/b.py",
        symbol_name="FuncB",
        qualified_name="module.FuncB",
        start_line=20,
        end_line=30,
        content="def FuncB(): pass",
        score=0.9,
    )

    item_b_sem = NormalizedSearchResult(
        id="item_b_s",
        source="semantic",
        repository_id="repo1",
        file_path="src/b.py",
        symbol_name="FuncB",
        qualified_name="module.FuncB",
        start_line=20,
        end_line=30,
        content="def FuncB(): # full body\n    return True",
        score=0.85,
    )

    item_c = NormalizedSearchResult(
        id="item_c",
        source="semantic",
        repository_id="repo1",
        file_path="src/c.py",
        symbol_name="FuncC",
        qualified_name="module.FuncC",
        start_line=5,
        end_line=15,
        content="def FuncC(): pass",
        score=0.8,
    )

    graph_list = [item_a, item_b_graph]
    semantic_list = [item_b_sem, item_c]

    fused = composer.fuse(graph_results=graph_list, semantic_results=semantic_list, top_k=10)

    assert len(fused) == 3

    # Top item must be Item B because it appeared in both lists
    top_item = fused[0]
    assert top_item.qualified_name == "module.FuncB"
    assert top_item.source == "both"
    expected_b_score = round((1.0 / 62.0) + (1.0 / 61.0), 6)
    assert abs(top_item.rrf_score - expected_b_score) < 1e-5

    # Second item must be Item A
    second_item = fused[1]
    assert second_item.qualified_name == "module.FuncA"
    assert second_item.source == "graph"
    expected_a_score = round(1.0 / 61.0, 6)
    assert abs(second_item.rrf_score - expected_a_score) < 1e-5

    # Third item must be Item C
    third_item = fused[2]
    assert third_item.qualified_name == "module.FuncC"
    assert third_item.source == "semantic"
    expected_c_score = round(1.0 / 62.0, 6)
    assert abs(third_item.rrf_score - expected_c_score) < 1e-5


def test_rrf_deduplication():
    composer = RRFComposer(k=60)
    item1 = NormalizedSearchResult(
        id="1",
        source="semantic",
        repository_id="r",
        file_path="src/main.py",
        start_line=1,
        end_line=10,
        content="print(1)",
    )
    item2 = NormalizedSearchResult(
        id="2",
        source="semantic",
        repository_id="r",
        file_path="src/main.py",
        start_line=1,
        end_line=10,
        content="print(1)",
    )

    fused = composer.fuse([item1], [item2], top_k=5)
    assert len(fused) == 1
    assert fused[0].source == "both"
