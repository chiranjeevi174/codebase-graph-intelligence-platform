class UserService:
    def create_user(self, name: str, email: str) -> dict:
        """Create a user with name and email."""
        return {"name": name, "email": email}


def handle_user_creation(name: str, email: str):
    svc = UserService()
    return svc.create_user(name, email)
