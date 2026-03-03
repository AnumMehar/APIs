
from fastapi import APIRouter
from app.db.prisma import prisma
from app.schemas.user import UserCreate, UserOut
from app.utils import errors

router = APIRouter()


def normalize_national_id(national_id: str) -> str:
    return national_id.replace("-", "").replace(" ", "")

@router.post("/")
async def create_user(user: UserCreate):
    try:
        normalized_id = user.national_id.replace("-", "").replace(" ", "")

        # Check if user already exists by National_ID
        existing_user = await prisma.user.find_unique(
            where={"national_id": normalized_id}
        )

        if existing_user:
            # User already exists → return existing row
            return {
                "N_ID": existing_user.n_id,
                "uuid": existing_user.uuid,
                "name": existing_user.name,
                "age": existing_user.age,
                "gender": existing_user.gender,
                "national_id": existing_user.national_id,
                "created_at": existing_user.created_at,
                "message": "User already exists. Please proceed to the test."
            }

        # New user → create a new row
        new_user = await prisma.user.create(
            data={
                "name": user.name,
                "age": user.age,
                "gender": user.gender,
                "national_id": normalized_id,
            }
        )

        return {
            "N_ID": new_user.n_id,
            "uuid": new_user.uuid,
            "name": new_user.name,
            "age": new_user.age,
            "gender": new_user.gender,
            "national_id": new_user.national_id,
            "created_at": new_user.created_at,
        }

    except Exception as e:
        print("Error creating user:", e)
        errors.conflict("409: User with this National ID already exists")




