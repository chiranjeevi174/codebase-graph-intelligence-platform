"""Main entry point for sample repository."""

from services.user_service import UserService


def main():
    service = UserService("production_db")
    user = service.create_user("alice", "alice@example.com")
    print(f"Created user: {user}")


if __name__ == "__main__":
    main()
