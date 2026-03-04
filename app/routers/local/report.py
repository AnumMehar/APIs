from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
from app.db.prisma import prisma
from app.schemas.report import ReportResponse, UpdateReportPayload
from app.services.depression_service import depression_result
from app.services.dementia_service import dementia_result
from app.dependencies.auth import doctor_or_admin

router = APIRouter()


# Helper function
async def get_latest_tests(user_uuid: str) -> Dict:
    dep = await prisma.depression_screening.find_first(
        where={"user_uuid": user_uuid},
        order={"created_at": "desc"}
    )

    dem = await prisma.dementia_screening.find_first(
        where={"user_uuid": user_uuid},
        order={"created_at": "desc"}
    )

    pf = await prisma.physicalfrailty.find_first(
        where={"User_uuid": user_uuid},
        order={"created_at": "desc"}
    )

    result = {}

    if dep:
        result["depression"] = {
            "Dep_test_id": dep.Dep_test_id,
            "final_score": dep.final_scores,
            "final_result": dep.final_result,
            "questions": [
                {
                    "question": f"Q{i}",
                    "answer": getattr(dep, f"Q{i}_ans"),
                    "score": getattr(dep, f"Q{i}_ans_score")
                }
                for i in range(1, 16)
            ]
        }

    if dem:
        result["dementia"] = {
            "Dem_test_id": dem.dem_test_id,
            "total_earned_points": dem.total_earned_point,
            "final_result": dem.final_result,
            "questions": [
                {
                    "question": f"Q{i}",
                    "answer": getattr(dem, f"Q{i}_ans"),
                    "possible_points": getattr(dem, f"Q{i}_P_point"),
                    "earned_points": getattr(dem, f"Q{i}_E_point")
                }
                for i in range(1, 13)
            ]
        }

    if pf:
        result["physical_frailty"] = {
            "PF_test_id": pf.PF_test_id,
            "created_at": pf.created_at,
            "session_status": pf.session_status,
            "session_date": pf.session_date,
            "session_submitted_at": pf.session_submitted_at,
            "Walking_speed": pf.Walking_speed,
            "walking_speed_created_at": pf.walking_speed_created_at,
            # "walking_speed_is_done": frailty.walking_speed_is_done,
            "Functional_reach": pf.Functional_reach,
            "functional_reach_created_at": pf.functional_reach_created_at,
            "Standing_on_one_leg": pf.Standing_on_one_leg,
            "standing_on_one_leg_created_at": pf.standing_on_one_leg_created_at,
            "Time_up_and_go": pf.Time_up_and_go,
            "time_up_and_go_created_at": pf.time_up_and_go_created_at,
            "seated_forward_bend": pf.seated_forward_bend,
            "seated_forward_bend_created_at": pf.seated_forward_bend_created_at,
            "grip_strength": pf.grip_strength,
            "grip_strength_created_at": pf.grip_strength_created_at,
        }

    return result if result else None

