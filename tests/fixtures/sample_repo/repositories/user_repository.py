"""User repository data access layer."""

from models.user import User


class UserRepository:
    """Repository managing user persistence."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    def save_user(self, user: User) -> User:
        print(f"Saving user {user.username} to database at {self.connection_string}")
        return user
