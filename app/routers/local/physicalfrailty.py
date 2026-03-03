# from fastapi import APIRouter, HTTPException
# from app.db.prisma import prisma
# from datetime import datetime, timezone
# from app.schemas.physicalfrailty import PhysicalFrailtyTestCreate, PhysicalFrailtyResponse
#
# router = APIRouter()
#
# TEST_COLUMN_MAP_R1 = {
#     "walking_speed": "Walking_speed_r1",
#     "functional_reach": "Functional_reach_r1",
#     "standing_on_one_leg": "Standing_on_one_leg_r1",
#     "time_up_and_go": "Time_up_and_go_r1",
#     "seated_forward_bend": "seated_forward_bend_r1"
# }
#
# TEST_COLUMN_MAP_R2 = {
#     "walking_speed": "Walking_speed_r2",
#     "functional_reach": "Functional_reach_r2",
#     "standing_on_one_leg": "Standing_on_one_leg_r2",
#     "time_up_and_go": "Time_up_and_go_r2",
#     "seated_forward_bend": "seated_forward_bend_r2"
# }
#
# @router.post("/round1", response_model=PhysicalFrailtyResponse)
# async def submit_round1(data: PhysicalFrailtyTestCreate):
#
#     test_key = data.test.lower()
#     if test_key not in TEST_COLUMN_MAP_R1:
#         raise HTTPException(400, "Invalid test")
#
#     # Check if user exists
#     user = await prisma.user.find_unique(where={"uuid": str(data.user_uuid)})
#     if not user:
#         raise HTTPException(404, "User not found")
#
#     # -----------------------------
#     # ✅ 6-HOUR SESSION LOGIC HERE
#     # -----------------------------
#     from datetime import datetime, timedelta
#
#     now = datetime.now(timezone.utc)
#     six_hours_ago = now - timedelta(hours=6)
#
#     latest_session = await prisma.physicalfrailty.find_first(
#         where={"User_uuid": str(data.user_uuid)},
#         order={"created_at": "desc"}
#     )
#
#     if not latest_session:
#         create_new = True
#     elif latest_session.created_at < six_hours_ago:
#         create_new = True
#     else:
#         create_new = False
#
#     # -----------------------------
#     # CREATE OR UPDATE
#     # -----------------------------
#
#     if create_new:
#         create_data = {
#             "User_uuid": str(data.user_uuid),
#             TEST_COLUMN_MAP_R1[test_key]: data.value,
#             f"{test_key}_r1_created_at": now,
#             f"{test_key}_r1_is_done": True
#         }
#         record = await prisma.physicalfrailty.create(data=create_data)
#
#     else:
#         update_data = {
#             TEST_COLUMN_MAP_R1[test_key]: data.value,
#             f"{test_key}_r1_created_at": now,
#             f"{test_key}_r1_is_done": True,
#             "sync_status": 0
#         }
#         record = await prisma.physicalfrailty.update(
#             where={"PF_test_id": latest_session.PF_test_id},
#             data=update_data
#         )
#
#     return record
#
#
# # -----------------------------
# # Round 2 API (Button 2)
# # -----------------------------
# @router.post("/round2", response_model=PhysicalFrailtyResponse)
# async def submit_round2(data: PhysicalFrailtyTestCreate):
#
#     test_key = data.test.lower()
#     if test_key not in TEST_COLUMN_MAP_R2:
#         raise HTTPException(400, "Invalid test")
#
#     # Check if user exists
#     user = await prisma.user.find_unique(where={"uuid": str(data.user_uuid)})
#     if not user:
#         raise HTTPException(404, "User not found")
#
#     # Find the latest session of this user (matching Round 1)
#     latest_session = await prisma.physicalfrailty.find_first(
#         where={"User_uuid": str(data.user_uuid)},
#         order={"PF_test_id": "desc"}
#     )
#
#     if not latest_session:
#         raise HTTPException(404, "No session found for this user. Submit Round 1 first.")
#     now = datetime.now(timezone.utc)
#     # Prepare data to update Round 2
#     update_data = {
#         TEST_COLUMN_MAP_R2[test_key]: data.value,
#         f"{test_key}_r2_created_at": now,
#         f"{test_key}_r2_is_done": True,
#         "sync_status": 0
#     }
#
#     # Update the latest session row
#     record = await prisma.physicalfrailty.update(
#         where={"PF_test_id": latest_session.PF_test_id},
#         data=update_data
#     )
#
#     return record

