from fastapi import FastAPI

app = FastAPI()


@app.get("/api/users")
def get_users_api():
    return [{"id": 1, "name": "Alice"}]
