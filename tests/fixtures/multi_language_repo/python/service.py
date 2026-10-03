class BaseService:
    def log(self, msg: str):
        print(f"[LOG] {msg}")

class UserService(BaseService):
    def create_user(self, name: str) -> str:
        self.log(f"Creating user {name}")
        return f"user_{name}"
