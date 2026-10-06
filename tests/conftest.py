"""Pytest fixtures for unit and integration testing."""

import pytest

from app.config.settings import Settings


@pytest.fixture
def test_settings():
    """Return test settings override."""
    return Settings(
        APP_NAME="Test Graph Intelligence Platform",
        ENVIRONMENT="test",
        LLM_PROVIDER="openai",
        OPENAI_API_KEY="test_openai_key",
    )


@pytest.fixture
def sample_python_code():
    """Return a sample Python source code string for AST testing."""
    return '''"""Sample Module Docstring."""

import os
from typing import List

class BaseService:
    def __init__(self, name: str):
        self.name = name

    def get_status(self) -> str:
        return "active"

class UserService(BaseService):
    """User management service class."""

    def __init__(self, name: str, db_url: str):
        super().__init__(name)
        self.db_url = db_url

    @classmethod
    def create_default(cls) -> "UserService":
        return cls("DefaultUser", "sqlite:///:memory:")

    async def fetch_user(self, user_id: int) -> dict:
        status = self.get_status()
        return {"id": user_id, "status": status}

def calculate_tax(amount: float, rate: float = 0.1) -> float:
    """Calculate tax helper function."""
    return amount * rate
'''
