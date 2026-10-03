"""Evaluation dataset loader and validator."""

import json
from pathlib import Path

from app.evaluation.models import EvalCase
from app.utils.logger import logger


def load_evaluation_dataset(dataset_path: str | Path, repository_id: str | None = None) -> list[EvalCase]:
    """Load evaluation cases from JSONL dataset file.

    Args:
        dataset_path: Path to codebase_questions.jsonl file.
        repository_id: Optional repository filter.

    Returns:
        List of validated EvalCase instances.
    """
    path = Path(dataset_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Evaluation dataset file not found at: {path}")

    cases: list[EvalCase] = []

    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue

            try:
                data = json.loads(line_str)
                case = EvalCase(**data)
                if repository_id is None or case.repository_id == repository_id:
                    cases.append(case)
            except Exception as e:
                logger.warning(f"Error parsing line {line_num} in dataset {path}: {e}")

    logger.info(f"Loaded {len(cases)} evaluation test cases from {path}")
    return cases
