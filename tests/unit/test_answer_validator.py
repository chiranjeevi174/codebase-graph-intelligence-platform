"""Unit tests for AnswerValidator component."""

from app.models.entities import NormalizedSearchResult, ResolvedEntity
from app.reasoning.answer_validator import AnswerValidator


def test_answer_validator_grounded_answer():
    validator = AnswerValidator()

    resolved = [
        ResolvedEntity(
            symbol_id="1",
            name="create_user",
            qualified_name="services.UserService.create_user",
            symbol_type="Method",
            file_path="services/user_service.py",
            start_line=10,
            end_line=30,
        )
    ]

    fused = [
        NormalizedSearchResult(
            id="c1",
            source="both",
            repository_id="repo",
            file_path="services/user_service.py",
            start_line=10,
            end_line=30,
            content="def create_user(): pass",
        )
    ]

    good_answer = "UserService.create_user is defined in services/user_service.py:10-30 and creates a user entity."
    is_valid, errors = validator.validate(good_answer, fused_results=fused, resolved_entities=resolved)
    assert is_valid is True
    assert len(errors) == 0


def test_answer_validator_ungrounded_file():
    validator = AnswerValidator()

    resolved = []
    fused = [
        NormalizedSearchResult(
            id="c1",
            source="semantic",
            repository_id="repo",
            file_path="services/user_service.py",
            start_line=10,
            end_line=30,
            content="def create_user(): pass",
        )
    ]

    bad_answer = "The function is defined in non_existent_file.py:50."
    is_valid, errors = validator.validate(bad_answer, fused_results=fused, resolved_entities=resolved)
    assert is_valid is False
    assert any("non_existent_file.py" in err for err in errors)
