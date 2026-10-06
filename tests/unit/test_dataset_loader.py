"""Unit tests for evaluation dataset loader."""

from pathlib import Path

from app.evaluation.dataset_loader import load_evaluation_dataset


def test_load_evaluation_dataset():
    dataset_path = Path("tests/fixtures/evaluation/codebase_questions.jsonl").resolve()
    assert dataset_path.exists()

    cases = load_evaluation_dataset(dataset_path)
    assert len(cases) >= 10

    # Filter sample_repo
    sample_cases = load_evaluation_dataset(dataset_path, repository_id="sample_repo")
    assert len(sample_cases) >= 10
    assert all(c.repository_id == "sample_repo" for c in sample_cases)

    # Filter multi_language_repo
    ml_cases = load_evaluation_dataset(dataset_path, repository_id="multi_language_repo")
    assert len(ml_cases) == 0
    assert all(c.repository_id == "multi_language_repo" for c in ml_cases)
