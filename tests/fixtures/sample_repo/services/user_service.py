"""User service business logic layer."""

from models.user import User
from repositories.user_repository import UserRepository
from services.base_service import BaseService


class UserService(BaseService):
    """Service handling user creation and management."""

    def __init__(self, db_url: str):
        super().__init__("UserService")
        self.repository = UserRepository(db_url)

    def create_user(self, username: str, email: str) -> User:
        user = User(username=username, email=email)
        return self.repository.save_user(user)
