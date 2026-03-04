from fastapi import APIRouter, HTTPException
from app.schemas.dementia import DementiaSubmit, DementiaResponse
from app.db.prisma import prisma
from app.services.dementia_service import dementia_result
from app.utils.errors import not_found, internal_server_error
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=DementiaResponse)
async def dementia_test(data: DementiaSubmit):
    try:
        # ===============================
        # IF test_id PROVIDED → UPDATE DIRECTLY
        # ===============================
        if data.test_id:

            existing_test = await prisma.dementia_screening.find_unique(
                where={"dem_test_id": data.test_id}
            )

            if not existing_test:
                raise HTTPException(status_code=404, detail="Test not found")

            if existing_test.is_submitted:
                raise HTTPException(status_code=400, detail="Test already submitted")

            # 👉 DO NOT TOUCH USER TABLE HERE
            user_uuid = existing_test.user_uuid

            # =====================================================
            # CASE 2: NO test_id → REQUIRE N_ID
            # =====================================================
        else:

            if not data.n_id:
                raise HTTPException(status_code=400, detail="N_ID is required")

            user = await prisma.user.find_first(
                where={"n_id": data.n_id}
            )

            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            user_uuid = user.uuid

            existing_test = await prisma.dementia_screening.find_first(
                where={
                    "user_uuid": user_uuid,
                    "is_submitted": False
                }
            )

        # =====================================================
        # 🔄 UPDATE EXISTING TEST
        # =====================================================
        if existing_test:

            update_data = {}

            # Update only provided questions
            if data.questions:
                for q in data.questions:
                    update_data[f"Q{q.no}_ans"] = q.answer
                    update_data[f"Q{q.no}_P_point"] = q.possible
                    update_data[f"Q{q.no}_E_point"] = q.earned

            # Recalculate total safely
            earned_points = []
            for i in range(1, 13):
                if data.questions and any(q.no == i for q in data.questions):
                    earned = next(q.earned for q in data.questions if q.no == i)
                else:
                    earned = getattr(existing_test, f"Q{i}_E_point") or 0
                earned_points.append(earned)

            total = sum(earned_points)
            update_data["total_earned_point"] = total
            update_data["final_result"] = dementia_result(total)

            # Handle submission
            if data.submit_test:
                update_data["is_submitted"] = True
                update_data["completed_at"] = datetime.utcnow()

            update_data["sync_status"] = 0

            updated = await prisma.dementia_screening.update(
                where={"dem_test_id": existing_test.dem_test_id},
                data=update_data
            )
            return updated

        # =====================================================
        # 🆕 CREATE NEW TEST
        # =====================================================
        else:
            if not data.questions:
                raise HTTPException(status_code=400, detail="Questions required")

            total = sum(q.earned for q in data.questions)

            create_data = {
                "user_uuid": user.uuid,
                "total_earned_point": total,
                "final_result": dementia_result(total),
                "is_submitted": data.submit_test or False,
                "completed_at": datetime.utcnow() if data.submit_test else None,
                "sync_status": 0
            }

            for q in data.questions:
                create_data[f"Q{q.no}_ans"] = q.answer
                create_data[f"Q{q.no}_P_point"] = q.possible
                create_data[f"Q{q.no}_E_point"] = q.earned

            new_test = await prisma.dementia_screening.create(data=create_data)
            return new_test

    except Exception as e:
        print("Dementia error:", e)

        internal_server_error("Failed dementia test operation")
