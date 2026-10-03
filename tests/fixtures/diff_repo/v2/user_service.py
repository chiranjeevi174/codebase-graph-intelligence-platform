class UserService:
    def create_user(self, name: str, email: str, role: str = "user") -> dict:
        """Create a user with name, email, and role."""
        return {"name": name, "email": email, "role": role}


def handle_user_creation(name: str, email: str):
    svc = UserService()
    return svc.create_user(name, email, "admin")


def audit_user_signup(name: str, email: str):
    handle_user_creation(name, email)
