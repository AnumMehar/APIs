from app.db.prisma import prisma

async def get_db():
    return prisma
