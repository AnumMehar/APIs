# # from fastapi import APIRouter, HTTPException
# # from typing import List, Optional
# # from datetime import datetime
# # from app.db.prisma import prisma
# # from app.schemas.depression import DepressionSubmit, DepressionResponse
# # from app.services.depression_service import depression_result
# # from app.utils.errors import not_found, internal_server_error
# #
# # router = APIRouter()
# #
# #
# # # ---------------- API ----------------
# # @router.post("/", response_model=DepressionResponse)
# # async def depression_test(data: DepressionSubmit):
# #     try:
# #         record = {}
# #
# #         # ----------- CREATE NEW TEST -----------
# #         if not data.test_id:
# #             if not data.n_id:
# #                 raise HTTPException(status_code=400, detail="N_ID required for new test")
# #             if not data.answers:
# #                 raise HTTPException(status_code=400, detail="answers required for new test")
# #
# #             # Check user exists
# #             user = await prisma.user.find_first(
# #                 where={"n_id": data.n_id}
# #             )
# #
# #             if not user:
# #                 not_found("User not found")
# #
# #
# #             # Map answers and calculate score
# #             final_score = sum(ans.score for ans in data.answers)
# #             record["user_uuid"] = user.uuid             # ✅ Prisma field match
# #             # record["n_id"] = user.n_id
# #             record["final_scores"] = final_score
# #             record["final_result"] = depression_result(final_score)
# #             record["is_submitted"] = False                   # New field
# #             record["completed_at"] = None
# #
# #             for ans in data.answers:
# #                 record[f"Q{ans.question_no}_ans"] = ans.answer
# #                 record[f"Q{ans.question_no}_ans_score"] = ans.score
# #
# #             # Handle final submit
# #             if data.submit_test:
# #                 record["is_submitted"] = True
# #                 record["completed_at"] = datetime.utcnow()
# #
# #             # Create new record in Prisma
# #             result = await prisma.depression_screening.create(data=record)
# #             return result
# #
# #         # ----------- UPDATE EXISTING TEST -----------
# #         test = await prisma.depression_screening.find_unique(
# #             where={"Dep_test_id": data.test_id}
# #         )
# #         if not test:
# #             raise HTTPException(status_code=404, detail="Depression test not found")
# #         if getattr(test, "is_submitted", False):
# #             raise HTTPException(status_code=400, detail="Test already submitted")
# #
# #         # Merge new answers with existing ones
# #         existing_scores = [
# #             getattr(test, f"Q{i}_ans_score") or 0 for i in range(1, 16)
# #         ]
# #
# #         if data.answers:
# #             for ans in data.answers:
# #                 record[f"Q{ans.question_no}_ans"] = ans.answer
# #                 record[f"Q{ans.question_no}_ans_score"] = ans.score
# #                 existing_scores[ans.question_no - 1] = ans.score
# #
# #             record["final_scores"] = sum(existing_scores)
# #             record["final_result"] = depression_result(sum(existing_scores))
# #
# #         # Handle final submit
# #         if data.submit_test:
# #             record["is_submitted"] = True
# #             record["completed_at"] = datetime.utcnow()
# #         else:
# #             record["is_submitted"] = False
# #             record["completed_at"] = None
# #
# #         record["sync_status"] = 0
# #         # Update record in Prisma
# #         updated = await prisma.depression_screening.update(
# #             where={"Dep_test_id": data.test_id},
# #             data=record
# #         )
# #         return updated
# #
# #     except Exception as e:
# #         print("Depression error:", e)
# #         internal_server_error("Failed depression test operation")
#
# from fastapi import APIRouter, HTTPException
# from app.schemas.depression import DepressionSubmit, DepressionResponse
# from app.db.prisma import prisma
# from app.services.depression_service import depression_result
# from app.utils.errors import internal_server_error
# from datetime import datetime
#
# router = APIRouter()
#
#
# @router.post("/", response_model=DepressionResponse)
# async def depression_test(data: DepressionSubmit):
#     try:
#
#         # =====================================================
#         # CASE 1: test_id PROVIDED → UPDATE DIRECTLY
#         # =====================================================
#         if data.test_id:
#
#             existing_test = await prisma.depression_screening.find_unique(
#                 where={"dep_test_id": data.test_id}
#             )
#
#             if not existing_test:
#                 raise HTTPException(status_code=404, detail="Test not found")
#
#             if existing_test.is_submitted:
#                 raise HTTPException(status_code=400, detail="Test already submitted")
#
#             user_uuid = existing_test.user_uuid
#
#         # =====================================================
#         # CASE 2: NO test_id → REQUIRE N_ID
#         # =====================================================
#         else:
#
#             if not data.n_id:
#                 raise HTTPException(status_code=400, detail="N_ID is required")
#
#             user = await prisma.user.find_first(
#                 where={"n_id": data.n_id}
#             )
#
#             if not user:
#                 raise HTTPException(status_code=404, detail="User not found")
#
#             user_uuid = user.uuid
#
#             # Check existing in-progress test
#             existing_test = await prisma.depression_screening.find_first(
#                 where={
#                     "user_uuid": user_uuid,
#                     "is_submitted": False
#                 }
#             )
#
#         # =====================================================
#         # UPDATE EXISTING TEST
#         # =====================================================
#         if existing_test:
#
#             update_data = {}
#
#             # Update only provided questions
#             if data.questions:
#                 for q in data.questions:
#                     update_data[f"Q{q.no}_ans"] = q.answer
#                     update_data[f"Q{q.no}_ans_score"] = q.score
#
#             # Recalculate total safely (Assuming 9 questions)
#             scores = []
#             for i in range(1, 10):
#                 if data.questions and any(q.no == i for q in data.questions):
#                     score = next(q.score for q in data.questions if q.no == i)
#                 else:
#                     score = getattr(existing_test, f"Q{i}_ans_score") or 0
#                 scores.append(score)
#
#             total = sum(scores)
#
#             update_data["final_score"] = total
#             update_data["final_result"] = depression_result(total)
#
#             # Handle submission
#             if data.submit_test:
#                 update_data["is_submitted"] = True
#                 update_data["completed_at"] = datetime.utcnow()
#
#             update_data["sync_status"] = 0
#
#             updated = await prisma.depression_screening.update(
#                 where={"dep_test_id": existing_test.dep_test_id},
#                 data=update_data
#             )
#
#             return updated
#
#         # =====================================================
#         # CREATE NEW TEST
#         # =====================================================
#         else:
#
#             if not data.questions:
#                 raise HTTPException(status_code=400, detail="Questions required")
#
#             total = sum(q.score for q in data.questions)
#
#             create_data = {
#                 "user_uuid": user_uuid,
#                 "final_score": total,
#                 "final_result": depression_result(total),
#                 "is_submitted": data.submit_test or False,
#                 "completed_at": datetime.utcnow() if data.submit_test else None,
#                 "sync_status": 0
#             }
#
#             for q in data.questions:
#                 create_data[f"Q{q.no}_ans"] = q.answer
#                 create_data[f"Q{q.no}_ans_score"] = q.score
#
#             new_test = await prisma.depression_screening.create(
#                 data=create_data
#             )
#
#             return new_test
#
#     except Exception as e:
#         print("Depression error:", e)
#         internal_server_error("Failed depression test operation")

