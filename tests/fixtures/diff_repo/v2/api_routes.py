from fastapi import APIRouter

router = APIRouter()


@router.get("/api/users/{id}")
def get_user_by_id(id: int):
    return {"id": id, "name": "Alice"}
