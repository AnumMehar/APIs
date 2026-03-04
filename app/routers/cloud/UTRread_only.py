# from fastapi import APIRouter , HTTPException
# from app.db.prisma import prisma
# from app.utils import errors
# from app.utils.errors import not_found, internal_server_error
# from typing import List
# from app.schemas.depression import DepressionResponse
# from app.schemas.dementia import DementiaResponse
# from app.schemas.physicalfrailty import PhysicalFrailtyResponse
# from app.routers.local.report import get_latest_tests
#
# router = APIRouter()
#
#
# # ============================================================
# # USERS GET
# # ============================================================
#
# @router.get("/{national_id}")
# async def get_user(national_id: str):
#     try:
#         normalized_id = national_id.replace("-", "").replace(" ", "")
#         user = await prisma.user.find_unique(where={"national_id": normalized_id})
#         if not user:
#             errors.not_found(f"404: User with National_ID {national_id} not found")
#
#         return {
#             "N_ID": user.n_id,
#             "name": user.name,
#             "age": user.age,
#             "gender": user.gender,
#             "national_id": user.national_id,
#             "created_at": user.created_at,
#         }
#
#     except Exception as e:
#         print("Error fetching user:", e)
#         errors.internal_server_error("500: Unable to fetch user.")
#
#
# @router.get("/tests/{national_id}")
# async def get_user_tests(national_id: str):
#     try:
#         normalized_id = national_id.replace("-", "").replace(" ", "")
#         user = await prisma.user.find_unique(where={"national_id": normalized_id})
#         if not user:
#             errors.not_found(f"404: User with National_ID {national_id} not found")
#
#         depression_tests = await prisma.depression_screening.find_many(
#             where={"user_uuid": user.uuid}
#         )
#         dementia_tests = await prisma.dementia_screening.find_many(
#             where={"user_uuid": user.uuid}
#         )
#         frailty = await prisma.physicalfrailty.find_many(
#             where={"user_uuid": user.uuid}
#         )
#
#         return {
#             "N_ID": user.n_id,
#             "name": user.name,
#             "depression_tests": depression_tests,
#             "dementia_tests": dementia_tests,
#             "physical_frailty": frailty
#         }
#
#     except Exception as e:
#         print("Error fetching user tests:", e)
#         errors.internal_server_error("500: Unable to fetch user tests.")
#
# # ============================================================
# # DEPRESSION GET
# # ============================================================
#
# # Get all depression tests by N_ID
# @router.get("/id/{n_id}", response_model=List[DepressionResponse])
# async def get_tests_by_nid(n_id: int):
#     try:
#         user = await prisma.user.find_unique(where={"n_id": n_id})
#         if not user:
#             not_found("404: User with this N_ID not found")
#
#         tests = await prisma.depression_screening.find_many(
#             where={"user_uuid": user.uuid}
#         )
#         return tests
#
#     except Exception as e:
#         print("Error fetching tests by N_ID:", e)
#         internal_server_error("500: Failed to fetch depression tests")
#
#
# # Get all depression tests by National_ID
# @router.get("/Nid/{national_id}", response_model=List[DepressionResponse])
# async def get_tests_by_national_id(national_id: str):
#     try:
#         normalized_id = national_id.replace("-", "").replace(" ", "")
#         user = await prisma.user.find_unique(where={"national_id": normalized_id})
#         if not user:
#             not_found("User with this National_ID not found")
#
#         tests = await prisma.depression_screening.find_many(
#             where={"user_uuid": user.uuid}
#         )
#         return tests
#
#     except Exception as e:
#         print("Error fetching tests by National_ID:", e)
#         internal_server_error("500: Failed to fetch depression tests")
#
#
# # Get a single depression test by dep_test_id
# @router.get("/test/{Dep_test_id}")
# async def get_test_with_user(Dep_test_id: int):
#     try:
#         # 1️⃣ Get the depression test row
#         test = await prisma.depression_screening.find_unique(
#             where={"Dep_test_id": Dep_test_id}
#         )
#         if not test:
#             not_found(f"404: Depression test with ID {Dep_test_id} not found")
#
#         # 2️⃣ Get the user who attempted the test
#         user = await prisma.user.find_unique(
#             where={"uuid": test.user_uuid}
#         )
#         if not user:
#             not_found("404: User associated with this test not found")
#
#         # 3️⃣ Return combined info
#         return {
#             "Dep_test_id": test.Dep_test_id,
#             "user": {
#                 "N_ID": user.n_id,
#                 # "uuid": user.uuid,
#                 "name": user.name,
#                 "age": user.age,
#                 "gender": user.gender,
#                 "national_id": user.national_id,
#                 "created_at": user.created_at,
#             },
#             "answers": {
#                 f"Q{i}_ans": getattr(test, f"Q{i}_ans") for i in range(1, 16)
#             },
#             "scores": {
#                 f"Q{i}_ans_score": getattr(test, f"Q{i}_ans_score") for i in range(1, 16)
#             },
#             "final_scores": test.final_scores,
#             "final_result": test.final_result,
#             "created_at": test.created_at,
#         }
#
#     except Exception as e:
#         print("Error fetching test with user:", e)
#         internal_server_error("500: Failed to fetch depression test with user info")
#
# # ============================================================
# # DEMENTIA GET
# # ============================================================
#
# # 2️⃣ Get all dementia tests by N_ID
# @router.get("/id/{n_id}", response_model=List[DementiaResponse])
# async def get_tests_by_nid(n_id: int):
#     try:
#         user = await prisma.user.find_unique(where={"n_id": n_id})
#         if not user:
#             not_found("404: User with this N_ID not found")
#
#         return await prisma.dementia_screening.find_many(
#             where={"user_uuid": user.uuid}
#         )
#
#     except Exception as e:
#         print("Fetch by N_ID error:", e)
#         internal_server_error("500: Failed to fetch dementia tests")
#
#
# # 3️⃣ Get all dementia tests by National_ID
# @router.get("/Nid/{national_id}", response_model=List[DementiaResponse])
# async def get_tests_by_national_id(national_id: str):
#     try:
#         normalized = national_id.replace("-", "").replace(" ", "")
#         user = await prisma.user.find_unique(where={"national_id": normalized})
#         if not user:
#             not_found("404: User with this National_ID not found")
#
#         return await prisma.dementia_screening.find_many(
#             where={"user_uuid": user.uuid}
#         )
#
#     except Exception as e:
#         print("Fetch by National_ID error:", e)
#         internal_server_error("500: Failed to fetch dementia tests")
#
#
# # 4️⃣ Get dementia test + user by Dem_test_id
# @router.get("/test/{dem_test_id}")
# async def get_test_with_user(dem_test_id: int):
#     try:
#         test = await prisma.dementia_screening.find_unique(
#             where={"dem_test_id": dem_test_id}
#         )
#         if not test:
#             not_found(f"404: Dementia test {dem_test_id} not found")
#
#         user = await prisma.user.find_unique(where={"uuid": test.user_uuid})
#         if not user:
#             not_found("404: User linked to this test not found")
#
#         return {
#             "dem_test_id": test.dem_test_id,
#             "user": {
#                 "n_id": user.n_id,
#                 # "uuid": user.uuid,
#                 "name": user.name,
#                 "age": user.age,
#                 "gender": user.gender,
#                 "national_id": user.national_id,
#             },
#             "answers": {
#                 f"Q{i}_ans": getattr(test, f"Q{i}_ans") for i in range(1, 13)
#             },
#             "points": {
#                 f"Q{i}": {
#                     "possible": getattr(test, f"Q{i}_P_point"),
#                     "earned": getattr(test, f"Q{i}_E_point"),
#                 }
#                 for i in range(1, 13)
#             },
#             "total_earned_point": test.total_earned_point,
#             "final_result": test.final_result,
#             "created_at": test.created_at,
#         }
#
#     except Exception as e:
#         print("Fetch dementia test error:", e)
#         internal_server_error("500: Failed to fetch dementia test")
#
# # ============================================================
# # Physical Frailty GET
# # ============================================================
#
# # ✅ Get all sessions for a user by N_ID
# @router.get("/id/{n_id}", response_model=List[PhysicalFrailtyResponse])
# async def get_by_nid(n_id: int):
#     user = await prisma.user.find_unique(where={"n_id": n_id})
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     sessions = await prisma.physicalfrailty.find_many(
#         where={"User_uuid": user.uuid},
#         order={"created_at": "desc"}
#     )
#     return sessions
#
#
# # ✅ Get all sessions for a user by National_ID
# @router.get("/nid/{national_id}", response_model=List[PhysicalFrailtyResponse])
# async def get_by_national_id(national_id: str):
#     normalized = national_id.replace("-", "").replace(" ", "")
#     user = await prisma.user.find_unique(where={"national_id": normalized})
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     sessions = await prisma.physicalfrailty.find_many(
#         where={"User_uuid": user.uuid},
#         order={"created_at": "desc"}
#     )
#     return sessions
#
#
# # ✅ Get single session by PF_test_id
# @router.get("/test/{pf_test_id}", response_model=PhysicalFrailtyResponse)
# async def get_pf_test(pf_test_id: int):
#     session = await prisma.physicalfrailty.find_unique(where={"PF_test_id": pf_test_id})
#     if not session:
#         raise HTTPException(status_code=404, detail="Physical frailty session not found")
#     return session
#
# # ============================================================
# # Physical Frailty GET
# # ============================================================
#
#
# # GET report by report_test_id
# @router.get("/reportid/{report_test_id}")
# async def get_report_by_test_id(report_test_id: int):
#     report = await prisma.report.find_unique(where={"Report_test_id": report_test_id})
#     if not report:
#         raise HTTPException(404, "Report not found")
#
#     user = await prisma.user.find_unique(where={"uuid": report.user_uuid})
#     tests = await get_latest_tests(user.uuid)
#
#     return {
#         "user": {
#             "N_ID": user.n_id,
#             "name": user.name,
#             "age": user.age,
#             "gender": user.gender,
#             "national_id": user.national_id,
#         },
#         "report": {
#             "Report_test_id": report.Report_test_id,
#             "created_at": report.created_at,
#             "remarks": report.remarks
#         },
#         **tests  # includes depression, dementia, physical_frailty
#     }
#
# # GET reports by N_ID
# @router.get("/nid/{n_id}")
# async def get_reports_by_nid(n_id: int):
#     user = await prisma.user.find_unique(where={"n_id": n_id})
#     if not user:
#         raise HTTPException(404, "User not found")
#
#     reports = await prisma.report.find_many(
#         where={"user_uuid": user.uuid},
#         order={"created_at": "desc"}
#     )
#
#     if not reports:
#         raise HTTPException(404, "No reports found")
#
#     output = []
#
#     for r in reports:
#         # fetch detailed test info
#         dep = await prisma.depression_screening.find_unique(where={"Dep_test_id": r.Dep_test_id}) if r.Dep_test_id else None
#         dem = await prisma.dementia_screening.find_unique(where={"dem_test_id": r.Dem_test_id}) if r.Dem_test_id else None
#         pf = await prisma.physicalfrailty.find_unique(where={"PF_test_id": r.PF_test_id}) if r.PF_test_id else None
#
#         # organize test outputs
#         depression_data = None
#         if dep:
#             depression_data = {
#                 "final_score": dep.final_scores,
#                 "final_result": dep.final_result,
#                 "questions": [
#                     {
#                         "question": f"Q{i}",
#                         "answer": getattr(dep, f"Q{i}_ans"),
#                         "score": getattr(dep, f"Q{i}_ans_score")
#                     }
#                     for i in range(1, 16)
#                 ]
#             }
#
#         dementia_data = None
#         if dem:
#             dementia_data = {
#                 "total_earned_points": dem.total_earned_point,
#                 "final_result": dem.final_result,
#                 "questions": [
#                     {
#                         "question": f"Q{i}",
#                         "answer": getattr(dem, f"Q{i}_ans"),
#                         "possible_points": getattr(dem, f"Q{i}_P_point"),
#                         "earned_points": getattr(dem, f"Q{i}_E_point")
#                     }
#                     for i in range(1, 13)
#                 ]
#             }
#
#         physical_data = None
#         if pf:
#             physical_data = {
#                 "PF_test_id": pf.PF_test_id,
#                 "created_at": pf.created_at,
#                 "session_status": pf.session_status,
#                 "session_date": pf.session_date,
#                 "session_submitted_at": pf.session_submitted_at,
#                 "Walking_speed": pf.Walking_speed,
#                 "walking_speed_created_at": pf.walking_speed_created_at,
#                 # "walking_speed_is_done": frailty.walking_speed_is_done,
#                 "Functional_reach": pf.Functional_reach,
#                 "functional_reach_created_at": pf.functional_reach_created_at,
#                 "Standing_on_one_leg": pf.Standing_on_one_leg,
#                 "standing_on_one_leg_created_at": pf.standing_on_one_leg_created_at,
#                 "Time_up_and_go": pf.Time_up_and_go,
#                 "time_up_and_go_created_at": pf.time_up_and_go_created_at,
#                 "seated_forward_bend": pf.seated_forward_bend,
#                 "seated_forward_bend_created_at": pf.seated_forward_bend_created_at,
#                 "grip_strength": pf.grip_strength,
#                 "grip_strength_created_at": pf.grip_strength_created_at,
#             }
#
#         output.append({
#             "report": {
#                 "Report_test_id": r.Report_test_id,
#                 "created_at": r.created_at,
#                 "remarks": r.remarks
#             },
#             "depression": depression_data,
#             "dementia": dementia_data,
#             "physical_frailty": physical_data
#         })
#
#     return {
#         "user": {
#             "N_ID": user.n_id,
#             "name": user.name,
#             "age": user.age,
#             "gender": user.gender,
#             "national_id": user.national_id,
#         },
#         "reports": output
#     }
#
#
# # GET reports by national_id
# @router.get("/national/{national_id}")
# async def get_reports_by_national_id(national_id: str):
#     clean_id = national_id.replace("-", "").replace(" ", "")
#     user = await prisma.user.find_unique(where={"national_id": clean_id})
#     if not user:
#         raise HTTPException(404, "User not found")
#
#     reports = await prisma.report.find_many(where={"user_uuid": user.uuid}, order={"created_at": "desc"})
#
#     output = []
#     for r in reports:
#         dep = await prisma.depression_screening.find_unique(where={"Dep_test_id": r.Dep_test_id}) if r.Dep_test_id else None
#         dem = await prisma.dementia_screening.find_unique(where={"dem_test_id": r.Dem_test_id}) if r.Dem_test_id else None
#         pf = await prisma.physicalfrailty.find_unique(where={"PF_test_id": r.PF_test_id}) if r.PF_test_id else None
#
#         depression_data = None
#         if dep:
#             depression_data = {
#                 "final_score": dep.final_scores,
#                 "final_result": dep.final_result,
#                 "questions": [
#                     {
#                         "question": f"Q{i}",
#                         "answer": getattr(dep, f"Q{i}_ans"),
#                         "score": getattr(dep, f"Q{i}_ans_score")
#                     }
#                     for i in range(1, 16)
#                 ]
#             }
#
#         dementia_data = None
#         if dem:
#             dementia_data = {
#                 "total_earned_points": dem.total_earned_point,
#                 "final_result": dem.final_result,
#                 "questions": [
#                     {
#                         "question": f"Q{i}",
#                         "answer": getattr(dem, f"Q{i}_ans"),
#                         "possible_points": getattr(dem, f"Q{i}_P_point"),
#                         "earned_points": getattr(dem, f"Q{i}_E_point")
#                     }
#                     for i in range(1, 13)
#                 ]
#             }
#
#         physical_data = None
#         if pf:
#             physical_data = {
#                 "PF_test_id": pf.PF_test_id,
#                 "created_at": pf.created_at,
#                 "session_status": pf.session_status,
#                 "session_date": pf.session_date,
#                 "session_submitted_at": pf.session_submitted_at,
#                 "Walking_speed": pf.Walking_speed,
#                 "walking_speed_created_at": pf.walking_speed_created_at,
#                 # "walking_speed_is_done": frailty.walking_speed_is_done,
#                 "Functional_reach": pf.Functional_reach,
#                 "functional_reach_created_at": pf.functional_reach_created_at,
#                 "Standing_on_one_leg": pf.Standing_on_one_leg,
#                 "standing_on_one_leg_created_at": pf.standing_on_one_leg_created_at,
#                 "Time_up_and_go": pf.Time_up_and_go,
#                 "time_up_and_go_created_at": pf.time_up_and_go_created_at,
#                 "seated_forward_bend": pf.seated_forward_bend,
#                 "seated_forward_bend_created_at": pf.seated_forward_bend_created_at,
#                 "grip_strength": pf.grip_strength,
#                 "grip_strength_created_at": pf.grip_strength_created_at,
#             }
#
#         output.append({
#             "report": {
#                 "Report_test_id": r.Report_test_id,
#                 "created_at": r.created_at,
#                 "remarks": r.remarks
#             },
#             "depression": depression_data,
#             "dementia": dementia_data,
#             "physical_frailty": physical_data
#         })
#
#     return {
#         "user": {
#             "N_ID": user.n_id,
#             "name": user.name,
#             "age": user.age,
#             "gender": user.gender,
#             "national_id": user.national_id,
#         },
#         "reports": output
#     }
#

from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.db.cloud_db import supabase
from app.schemas.depression import DepressionResponse, DepressionOut
from app.schemas.dementia import DementiaResponse, DementiaOut
from app.schemas.physicalfrailty import PhysicalFrailtyResponse, PhysicalFrailtyOut
from app.routers.local.report import get_latest_tests
from app.dependencies.auth import (
    require_super_admin,
    require_doctor,
    get_current_admin,
    doctor_or_admin
)

router = APIRouter()


# ============================================================
# HELPERS
# ============================================================

def normalize_national_id(national_id: str) -> str:
    return national_id.replace("-", "").replace(" ", "")


def get_single(table: str, column: str, value):
    res = (
        supabase
        .table(table)
        .select("*")
        .eq(column, value)
        .single()
        .execute()
    )
    return res.data


def get_many(table: str, column: str, value, order_by: str = None):
    q = supabase.table(table).select("*").eq(column, value)
    if order_by:
        q = q.order(order_by, desc=True)
    return q.execute().data


# ============================================================
# DOCTOR: VIEW MY PATIENTS
# ============================================================

@router.get("/my-patients")
async def my_patients(current=Depends(require_doctor)):
    patients = supabase.table("user") \
        .select("*") \
        .eq("assigned_doctor_uuid", current["uuid"]) \
        .eq("is_deleted", False) \
        .execute().data

    return [
        {
            "name": p["name"],
            "age": p["age"],
            "gender": p["gender"],
            "national_id": p["national_id"]
        }
        for p in patients
    ]

# ============================================================
# GET USERS by National_ID
# ============================================================

@router.get("/{national_id}")
async def get_user(
    national_id: str,
    current=Depends(doctor_or_admin)
):
    user = get_single(
        "user",
        "National_ID",
        normalize_national_id(national_id)
    )

    if not user:
        raise HTTPException(404, f"User with National_ID {national_id} not found")
        # Doctor can only access own patients
    if current["role"] == "doctor":
        if user["assigned_doctor_uuid"] != current["uuid"]:
            raise HTTPException(403, "Not authorized to access this patient")

    return {
        "N_ID": user["N_ID"],
        "name": user["Name"],
        "age": user["Age"],
        "gender": user["Gender"],
        "national_id": user["National_ID"],
        "created_at": user["created_at"],
    }


# ============================================================
# GET DEPRESSION Tests (user serial_id, user national_id, test serial_id)
# ============================================================

@router.get("/depression/id/{n_id}", response_model=List[DepressionOut])
async def get_depression_by_nid(n_id: int, current=Depends(doctor_or_admin)):
    # 1. Get the user's UUID from the 'user' table
    user_query = supabase.table("user").select("uuid").eq("N_ID", n_id).maybe_single().execute()

    if not user_query.data:
        raise HTTPException(status_code=404, detail="User not found")

    user_uuid = user_query.data.get("uuid")

    # 2. Fetch screening data using the user_uuid
    # Note: Use the exact table name 'Depression_Screening'
    response = supabase.table("Depression_Screening").select("*").eq("User_uuid", user_uuid).execute()

    return response.data  # This returns a list of dicts


@router.get("/depression/Nid/{national_id}", response_model=List[DepressionOut])
async def get_depression_by_national_id(national_id: str, current=Depends(doctor_or_admin)):
    user_query = supabase.table("user").select("uuid").eq("National_ID", normalize_national_id(national_id)).maybe_single().execute()

    if not user_query:
        raise HTTPException(404, "User not found")

    user_uuid = user_query.data.get("uuid")
    response = supabase.table("Depression_Screening").select("*").eq("User_uuid", user_uuid).execute()

    return response.data


@router.get("/depressiontest/{Dep_test_id}")
async def get_depression_test(Dep_test_id: int, current=Depends(doctor_or_admin)):
    try:
        # 1. Fetch test (Ensure the table name matches Supabase exactly)
        test_res = supabase.table("Depression_Screening") \
            .select("*") \
            .eq("Dep_test_id", Dep_test_id) \
            .execute()

        if not test_res.data:
            raise HTTPException(404, "Depression test not found")

        test = test_res.data[0]  # Get the first item

        # 2. Fetch User (Note: Use the key returned by Supabase, e.g., 'User_uuid')
        user_uuid = test.get("User_uuid") or test.get("user_uuid")

        user_res = supabase.table("user") \
            .select("*") \
            .eq("uuid", user_uuid) \
            .execute()

        if not user_res.data:
            raise HTTPException(404, "User associated with this test not found")

        user = user_res.data[0]

        # 3. Build response
        return {
            "Dep_test_id": test.get("Dep_test_id"),
            "user": {
                "N_ID": user.get("N_ID") or user.get("n_id"),
                "name": user.get("Name"),
                "age": user.get("Age"),
                "gender": user.get("Gender"),
                "national_id": user.get("National_ID") or user.get("national_id"),
                "created_at": user.get("created_at"),
            },
            "answers": {f"Q{i}_ans": test.get(f"Q{i}_ans") for i in range(1, 16)},
            "scores": {f"Q{i}_ans_score": test.get(f"Q{i}_ans_score") for i in range(1, 16)},
            "final_scores": test.get("Final_scores") or test.get("final_scores"),
            "final_result": test.get("Final_result") or test.get("final_result"),
            "created_at": test.get("created_at"),
        }

    except Exception as e:
        print(f"Supabase Error: {e.message}")
        raise HTTPException(status_code=500, detail=f"Database error: {e.message}")
    except Exception as e:
        print(f"General Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ============================================================
# DEMENTIA GET (user serial_id, user national_id, test serial_id)
# ============================================================

@router.get("/dementia/id/{n_id}", response_model=List[DementiaOut])
async def get_dementia_by_nid(n_id: int, current=Depends(doctor_or_admin)):
    # 1. Fetch user - using standard execute() to avoid the 204 error
    user_res = supabase.table("user").select("uuid").eq("N_ID", n_id).execute()

    if not user_res.data:
        raise HTTPException(status_code=404, detail="User not found")

    # Get the first match
    user_uuid = user_res.data[0].get("uuid")

    # 2. Fetch screening data (Ensure Table name is exactly correct)
    # Using 'Dementia_Screening' as per your previous logic
    response = supabase.table("Dementia_Screening").select("*").eq("User_uuid", user_uuid).execute()

    # Even if no records found, return empty list [] instead of crashing
    return response.data or []


@router.get("/dementia/Nid/{national_id}", response_model=List[DementiaOut])
async def get_dementia_by_national_id(national_id: str, current=Depends(doctor_or_admin)):
    user_query = supabase.table("user").select("uuid").eq("National_ID", normalize_national_id(national_id)).maybe_single().execute()
    if not user_query:
        raise HTTPException(404, "User not found")

    user_uuid = user_query.data.get("uuid")
    response = supabase.table("Dementia_Screening").select("*").eq("User_uuid", user_uuid).execute()

    return response.data


@router.get("/dementiatest/{dem_test_id}")
async def get_dementia_test(dem_test_id: int, current=Depends(doctor_or_admin)):
    try:
        # 1. Fetch test (Ensure the table name matches Supabase exactly)
        test_res = supabase.table("Dementia_Screening") \
            .select("*") \
            .eq("Dem_test_id", dem_test_id) \
            .execute()

        if not test_res.data:
            raise HTTPException(404, "Dementia test not found")

        test = test_res.data[0]  # Get the first item

        # 2. Fetch User (Note: Use the key returned by Supabase, e.g., 'User_uuid')
        user_uuid = test.get("User_uuid") or test.get("user_uuid")

        user_res = supabase.table("user") \
            .select("*") \
            .eq("uuid", user_uuid) \
            .execute()

        if not user_res.data:
            raise HTTPException(404, "User associated with this test not found")

        user = user_res.data[0]

        # 3. Build response
        return {
            "Dem_test_id": test.get("Dem_test_id"),
            "user": {
                "N_ID": user.get("N_ID") or user.get("n_id"),
                "name": user.get("Name"),
                "age": user.get("Age"),
                "gender": user.get("Gender"),
                "national_id": user.get("National_ID") or user.get("national_id"),
                "created_at": user.get("created_at"),
            },
            "answers": {f"Q{i}_ans": test.get(f"Q{i}_ans") for i in range(1, 13)},
            "Possible_points": {f"Q{i}_P_point": test.get(f"Q{i}_P_point") for i in range(1, 13)},
            "Earned_points": {f"Q{i}_E_point": test.get(f"Q{i}_E_point") for i in range(1, 13)},
            "total_earned_point": test.get("Total_earned_point") or test.get("total_earned_point"),
            "final_result": test.get("Final_result") or test.get("final_result"),
            "created_at": test.get("created_at"),
        }

    except Exception as e:
        print(f"Supabase Error: {e.message}")
        raise HTTPException(status_code=500, detail=f"Database error: {e.message}")
    except Exception as e:
        print(f"General Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
# ============================================================
# PHYSICAL FRAILTY GET
# ============================================================

@router.get("/frailty/id/{n_id}", response_model=List[PhysicalFrailtyResponse])
async def get_frailty_by_nid(n_id: int, current=Depends(doctor_or_admin)):
    user_res = supabase.table("user").select("uuid").eq("N_ID", n_id).execute()
    if not user_res.data:
        raise HTTPException(status_code=404, detail="User not found")

        # Get the first match
    user_uuid = user_res.data[0].get("uuid")

    # 2. Fetch screening data (Ensure Table name is exactly correct)
    # Using 'Dementia_Screening' as per your previous logic
    response = supabase.table("physical_frailty").select("*").eq("User_uuid", user_uuid).execute()

    # Even if no records found, return empty list [] instead of crashing
    return response.data or []

@router.get("/frailty/nid/{national_id}", response_model=List[PhysicalFrailtyResponse])
async def get_frailty_by_national_id(national_id: str, current=Depends(doctor_or_admin)):
    user_query = supabase.table("user").select("uuid").eq("National_ID",
                                                          normalize_national_id(national_id)).maybe_single().execute()
    if not user_query:
        raise HTTPException(404, "User not found")
    user_uuid = user_query.data.get("uuid")

    response = supabase.table("physical_frailty").select("*").eq("User_uuid", user_uuid).execute()

    return response.data

@router.get("/frailty/test/{pf_test_id}")
async def get_frailty_test(pf_test_id: int, current=Depends(doctor_or_admin)):
    try:
        # 1. Fetch test (Ensure the table name matches Supabase exactly)
        test_res = supabase.table("physical_frailty") \
            .select("*") \
            .eq("PF_test_id", pf_test_id) \
            .execute()

        if not test_res.data:
            raise HTTPException(404, "Physical Frailty test not found")

        test = test_res.data[0]  # Get the first item

        # 2. Fetch User (Note: Use the key returned by Supabase, e.g., 'User_uuid')
        user_uuid = test.get("User_uuid") or test.get("user_uuid")

        user_res = supabase.table("user") \
            .select("*") \
            .eq("uuid", user_uuid) \
            .execute()

        if not user_res.data:
            raise HTTPException(404, "User associated with this test not found")

        user = user_res.data[0]
        return {
            "PF_test_id": test.get("PF_test_id"),
            "user": {
                "N_ID": user.get("N_ID") or user.get("n_id"),
                "name": user.get("Name"),
                "age": user.get("Age"),
                "gender": user.get("Gender"),
                "national_id": user.get("National_ID") or user.get("national_id"),
                "created_at": user.get("created_at"),
            },
            "physical_frailty": {
                # Walking Speed R1
                "Walking_speed_r1": test.get("Walking_speed_r1") or test.get("walking_speed_r1"),
                "walking_speed_r1_created_at": test.get("walking_speed_r1_created_at"),

                # Functional Reach R1
                "Functional_reach_r1": test.get("Functional_reach_r1") or test.get("functional_reach_r1"),
                "functional_reach_r1_created_at": test.get("functional_reach_r1_created_at"),

                # Standing on one leg R1
                "Standing_on_one_leg_r1": test.get("Standing_on_one_leg_r1") or test.get("standing_on_one_leg_r1"),
                "standing_on_one_leg_r1_created_at": test.get("standing_on_one_leg_r1_created_at"),

                # Time up and go R1
                "Time_up_and_go_r1": test.get("Time_up_and_go_r1") or test.get("time_up_and_go_r1"),
                "time_up_and_go_r1_created_at": test.get("time_up_and_go_r1_created_at"),

                # Seated forward bend R1
                "seated_forward_bend_r1": test.get("seated_forward_bend_r1") or test.get("Seated_forward_bend_r1"),
                "seated_forward_bend_r1_created_at": test.get("seated_forward_bend_r1_created_at"),

                # Walking Speed R2
                "Walking_speed_r2": test.get("Walking_speed_r2") or test.get("walking_speed_r2"),
                "walking_speed_r2_created_at": test.get("walking_speed_r2_created_at"),

                # Functional Reach R2
                "Functional_reach_r2": test.get("Functional_reach_r2") or test.get("functional_reach_r2"),
                "functional_reach_r2_created_at": test.get("functional_reach_r2_created_at"),

                # Standing on one leg R2
                "Standing_on_one_leg_r2": test.get("Standing_on_one_leg_r2") or test.get("standing_on_one_leg_r2"),
                "standing_on_one_leg_r2_created_at": test.get("standing_on_one_leg_r2_created_at"),

                # Time up and go R2
                "Time_up_and_go_r2": test.get("Time_up_and_go_r2") or test.get("time_up_and_go_r2"),
                "time_up_and_go_r2_created_at": test.get("time_up_and_go_r2_created_at"),

                # Seated forward bend R2
                "seated_forward_bend_r2": test.get("seated_forward_bend_r2") or test.get("Seated_forward_bend_r2"),
                "seated_forward_bend_r2_created_at": test.get("seated_forward_bend_r2_created_at"),

                "created_at": test.get("created_at")
            }
        }
    except Exception as e:
        print(f"Supabase Error: {e.message}")
        raise HTTPException(status_code=500, detail=f"Database error: {e.message}")
    except Exception as e:
        print(f"General Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