from fastapi import APIRouter, HTTPException
from app.schemas.depression import DepressionSubmit, DepressionResponse
from app.db.prisma import prisma
from app.services.depression_service import depression_result
from app.utils.errors import internal_server_error
from datetime import datetime

router = APIRouter()


@router.post("/", response_model=DepressionResponse)
async def depression_test(data: DepressionSubmit):
    try:

        # =====================================================
        # CASE 1: test_id PROVIDED → UPDATE DIRECTLY
        # =====================================================
        if data.test_id:

            existing_test = await prisma.depression_screening.find_unique(
                where={"Dep_test_id": data.test_id}
            )

            if not existing_test:
                raise HTTPException(status_code=404, detail="Test not found")

            if existing_test.is_submitted:
                raise HTTPException(status_code=400, detail="Test already submitted")

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

            # Check if in-progress test already exists
            existing_test = await prisma.depression_screening.find_first(
                where={
                    "user_uuid": user_uuid,
                    "is_submitted": False
                }
            )

        # =====================================================
        # UPDATE EXISTING TEST
        # =====================================================
        if existing_test:

            update_data = {}

            # Update only provided answers
            if data.answers:
                for ans in data.answers:
                    update_data[f"Q{ans.question_no}_ans"] = ans.answer
                    update_data[f"Q{ans.question_no}_ans_score"] = ans.score

            # Recalculate total safely (Assuming 15 questions)
            scores = []
            for i in range(1, 16):
                if data.answers and any(a.question_no == i for a in data.answers):
                    score = next(a.score for a in data.answers if a.question_no == i)
                else:
                    score = getattr(existing_test, f"Q{i}_ans_score") or 0
                scores.append(score)

            total = sum(scores)

            update_data["final_scores"] = total
            update_data["final_result"] = depression_result(total)

            # Handle submission
            if data.submit_test:
                update_data["is_submitted"] = True
                update_data["completed_at"] = datetime.utcnow()

            update_data["sync_status"] = 0

            updated = await prisma.depression_screening.update(
                where={"Dep_test_id": existing_test.Dep_test_id},
                data=update_data
            )

            return updated

        # =====================================================
        # CREATE NEW TEST
        # =====================================================
        else:

            if not data.answers:
                raise HTTPException(status_code=400, detail="Answers required")

            total = sum(ans.score for ans in data.answers)

            create_data = {
                "user_uuid": user_uuid,
                "final_scores": total,
                "final_result": depression_result(total),
                "is_submitted": data.submit_test or False,
                "completed_at": datetime.utcnow() if data.submit_test else None,
                "sync_status": 0
            }

            for ans in data.answers:
                create_data[f"Q{ans.question_no}_ans"] = ans.answer
                create_data[f"Q{ans.question_no}_ans_score"] = ans.score

            new_test = await prisma.depression_screening.create(
                data=create_data
            )

            return new_test

    except Exception as e:
        print("Depression error:", e)
        internal_server_error("Failed depression test operation")