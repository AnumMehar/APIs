# # app/routers/admin.py
#
# from fastapi import APIRouter, Depends, HTTPException
# from datetime import datetime
# from app.db.prisma import prisma
# from app.db.cloud_db import supabase
# from app.utils import errors
# from app.dependencies.auth import require_super_admin, require_doctor, get_current_admin, doctor_or_admin
# from app.routers.local.report import get_latest_tests
# from app.utils.security import hash_password
# from app.schemas.admin import (
#     CreateDoctorSchema,
#     ResetDoctorPasswordSchema,
#     ChangePasswordSchema,
#     AssignDoctorSchema,
#     EditUserSchema
# )
#
# router = APIRouter()
#
# # ============================================================
# # SUPER ADMIN: CREATE DOCTOR
# # ============================================================
#
# @router.post("/create-doctor")
# async def create_doctor(
#     payload: CreateDoctorSchema,
#     current=Depends(require_super_admin)
# ):
#     existing = await supabase.admin.find_unique(where={"email": payload.email})
#     if existing:
#         raise HTTPException(status_code=400, detail="Email already exists")
#
#     doctor = await supabase.admin.create(
#         data={
#             "name": payload.name,
#             "email": payload.email,
#             "password_hash": hash_password(payload.password),
#             "role": "doctor",
#             "created_at": datetime.utcnow(),
#             "updated_at": datetime.utcnow()
#         }
#     )
#
#     return {"message": "Doctor created", "doctor_uuid": doctor.uuid}
#
#
# # ============================================================
# # SUPER ADMIN: VIEW ALL DOCTORS
# # ============================================================
#
# @router.get("/doctors")
# async def view_all_doctors(current=Depends(require_super_admin)):
#     return await supabase.admin.find_many(
#         where={"role": "doctor"},
#         order={"created_at": "desc"}
#     )
#
#
# # ============================================================
# # SUPER ADMIN: DELETE DOCTOR (HARD DELETE)
# # ============================================================
#
# @router.post("/delete-doctor/{doctor_uuid}")
# async def delete_doctor(
#     doctor_uuid: str,
#     current=Depends(require_super_admin)
# ):
#     doctor = await supabase.admin.find_unique(where={"uuid": doctor_uuid})
#
#     if not doctor or doctor.role != "doctor":
#         raise HTTPException(status_code=404, detail="Doctor not found")
#
#     return await supabase.admin.delete(where={"uuid": doctor_uuid})
#
# # ============================================================
# # CHANGE OWN PASSWORD (Doctor + Super Admin)
# # ============================================================
#
# @router.post("/change-password")
# async def change_password(
#     payload: ChangePasswordSchema,
#     current = Depends(get_current_admin)
# ):
#
#     from app.utils.security import verify_password, hash_password
#
#     # 1️⃣ Verify old password
#     if not verify_password(payload.old_password, current.password_hash):
#         raise HTTPException(status_code=400, detail="Incorrect old password")
#
#     # 2️⃣ Prevent same password reuse
#     if verify_password(payload.new_password, current.password_hash):
#         raise HTTPException(status_code=400, detail="New password cannot be same as old password")
#
#     # 3️⃣ Update password
#     await supabase.admin.update(
#         where={"uuid": current.uuid},
#         data={
#             "password_hash": hash_password(payload.new_password),
#             "updated_at": datetime.utcnow()
#         }
#     )
#
#     return {"message": "Password changed successfully"}
#
# # ============================================================
# # SUPER ADMIN: RESET DOCTOR PASSWORD
# # ============================================================
#
# @router.post("/reset-doctor-password/{doctor_uuid}")
# async def reset_doctor_password(
#     doctor_uuid: str,
#     payload: ResetDoctorPasswordSchema,
#     current=Depends(require_super_admin)
# ):
#     doctor = await supabase.admin.find_unique(where={"uuid": doctor_uuid})
#
#     if not doctor or doctor.role != "doctor":
#         raise HTTPException(404, "Doctor not found")
#
#     await supabase.admin.update(
#         where={"uuid": doctor_uuid},
#         data={
#             "password_hash": hash_password(payload.new_password),
#             "updated_at": datetime.utcnow()
#         }
#     )
#
#     return {"message": "Doctor password reset successfully"}
# # ============================================================
# # SUPER ADMIN: ASSIGN DOCTOR TO PATIENT
# # ============================================================
#
# @router.post("/assign-doctor/{user_uuid}")
# async def assign_doctor(
#     user_uuid: str,
#     payload: AssignDoctorSchema,
#     current=Depends(require_super_admin)
# ):
#     # Check doctor exists
#     doctor = await supabase.admin.find_unique(where={"uuid": payload.doctor_uuid})
#     if not doctor or doctor.role != "doctor":
#         raise HTTPException(status_code=400, detail="Invalid doctor")
#
#     # Check user exists
#     user = await supabase.user.find_unique(where={"uuid": user_uuid})
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     # Update assignment
#     updated_user = await supabase.user.update(
#         where={"uuid": user_uuid},
#         data={
#             "assigned_doctor_uuid": payload.doctor_uuid,
#             "updated_at": datetime.utcnow()
#         }
#     )
#
#     return {
#         "message": "Doctor assigned successfully",
#         "patient_name": updated_user.name,
#         "patient_uuid": updated_user.uuid,
#         "assigned_doctor_uuid": updated_user.assigned_doctor_uuid
#     }
#
# # ============================================================
# # SUPER ADMIN: EDIT USER
# # ============================================================
#
# @router.post("/update/{user_uuid}")
# async def edit_user(
#     user_uuid: str,
#     payload: EditUserSchema,
#     current=Depends(require_super_admin)
# ):
#     user = await supabase.user.find_unique(where={"uuid": user_uuid})
#
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     return await supabase.user.update(
#         where={"uuid": user_uuid},
#         data={
#             "name": payload.name if payload.name else user.name,
#             "age": payload.age if payload.age else user.age,
#             "gender": payload.gender if payload.gender else user.gender,
#             "national_id": payload.national_id if payload.national_id else user.national_id,
#             "updated_at": datetime.utcnow()
#         }
#     )
#
# # ============================================================
# # SUPER ADMIN: DELETE USER (HARD DELETE)
# # ============================================================
#
# @router.delete("/delete-user/{user_uuid}")
# async def delete_user(
#     user_uuid: str,
#     current=Depends(require_super_admin)
# ):
#     user = await supabase.user.find_unique(where={"uuid": user_uuid})
#
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     return await supabase.user.delete(where={"uuid": user_uuid})
#
#
# # ============================================================
# # SUPER ADMIN: DELETE INVALID TEST
# # ============================================================
#
# @router.delete("/delete-test/{test_type}/{test_id}")
# async def delete_invalid_test(
#     test_type: str,
#     test_id: int,
#     current=Depends(require_super_admin)
# ):
#     if test_type == "depression":
#         return await supabase.depression_screening.delete(
#             where={"Dep_test_id": test_id}
#         )
#
#     elif test_type == "dementia":
#         return await supabase.dementia_screening.delete(
#             where={"dem_test_id": test_id}
#         )
#
#     elif test_type == "physical":
#         return await supabase.physicalfrailty.delete(
#             where={"PF_test_id": test_id}
#         )
#
#     else:
#         raise HTTPException(status_code=400, detail="Invalid test type")
#
# # ============================================================
# # SUPER ADMIN: DELETE REPORT
# # ============================================================
#
# @router.delete("/delete-report/{report_id}")
# async def delete_report(
#     report_id: int,
#     current=Depends(require_super_admin)
# ):
#     report = await supabase.report.find_unique(
#         where={"Report_test_id": report_id}
#     )
#
#     if not report:
#         raise HTTPException(status_code=404, detail="Report not found")
#
#     return await supabase.report.delete(
#         where={"Report_test_id": report_id}
#     )
#
#
# # ============================================================
# # TRACK WHICH DOCTOR GENERATED REPORT
# # ============================================================
#
# @router.get("/report-generator/{report_id}")
# async def report_generator(
#     report_id: int,
#     current=Depends(require_super_admin)
# ):
#     report = await supabase.report.find_unique(
#         where={"Report_test_id": report_id},
#         include={"generator": True}
#     )
#
#     if not report:
#         raise HTTPException(404, "Report not found")
#
#     return {
#         "report_id": report.Report_test_id,
#         "doctor_name": report.generator.name if report.generator else None,
#         "doctor_email": report.generator.email if report.generator else None
#     }
#
# # ============================================================
# # DOCTOR: VIEW MY PATIENTS
# # ============================================================
#
# @router.get("/my-patients")
# async def my_patients(current=Depends(require_doctor)):
#
#     patients = await supabase.user.find_many(
#         where={
#             "assigned_doctor_uuid": current.uuid,
#             "is_deleted": False
#         }
#     )
#
#     return [
#         {
#             "name": p.name,
#             "age": p.age,
#             "gender": p.gender,
#             "national_id": p.national_id
#         }
#         for p in patients
#     ]
#
# # ============================================================
# # DOCTOR and admin:  view report by report ID
# # ============================================================
# @router.get("/reportid/{report_test_id}")
# async def get_report_by_test_id(
#     report_test_id: int,
#     current=Depends(doctor_or_admin)
# ):
#     report = await supabase.report.find_unique(where={"Report_test_id": report_test_id})
#     if not report:
#         raise HTTPException(404, "Report not found")
#
#     user = await supabase.user.find_unique(where={"uuid": report.user_uuid})
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
# # ============================================================
# # DOCTOR and admin:  view report by serial ID
# # ============================================================
# # GET reports by N_ID
# @router.get("/serial/{n_id}")
# async def get_reports_by_nid(n_id: int,
#     current = Depends(doctor_or_admin)
# ):
#     user = await supabase.user.find_unique(where={"n_id": n_id})
#     if not user:
#         raise HTTPException(404, "User not found")
#
#     reports = await supabase.report.find_many(
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
#         dep = await supabase.depression_screening.find_unique(where={"Dep_test_id": r.Dep_test_id}) if r.Dep_test_id else None
#         dem = await supabase.dementia_screening.find_unique(where={"dem_test_id": r.Dem_test_id}) if r.Dem_test_id else None
#         pf = await supabase.physicalfrailty.find_unique(where={"PF_test_id": r.PF_test_id}) if r.PF_test_id else None
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
# #============================================================
# # DOCTOR and admin: VIEW report by National_ID
# # ============================================================
# @router.get("/national/{national_id}")
# async def get_reports_by_national_id(
#     national_id: str,
#     current=Depends(doctor_or_admin)
# ):
#     clean_id = national_id.replace("-", "").replace(" ", "")
#     user = await supabase.user.find_unique(where={"national_id": clean_id})
#     if not user:
#         raise HTTPException(404, "User not found")
#
#     reports = await supabase.report.find_many(where={"user_uuid": user.uuid}, order={"created_at": "desc"})
#
#     output = []
#     for r in reports:
#         dep = await supabase.depression_screening.find_unique(
#             where={"Dep_test_id": r.Dep_test_id}) if r.Dep_test_id else None
#         dem = await supabase.dementia_screening.find_unique(
#             where={"dem_test_id": r.Dem_test_id}) if r.Dem_test_id else None
#         pf = await supabase.physicalfrailty.find_unique(where={"PF_test_id": r.PF_test_id}) if r.PF_test_id else None
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
# #============================================================
# # DOCTOR and admin: VIEW all reports
# # ============================================================
# @router.get("/reports")
# async def get_all_reports(current=Depends(doctor_or_admin)):
#     return await supabase.report.find_many()
#
# #============================================================
# # DOCTOR and admin: Tests results by National_ID
# # ============================================================
# @router.get("/tests/by-national/{national_id}")
# async def get_user_tests(
#     national_id: str,
#     current=Depends(doctor_or_admin)
# ):
#     try:
#         normalized_id = national_id.replace("-", "").replace(" ", "")
#         user = await supabase.user.find_unique(where={"national_id": normalized_id})
#         if not user:
#             errors.not_found(f"404: User with National_ID {national_id} not found")
#
#         depression_tests = await supabase.depression_screening.find_many(
#             where={"user_uuid": user.uuid}
#         )
#         dementia_tests = await supabase.dementia_screening.find_many(
#             where={"user_uuid": user.uuid}
#         )
#         frailty = await supabase.physicalfrailty.find_many(
#             where={"User_uuid": user.uuid}
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
# #============================================================
# # DOCTOR and admin: View all users
# # ============================================================
# @router.get("/users")
# async def view_all_users(current=Depends(doctor_or_admin)):
#     return await supabase.user.find_many(
#         where={"is_deleted": False}
#     )
#
# #============================================================
# # DOCTOR and admin: View all tests
# # ============================================================
# @router.get("/tests")
# async def view_all_tests(current=Depends(doctor_or_admin)):
#
#     return {
#         "depression": await supabase.depression_screening.find_many(),
#         "dementia": await supabase.dementia_screening.find_many(),
#         "physical_frailty": await supabase.physicalfrailty.find_many(),
#     }

# app/routers/admin.py

from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from app.db.cloud_db import supabase
from app.utils import errors
from app.schemas.admin import DeleteDoctorSchema
from app.dependencies.auth import (
    require_super_admin,
    require_doctor,
    get_current_admin,
    doctor_or_admin
)
from app.routers.local.report import get_latest_tests
from app.utils.security import hash_password, verify_password
from app.schemas.admin import (
    CreateDoctorSchema,
    ResetDoctorPasswordSchema,
    ChangePasswordSchema,
    AssignDoctorSchema,
    EditUserSchema
)

router = APIRouter()

# ============================================================
# SUPER ADMIN: CREATE DOCTOR
# ============================================================

@router.post("/create-doctor")
async def create_doctor(payload: CreateDoctorSchema, current=Depends(require_super_admin)):
    existing = supabase.table("admin").select("uuid").eq("email", payload.email).execute()
    if existing.data:
        raise HTTPException(400, "Email already exists")

    res = supabase.table("admin").insert({
        "name": payload.name,
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "role": "doctor",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }).execute()

    return {"message": "Doctor created", "doctor_uuid": res.data[0]["uuid"]}

# ============================================================
# SUPER ADMIN: VIEW ALL DOCTORS
# ============================================================

@router.get("/doctors")
async def view_all_doctors(current=Depends(require_super_admin)):
    return supabase.table("admin") \
        .select("name, email, created_at, last_login") \
        .eq("role", "doctor") \
        .order("created_at", desc=True) \
        .execute().data

# ============================================================
# SUPER ADMIN: DELETE DOCTOR
# ============================================================

@router.post("/delete-doctor")
async def delete_doctor(payload: DeleteDoctorSchema, current=Depends(require_super_admin)):
    doctor = supabase.table("admin").select("*").eq("email", payload.email).eq("role", "doctor").single().execute()

    if not doctor.data:
        raise HTTPException(404, "Doctor not found")

    supabase.table("admin").delete().eq("email", payload.email).execute()
    return {"message": "Doctor deleted"}

# ============================================================
# CHANGE OWN PASSWORD
# ============================================================

@router.post("/change-password")
async def change_password(payload: ChangePasswordSchema, current=Depends(get_current_admin)):
    if not verify_password(payload.old_password, current["password_hash"]):
        raise HTTPException(400, "Incorrect old password")

    if verify_password(payload.new_password, current["password_hash"]):
        raise HTTPException(400, "New password cannot be same as old password")

    supabase.table("admin").update({
        "password_hash": hash_password(payload.new_password),
        "updated_at": datetime.utcnow().isoformat()
    }).eq("uuid", current["uuid"]).execute()

    return {"message": "Password changed successfully"}

# ============================================================
# SUPER ADMIN: RESET DOCTOR PASSWORD
# ============================================================

@router.post("/reset-doctor-password/{doctor_uuid}")
async def reset_doctor_password(doctor_uuid: str, payload: ResetDoctorPasswordSchema,
                                current=Depends(require_super_admin)):
    doctor = supabase.table("admin").select("*").eq("uuid", doctor_uuid).single().execute()
    if not doctor.data or doctor.data["role"] != "doctor":
        raise HTTPException(404, "Doctor not found")

    supabase.table("admin").update({
        "password_hash": hash_password(payload.new_password),
        "updated_at": datetime.utcnow().isoformat()
    }).eq("uuid", doctor_uuid).execute()

    return {"message": "Doctor password reset successfully"}

# ============================================================
# SUPER ADMIN: ASSIGN DOCTOR TO PATIENT
# ============================================================

@router.post("/assign-doctor/{user_uuid}")
async def assign_doctor(user_uuid: str, payload: AssignDoctorSchema,
                        current=Depends(require_super_admin)):
    doctor = supabase.table("admin") \
        .select("uuid, name") \
        .eq("uuid", payload.doctor_uuid) \
        .eq("role", "doctor") \
        .single() \
        .execute()
    if not doctor.data:
        raise HTTPException(400, "Invalid doctor")
    doctor_name = doctor.data["name"]

    user = supabase.table("user").select("*").eq("uuid", user_uuid).single().execute()
    if not user.data:
        raise HTTPException(404, "User not found")

    updated = supabase.table("user").update({
        "assigned_doctor_uuid": payload.doctor_uuid,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("uuid", user_uuid).execute()

    return {
        "message": "Doctor assigned successfully",
        "patient_name": updated.data[0]["Name"],
        "patient_age": updated.data[0]["Age"],
        "patient_gender": updated.data[0]["Gender"],
        "patient_national_id": updated.data[0]["National_ID"],
        # "assigned_doctor_uuid": updated.data[0]["uuid"],
        "assigned_doctor_name": doctor_name
    }

# ============================================================
# SUPER ADMIN: EDIT USER
# ============================================================

@router.post("/update/{user_uuid}")
async def edit_user(user_uuid: str, payload: EditUserSchema,
                    current=Depends(require_super_admin)):
    user = supabase.table("user").select("*").eq("uuid", user_uuid).single().execute()
    if not user.data:
        raise HTTPException(404, "User not found")

    supabase.table("user").update({
        "name": payload.name or user.data["name"],
        "age": payload.age or user.data["age"],
        "gender": payload.gender or user.data["gender"],
        "national_id": payload.national_id or user.data["national_id"],
        "updated_at": datetime.utcnow().isoformat()
    }).eq("uuid", user_uuid).execute()

    return {"message": "User updated"}

# ============================================================
# SUPER ADMIN: DELETE USER
# ============================================================

@router.delete("/delete-user/{national_id}")
async def delete_user(national_id : str, current=Depends(require_super_admin)):
    user = supabase.table("user").select("National_ID").eq("National_ID", national_id ).execute()
    if not user.data:
        raise HTTPException(404, "User not found")

    supabase.table("user").delete().eq("National_ID", national_id ).execute()
    return {"message": "User deleted"}

# ============================================================
# SUPER ADMIN: DELETE INVALID TEST
# ============================================================

@router.delete("/delete-test/{test_type}/{test_id}")
async def delete_invalid_test(test_type: str, test_id: int,
                              current=Depends(require_super_admin)):
    table_map = {
        "depression": ("depression_screening", "Dep_test_id"),
        "dementia": ("dementia_screening", "dem_test_id"),
        "physical": ("physicalfrailty", "PF_test_id")
    }

    if test_type not in table_map:
        raise HTTPException(400, "Invalid test type")

    table, key = table_map[test_type]
    supabase.table(table).delete().eq(key, test_id).execute()
    return {"message": "Test deleted"}

# ============================================================
# SUPER ADMIN: DELETE REPORT
# ============================================================

@router.delete("/delete-report/{report_id}")
async def delete_report(report_id: int, current=Depends(require_super_admin)):
    report = supabase.table("report").select("*").eq("Report_test_id", report_id).execute()
    if not report.data:
        raise HTTPException(404, "Report not found")

    supabase.table("report").delete().eq("Report_test_id", report_id).execute()
    return {"message": "Report deleted"}

# ============================================================
# TRACK REPORT GENERATOR  or Doctor
# ============================================================

@router.get("/report-generator/{report_id}")
async def report_generator(report_id: int, current=Depends(require_super_admin)):
    report = supabase.table("report") \
        .select("Report_test_id, generator:admin(name,email)") \
        .eq("Report_test_id", report_id) \
        .single() \
        .execute()

    if not report.data:
        raise HTTPException(404, "Report not found")

    gen = report.data.get("generator")
    return {
        "report_id": report.data["Report_test_id"],
        "doctor_name": gen["name"] if gen else None,
        "doctor_email": gen["email"] if gen else None
    }

# ============================================================
# DOCTOR / ADMIN: VIEW REPORT BY REPORT ID
# ============================================================

@router.get("/reportid/{report_test_id}")
async def get_report_by_test_id(
        report_test_id: int,
        current=Depends(doctor_or_admin)
):
    report = supabase.table("report").select("*") \
        .eq("Report_test_id", report_test_id).single().execute()
    if not report.data:
        raise HTTPException(404, "Report not found")

    user = supabase.table("user").select("*") \
        .eq("uuid", report.data["user_uuid"]).single().execute()

    tests = await get_latest_tests(user.data["uuid"])

    return {
        "user": {
            "N_ID": user.data["N_ID"],
            "name": user.data["Name"],
            "age": user.data["Age"],
            "gender": user.data["Gender"],
            "national_id": user.data["National_ID"],
        },
        "report": {
            "Report_test_id": report.data["Report_test_id"],
            "created_at": report.data["created_at"],
            "remarks": report.data["remarks"]
        },
        **tests
    }

# ============================================================
# DOCTOR / ADMIN: VIEW REPORTS BY user SERIAL (N_ID)
# ============================================================

@router.get("/serial/{n_id}")
async def get_reports_by_nid(n_id: int,
                             current=Depends(doctor_or_admin)):
    user = supabase.table("user").select("*").eq("N_ID", n_id).single().execute()
    if not user.data:
        raise HTTPException(404, "User not found")

    reports = supabase.table("report") \
        .select("*") \
        .eq("user_uuid", user.data["uuid"]) \
        .order("created_at", desc=True) \
        .execute().data

    if not reports:
        raise HTTPException(404, "No reports found")

    output = []
    for r in reports:
        dep = supabase.table("Depression_Screening").select("*") \
            .eq("Dep_test_id", r["Dep_test_id"]).single().execute() if r["Dep_test_id"] else None
        dem = supabase.table("Dementia_Screening").select("*") \
            .eq("Dem_test_id", r["Dem_test_id"]).single().execute() if r["Dem_test_id"] else None
        pf = supabase.table("physical_frailty").select("*") \
            .eq("PF_test_id", r["PF_test_id"]).single().execute() if r["PF_test_id"] else None

        # --- identical data construction as original ---
        depression_data = None
        if dep and dep.data:
            depression_data = {
                "final_score": dep.data["Final_scores"],
                "final_result": dep.data["Final_result"],
                "questions": [
                    {
                        "question": f"Q{i}",
                        "answer": dep.data[f"Q{i}_ans"],
                        "score": dep.data[f"Q{i}_ans_score"]
                    } for i in range(1, 16)
                ]
            }

        dementia_data = None
        if dem and dem.data:
            dementia_data = {
                "total_earned_points": dem.data["Total_earned_point"],
                "final_result": dem.data["Final_result"],
                "questions": [
                    {
                        "question": f"Q{i}",
                        "answer": dem.data[f"Q{i}_ans"],
                        "possible_points": dem.data[f"Q{i}_P_point"],
                        "earned_points": dem.data[f"Q{i}_E_point"]
                    } for i in range(1, 13)
                ]
            }

        physical_data = pf.data if pf and pf.data else None

        output.append({
            "report": {
                "Report_test_id": r["Report_test_id"],
                "created_at": r["created_at"],
                "remarks": r["remarks"]
            },
            "depression": depression_data,
            "dementia": dementia_data,
            "physical_frailty": physical_data
        })

    return {
        "user": {
            "N_ID": user.data["N_ID"],
            "name": user.data["Name"],
            "age": user.data["Age"],
            "gender": user.data["Gender"],
            "national_id": user.data["National_ID"],
        },
        "reports": output
    }

# ============================================================
# DOCTOR / ADMIN: VIEW REPORTS BY NATIONAL ID
# ============================================================

@router.get("/national/{national_id}")
async def get_reports_by_national_id(national_id: str,
                                     current=Depends(doctor_or_admin)):
    clean_id = national_id.replace("-", "").replace(" ", "")
    user = supabase.table("user").select("*") \
        .eq("National_ID", clean_id).single().execute()
    if not user.data:
        raise HTTPException(404, "User not found")
    user = user.data
    reports = (
        supabase
            .table("report")
            .select("*")
            .eq("user_uuid", user["uuid"])
            .order("created_at", desc=True)
            .execute()
            .data
    )

    output = []

    for r in reports:

        dep = None
        dem = None
        pf = None

        if r["Dep_test_id"]:
            dep = supabase.table("Depression_Screening") \
                .select("*") \
                .eq("Dep_test_id", r["Dep_test_id"]) \
                .single() \
                .execute().data

        if r["Dem_test_id"]:
            dem = supabase.table("Dementia_Screening") \
                .select("*") \
                .eq("Dem_test_id", r["Dem_test_id"]) \
                .single() \
                .execute().data

        if r["PF_test_id"]:
            pf = supabase.table("physical_frailty") \
                .select("*") \
                .eq("PF_test_id", r["PF_test_id"]) \
                .single() \
                .execute().data

        output.append({
            "report": {
                "Report_test_id": r["Report_test_id"],
                "created_at": r["created_at"],
                "remarks": r["remarks"]
            },
            "depression": dep,
            "dementia": dem,
            "physical_frailty": pf
        })

    return {
        "user": {
            "N_ID": user["N_ID"],
            "name": user["Name"],
            "age": user["Age"],
            "gender": user["Gender"],
            "national_id": user["National_ID"],
        },
        "reports": output
    }
    # identical logic reuse
    return await get_reports_by_nid(user.data["N_ID"], current)

# ============================================================
# DOCTOR / ADMIN: VIEW ALL REPORTS
# ============================================================

@router.get("/reports")
async def get_all_reports(current=Depends(doctor_or_admin)):
    return supabase.table("report").select("*").execute().data

# ============================================================
# DOCTOR / ADMIN: TESTS BY NATIONAL ID
# ============================================================

@router.get("/tests/by-national/{national_id}")
async def get_user_tests(national_id: str,
                         current=Depends(doctor_or_admin)):
    normalized_id = national_id.replace("-", "").replace(" ", "")
    user = supabase.table("user").select("*") \
        .eq("National_ID", normalized_id).single().execute()
    if not user.data:
        errors.not_found(f"404: User with National_ID {national_id} not found")

    return {
        "N_ID": user.data["N_ID"],
        "name": user.data["Name"],
        "depression_tests": supabase.table("Depression_Screening").select("*")
            .eq("User_uuid", user.data["uuid"]).execute().data,
        "dementia_tests": supabase.table("Dementia_Screening").select("*")
            .eq("User_uuid", user.data["uuid"]).execute().data,
        "physical_frailty": supabase.table("physical_frailty").select("*")
            .eq("User_uuid", user.data["uuid"]).execute().data
    }

# ============================================================
# DOCTOR / ADMIN: VIEW ALL USERS
# ============================================================

@router.get("/users")
async def view_all_users(current=Depends(doctor_or_admin)):
    return supabase.table("user").select("*").eq("is_deleted", False).execute().data

# ============================================================
# DOCTOR / ADMIN: VIEW ALL TESTS
# ============================================================

@router.get("/tests")
async def view_all_tests(current=Depends(doctor_or_admin)):
    return {
        "depression": supabase.table("Depression_Screening").select("*").execute().data,
        "dementia": supabase.table("Dementia_Screening").select("*").execute().data,
        "physical_frailty": supabase.table("physical_frailty").select("*").execute().data
    }