from python.service import UserService


def run():
    service = UserService()
    service.create_user("Alice")


if __name__ == "__main__":
    run()
