# from fastapi import APIRouter, HTTPException, Response, status
# # from app.db.prisma import prisma
# from app.db.cloud_db import supabase
# from app.utils.security import verify_password, create_access_token
# from datetime import datetime
# from app.schemas.auth import LoginRequest
#
# router = APIRouter()
#
#
# @router.post("/login")
# async def login(data: LoginRequest, response: Response):
#
#     # 🔎 Find admin by email
#     admin = await supabase.admin.find_unique(where={"email": data.email})
#
#     if not admin:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid credentials"
#         )
#
#     # 🔐 Verify password
#     if not verify_password(data.password, admin.password_hash):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid credentials"
#         )
#
#     # 🚫 Check active status
#     if not admin.is_active:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Account inactive"
#         )
#
#     # 🕒 Update last login timestamp
#     await supabase.admin.update(
#         where={"uuid": admin.uuid},
#         data={"last_login": datetime.utcnow()}
#     )
#
#     # 🔑 Create RS256 JWT (3 days expiry handled inside create_access_token)
#     token = create_access_token({
#         "sub": admin.uuid,
#         "role": admin.role,
#         "name": admin.name
#     })
#
#     # 🍪 Set secure cookie (3 days)
#     response.set_cookie(
#         key="session",
#         value=token,
#         httponly=True,
#         secure=True,  # set False only during local development
#         samesite="lax",
#         max_age=60 * 60 * 24 * 3  # 3 days
#     )
#
#     return {
#         "message": "Login successful",
#         "role": admin.role,
#         "name": admin.name,
#         "access_token": token,
#         "token_type": "bearer"
#     }
#
#
# @router.post("/logout")
# async def logout(response: Response):
#     response.delete_cookie("session")
#     return {"message": "Logged out"}

from fastapi import APIRouter, HTTPException, Response, status
from datetime import datetime
from app.db.cloud_db import supabase
from app.utils.security import verify_password, create_access_token
from app.schemas.auth import LoginRequest

router = APIRouter()


@router.post("/login")
async def login(data: LoginRequest, response: Response):


    # 🔎 Find admin by email
    res = supabase.table("admin").select("*").eq("email", data.email).single().execute()
    admin = res.data

    if not admin:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    # 🔐 Verify password
    if not verify_password(data.password, admin["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    # 🚫 Check active status
    if not admin["is_active"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account inactive")

    # 🕒 Update last login timestamp
    supabase.table("admin").update({
        "last_login": datetime.utcnow().isoformat()
    }).eq("uuid", admin["uuid"]).execute()

    # 🔑 Create RS256 JWT (3 days expiry handled inside create_access_token)
    token = create_access_token({
        "sub": admin["uuid"],
        "role": admin["role"],
        "name": admin["name"]
    })

    # 🍪 Set secure cookie (3 days)
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 3
    )

    return {
        "message": "Login successful",
        "role": admin["role"],
        "name": admin["name"],
        "access_token": token,
        "token_type": "bearer"
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("session")
    return {"message": "Logged out"}