@router.post("/generate/{user_uuid}")
async def generate_report(
    user_uuid: str,
    payload: ReportResponse = None,
    current=Depends(doctor_or_admin)
):
    # 1️⃣ Check user exists
    user = await prisma.user.find_unique(where={"uuid": user_uuid})
    print("USER UUID RECEIVED:", user_uuid)
    print("USER RESULT:", user)
    if not user:
        raise HTTPException(404, "User not found")

    # 2️⃣ Get latest tests
    depression = await prisma.depression_screening.find_first(
        where={"user_uuid": user_uuid},
        order={"created_at": "desc"}
    )

    dementia = await prisma.dementia_screening.find_first(
        where={"user_uuid": user_uuid},
        order={"created_at": "desc"}
    )

    frailty = await prisma.physicalfrailty.find_first(
        where={"User_uuid": user_uuid},
        order={"created_at": "desc"}
    )

    # 3️⃣ Create report row
    report = await prisma.report.create(
        data={
            "user_uuid": user_uuid,
            # "generated_by": current["uuid"],
            "Dep_test_id": depression.Dep_test_id if depression else None,
            "Dem_test_id": dementia.dem_test_id if dementia else None,
            "PF_test_id": frailty.PF_test_id if frailty else None,
            "remarks": payload.remarks if payload else None
        }
    )

    # 4️⃣ RETURN COMPLETE REPORT DATA
    return {
        "Report_test_id": report.Report_test_id,
        # "generated_by": current["name"],
        # "generated_role": current["role"],
        "created_at": report.created_at,
        "user": {
            "name": user.name,
            "age": user.age,
            "gender": user.gender,
            "national_id": user.national_id
        },

        "depression": {
            "Dep_test_id": depression.Dep_test_id,
            "created_at": depression.created_at,
            "answers": {
                f"Q{i}": getattr(depression, f"Q{i}_ans") for i in range(1, 16)
            },
            "scores": {
                f"Q{i}": getattr(depression, f"Q{i}_ans_score") for i in range(1, 16)
            },
            "final_scores": depression.final_scores,
            "final_result": depression.final_result
        } if depression else None,

        "dementia": {
            "dem_test_id": dementia.dem_test_id,
            "created_at": dementia.created_at,
            "answers": {
                f"Q{i}": getattr(dementia, f"Q{i}_ans") for i in range(1, 13)
            },
            "points": {
                f"Q{i}": {
                    "possible": getattr(dementia, f"Q{i}_P_point"),
                    "earned": getattr(dementia, f"Q{i}_E_point"),
                }
                for i in range(1, 13)
            },
            "total_earned_point": dementia.total_earned_point,
            "final_result": dementia.final_result
        } if dementia else None,

        "physical_frailty": {
            "PF_test_id": frailty.PF_test_id,
            "created_at": frailty.created_at,
            # Walking Speed R1
            "Walking_speed_r1": frailty.Walking_speed_r1,
            "walking_speed_r1_created_at": frailty.walking_speed_r1_created_at,

            # Functional Reach R1
            "Functional_reach_r1": frailty.Functional_reach_r1,
            "functional_reach_r1_created_at": frailty.functional_reach_r1_created_at,

            # Standing on one leg R1
            "Standing_on_one_leg_r1": frailty.Standing_on_one_leg_r1,
            "standing_on_one_leg_r1_created_at": frailty.standing_on_one_leg_r1_created_at,

            # Time up and go R1
            "Time_up_and_go_r1": frailty.Time_up_and_go_r1,
            "time_up_and_go_r1_created_at": frailty.time_up_and_go_r1_created_at,

            # Seated forward bend R1
            "seated_forward_bend_r1": frailty.seated_forward_bend_r1,
            "seated_forward_bend_r1_created_at": frailty.seated_forward_bend_r1_created_at,

            # Walking Speed R2
            "Walking_speed_r2": frailty.Walking_speed_r2,
            "walking_speed_r2_created_at": frailty.walking_speed_r2_created_at,

            # Functional Reach R2
            "Functional_reach_r2": frailty.Functional_reach_r2,
            "functional_reach_r2_created_at": frailty.functional_reach_r2_created_at,

            # Standing on one leg R2
            "Standing_on_one_leg_r2": frailty.Standing_on_one_leg_r2,
            "standing_on_one_leg_r2_created_at": frailty.standing_on_one_leg_r2_created_at,

            # Time up and go R2
            "Time_up_and_go_r2": frailty.Time_up_and_go_r2,
            "time_up_and_go_r2_created_at": frailty.time_up_and_go_r2_created_at,

            # Seated forward bend R2
            "seated_forward_bend_r2": frailty.seated_forward_bend_r2,
            "seated_forward_bend_r2_created_at": frailty.seated_forward_bend_r2_created_at,

        } if frailty else None
    }


@router.post("/update/{report_id}")
async def update_report(report_id: int, payload: UpdateReportPayload):
    # 1️⃣ Fetch the report
    report = await prisma.report.find_unique(
        where={"Report_test_id": report_id}
    )
    if not report:
        raise HTTPException(404, "Report not found")

    # 2️⃣ Update depression test if provided
    if payload.depression_answers and report.Dep_test_id:
        final_score = sum(ans.score for ans in payload.depression_answers)
        final_result = depression_result(final_score)

        # Prepare dynamic question fields
        update_data = {
            "final_scores": final_score,
            "final_result": final_result
        }
        for ans in payload.depression_answers:
            update_data[f"Q{ans.question_no}_ans"] = ans.answer
            update_data[f"Q{ans.question_no}_ans_score"] = ans.score

        await prisma.depression_screening.update(
            where={"Dep_test_id": report.Dep_test_id},
            data=update_data
        )

    # 3️⃣ Update dementia test if provided
    if payload.dementia_answers and report.Dem_test_id:
        total_earned = sum(q.earned for q in payload.dementia_answers)
        final_result = dementia_result(total_earned)

        update_data = {
            "total_earned_point": total_earned,
            "final_result": final_result
        }
        for q in payload.dementia_answers:
            update_data[f"Q{q.no}_ans"] = q.answer
            update_data[f"Q{q.no}_P_point"] = q.possible
            update_data[f"Q{q.no}_E_point"] = q.earned

        await prisma.dementia_screening.update(
            where={"dem_test_id": report.Dem_test_id},
            data=update_data
        )
    # 4️⃣ Update remarks if provided
    if payload.remarks is not None:
        await prisma.report.update(
            where={"Report_test_id": report.Report_test_id},
            data={"remarks": payload.remarks}
        )

    # Fetch updated report data
    updated_report = await get_report_by_test_id(report.Report_test_id)
    return updated_report


# GET report by report_test_id
@router.get("/reportid/{report_test_id}")
async def get_report_by_test_id(report_test_id: int):
    report = await prisma.report.find_unique(where={"Report_test_id": report_test_id})
    if not report:
        raise HTTPException(404, "Report not found")

    user = await prisma.user.find_unique(where={"uuid": report.user_uuid})
    tests = await get_latest_tests(user.uuid)

    return {
        "user": {
            "N_ID": user.n_id,
            "name": user.name,
            "age": user.age,
            "gender": user.gender,
            "national_id": user.national_id,
        },
        "report": {
            "Report_test_id": report.Report_test_id,
            "created_at": report.created_at,
            "remarks": report.remarks
        },
        **tests  # includes depression, dementia, physical_frailty
    }
