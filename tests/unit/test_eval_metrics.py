"""Unit tests for deterministic evaluation metrics."""

from app.evaluation.metrics import (
    answer_completeness,
    citation_metrics,
    compute_metric_set,
    entity_resolution_metrics,
    hit_at_k,
    mrr_at_k,
    path_accuracy,
    recall_at_k,
)


def test_hit_at_k():
    actual = ["module.ClassA", "module.ClassB", "module.ClassC"]
    expected = ["ClassB"]

    assert hit_at_k(actual, expected, k=1) == 0.0
    assert hit_at_k(actual, expected, k=2) == 1.0
    assert hit_at_k(actual, expected, k=5) == 1.0


def test_recall_at_k():
    actual = ["ClassA", "ClassB", "ClassC"]
    expected = ["ClassA", "ClassD"]

    assert recall_at_k(actual, expected, k=1) == 0.5
    assert recall_at_k(actual, expected, k=3) == 0.5


def test_mrr_at_k():
    actual = ["ClassX", "ClassY", "ClassTarget", "ClassZ"]
    expected = ["ClassTarget"]

    assert mrr_at_k(actual, expected, k=2) == 0.0
    assert mrr_at_k(actual, expected, k=3) == 1.0 / 3.0


def test_entity_resolution_metrics():
    actual = ["UserService", "UserRepository"]
    expected = ["UserService"]

    res = entity_resolution_metrics(actual, expected)
    assert res["precision"] == 0.5
    assert res["recall"] == 1.0
    assert res["accuracy"] == 1.0


def test_path_accuracy():
    actual_paths = [["main", "UserService", "UserRepository"]]
    expected_paths = [["main", "UserService", "UserRepository"]]

    res = path_accuracy(actual_paths, expected_paths)
    assert res["path_found"] == 1.0
    assert res["path_accuracy"] == 1.0


def test_citation_metrics():
    actual_citations = ["services/user_service.py"]
    expected_files = ["services/user_service.py", "repositories/user_repository.py"]

    res = citation_metrics(actual_citations, expected_files)
    assert res["precision"] == 1.0
    assert res["recall"] == 0.5


def test_answer_completeness():
    answer_text = "The UserService class calls UserRepository to fetch user records."
    keywords = ["UserService", "UserRepository"]

    comp = answer_completeness(answer_text, keywords)
    assert comp == 1.0


def test_structural_diff_metrics():
    from app.evaluation.metrics import structural_diff_metrics

    act = {"files_changed": ["a.py", "b.py"], "symbols_changed": ["sym1"], "affected_files": ["a.py"]}
    exp = {"files_changed": ["a.py", "b.py"], "symbols_changed": ["sym1"], "affected_files": ["a.py"]}

    res = structural_diff_metrics(act, exp)
    assert res["file_change_detection_accuracy"] == 1.0
    assert res["symbol_change_detection_accuracy"] == 1.0
    assert res["affected_file_precision"] == 1.0
    assert res["affected_file_recall"] == 1.0

