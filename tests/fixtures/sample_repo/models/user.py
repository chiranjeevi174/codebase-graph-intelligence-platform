"""User domain model."""


class User:
    """Domain model representing a user entity."""

    def __init__(self, username: str, email: str):
        self.username = username
        self.email = email
