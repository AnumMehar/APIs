from fastapi import FastAPI
from app.routers.local import report, depression, physicalfrailty, dementia, user
from app.routers.cloud import admin, auth, UTRread_only
from app.db.prisma import prisma
from app.db.cloud_db import supabase

app = FastAPI(title="Mental Health Screening API")

@app.on_event("startup")
async def startup():
    await prisma.connect()
    print("✅ Local Database (Prisma) Connected")

    # Supabase (Cloud) doesn't need an 'await connect()'
    # but we can do a simple check here
    print("✅ Cloud Database (Supabase Client) Initialized")

@app.on_event("shutdown")
async def shutdown():
    await prisma.disconnect()

# 🔹 Updated router prefixes
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(user.router, prefix="/users", tags=["Users"])
app.include_router(depression.router, prefix="/depression", tags=["Depression"])
app.include_router(dementia.router, prefix="/dementia", tags=["Dementia"])
app.include_router(physicalfrailty.router, prefix="/physicalfrailty", tags=["PhysicalFrailty"])
app.include_router(report.router, prefix="/report", tags=["Report"])
app.include_router(UTRread_only.router, prefix="/read", tags=["Read"])