from fastapi import APIRouter, HTTPException
from app.db.prisma import prisma
from datetime import datetime, timezone, timedelta
from app.schemas.physicalfrailty import PhysicalFrailtyTestCreate, PhysicalFrailtyResponse

router = APIRouter()

TEST_COLUMN_MAP_R1 = {
    "walking_speed": "Walking_speed_r1",
    "functional_reach": "Functional_reach_r1",
    "standing_on_one_leg": "Standing_on_one_leg_r1",
    "time_up_and_go": "Time_up_and_go_r1",
    "seated_forward_bend": "seated_forward_bend_r1"
}

TEST_COLUMN_MAP_R2 = {
    "walking_speed": "Walking_speed_r2",
    "functional_reach": "Functional_reach_r2",
    "standing_on_one_leg": "Standing_on_one_leg_r2",
    "time_up_and_go": "Time_up_and_go_r2",
    "seated_forward_bend": "seated_forward_bend_r2"
}

# -----------------------------
# Round 1 API
# -----------------------------
@router.post("/round1", response_model=PhysicalFrailtyResponse)
async def submit_round1(data: PhysicalFrailtyTestCreate):

    test_key = data.test.lower()
    if test_key not in TEST_COLUMN_MAP_R1:
        raise HTTPException(400, "Invalid test")

    # 🔥 Find user by n_id (NOT uuid)
    user = await prisma.user.find_first(
        where={"n_id": data.n_id}
    )

    if not user:
        raise HTTPException(404, "User not found")

    user_uuid = user.uuid  # still use uuid internally

    now = datetime.now(timezone.utc)
    six_hours_ago = now - timedelta(hours=6)

    latest_session = await prisma.physicalfrailty.find_first(
        where={"User_uuid": user_uuid},
        order={"created_at": "desc"}
    )

    if not latest_session or latest_session.created_at < six_hours_ago:
        create_data = {
            "User_uuid": user_uuid,
            TEST_COLUMN_MAP_R1[test_key]: data.value,
            f"{test_key}_r1_created_at": now,
            f"{test_key}_r1_is_done": True,
            "sync_status": 0
        }

        record = await prisma.physicalfrailty.create(data=create_data)

    else:
        update_data = {
            TEST_COLUMN_MAP_R1[test_key]: data.value,
            f"{test_key}_r1_created_at": now,
            f"{test_key}_r1_is_done": True,
            "sync_status": 0
        }

        record = await prisma.physicalfrailty.update(
            where={"PF_test_id": latest_session.PF_test_id},
            data=update_data
        )

    return record

# -----------------------------
# Round 2 API
# -----------------------------
@router.post("/round2", response_model=PhysicalFrailtyResponse)
async def submit_round2(data: PhysicalFrailtyTestCreate):

    test_key = data.test.lower()
    if test_key not in TEST_COLUMN_MAP_R2:
        raise HTTPException(400, "Invalid test")

    # 🔥 Find user by n_id
    user = await prisma.user.find_first(
        where={"n_id": data.n_id}
    )

    if not user:
        raise HTTPException(404, "User not found")

    user_uuid = user.uuid

    latest_session = await prisma.physicalfrailty.find_first(
        where={"User_uuid": user_uuid},
        order={"PF_test_id": "desc"}
    )

    if not latest_session:
        raise HTTPException(404, "No session found for this user. Submit Round 1 first.")

    now = datetime.now(timezone.utc)

    update_data = {
        TEST_COLUMN_MAP_R2[test_key]: data.value,
        f"{test_key}_r2_created_at": now,
        f"{test_key}_r2_is_done": True,
        "sync_status": 0
    }

    record = await prisma.physicalfrailty.update(
        where={"PF_test_id": latest_session.PF_test_id},
        data=update_data
    )

    return record