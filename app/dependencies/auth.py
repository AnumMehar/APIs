# from fastapi import Request, HTTPException, Depends
# from app.utils.security import verify_token
# from app.db.prisma import prisma
#
#
# async def get_current_admin(request: Request):
#
#     token = request.cookies.get("session")
#     if not token:
#         raise HTTPException(401, "Not authenticated")
#
#     try:
#         payload = verify_token(token)
#         admin_uuid = payload.get("sub")
#
#         admin = await prisma.admin.find_unique(where={"uuid": admin_uuid})
#
#         if not admin or not admin.is_active:
#             raise HTTPException(403, "Access denied")
#
#         return admin
#
#     except:
#         raise HTTPException(401, "Invalid or expired session")
#
#
# def require_super_admin(current=Depends(get_current_admin)):
#     if current.role != "super_admin":
#         raise HTTPException(403, "Super Admin only")
#     return current
#
#
# def require_doctor(current=Depends(get_current_admin)):
#     if current.role != "doctor":
#         raise HTTPException(403, "Doctor only")
#     return current
#
# def doctor_or_admin(current=Depends(get_current_admin)):
#     if current.role not in ["doctor", "super_admin"]:
#         raise HTTPException(status_code=403, detail="Not authorized")
#     return current

from fastapi import Request, HTTPException, Depends
from app.utils.security import verify_token
from app.db.cloud_db import supabase


async def get_current_admin(request: Request):
    token = request.cookies.get("session") or request.headers.get("Authorization")

    if token and token.startswith("Bearer "):
        token = token[7:]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = verify_token(token)
        admin_uuid = payload.get("sub")

        if not admin_uuid:
            raise HTTPException(401, "Invalid token payload")

        res = supabase.table("admin") \
            .select("*") \
            .eq("uuid", admin_uuid) \
            .eq("is_active", True) \
            .single() \
            .execute()

        if not res.data:
            raise HTTPException(403, "Access denied")

        return res.data

    except HTTPException:
        raise
    except Exception as e:
        print("AUTH ERROR:", e)
        raise HTTPException(401, "Invalid or expired session")


def require_super_admin(current=Depends(get_current_admin)):
    if current["role"] != "super_admin":
        raise HTTPException(403, "Super Admin only")
    return current


def require_doctor(current=Depends(get_current_admin)):
    if current["role"] != "doctor":
        raise HTTPException(403, "Doctor only")
    return current


def doctor_or_admin(current=Depends(get_current_admin)):
    if current["role"] not in ["doctor", "super_admin"]:
        raise HTTPException(403, "Not authorized")
    return current