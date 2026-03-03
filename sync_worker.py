# # import asyncio
# # import datetime
# # import httpx
# # from prisma import Prisma
# # import os
# # from dotenv import load_dotenv
# #
# # load_dotenv()
# # # Initialize Prisma client
# # prisma = Prisma()
# #
# # # Supabase configuration
# #
# # SUPABASE_URL = os.getenv("SUPABASE_URL").rstrip("/") + "/rest/v1/"
# # SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# # print("SUPABASE_URL =", SUPABASE_URL)
# # print("SUPABASE_KEY =", SUPABASE_KEY[:4] + "..." if SUPABASE_KEY else "None")
# # HEADERS = {
# #     "apikey": SUPABASE_KEY,
# #     "Authorization": f"Bearer {SUPABASE_KEY}",
# #     "Content-Type": "application/json"
# # }
# #
# # # Tables and relation fields
# # TABLES = ["user", "Depression_Screening", "Dementia_Screening", "physical_frailty", "report"]
# #
# # # Keys are local Prisma model names, Values are remote Supabase table names
# # RELATION_FIELDS = {
# #     "user": "user",
# #     "depression_screening": "Depression_Screening",
# #     "dementia_screening": "Dementia_Screening",
# #     "physicalfrailty": "physical_frailty",
# #     "report": "report"
# # }
# #
# # # Field mapping: Prisma field -> Supabase column
# # COLUMN_MAPPING = {
# #     "user": {
# #         "uuid": "uuid",
# #         "n_id": "N_ID",
# #         "name": "Name",
# #         "age": "Age",
# #         "gender": "Gender",
# #         "national_id": "National_ID",
# #         "is_deleted": "is_deleted",
# #         "assigned_doctor_uuid": "assigned_doctor_uuid",
# #         "created_at": "created_at",
# #         "updated_at": "updated_at",
# #         "sync_status": "sync_status"
# #     },
# #     "depression_screening": {
# #         "uuid": "uuid",
# #         "user_uuid": "User_uuid",
# #         "Dep_test_id": "Dep_test_id",
# #         "created_at": "created_at",
# #         "sync_status": "sync_status",
# #         "Q1_ans": "Q1_ans",
# #         "Q1_ans_score": "Q1_ans_score",
# #         "Q2_ans": "Q2_ans",
# #         "Q2_ans_score": "Q2_ans_score",
# #         "Q3_ans": "Q3_ans",
# #         "Q3_ans_score": "Q3_ans_score",
# #         "Q4_ans": "Q4_ans",
# #         "Q4_ans_score": "Q4_ans_score",
# #         "Q5_ans": "Q5_ans",
# #         "Q5_ans_score": "Q5_ans_score",
# #         "Q6_ans": "Q6_ans",
# #         "Q6_ans_score": "Q6_ans_score",
# #         "Q7_ans": "Q7_ans",
# #         "Q7_ans_score": "Q7_ans_score",
# #         "Q8_ans": "Q8_ans",
# #         "Q8_ans_score": "Q8_ans_score",
# #         "Q9_ans": "Q9_ans",
# #         "Q9_ans_score": "Q9_ans_score",
# #         "Q10_ans": "Q10_ans",
# #         "Q10_ans_score": "Q10_ans_score",
# #         "Q11_ans": "Q11_ans",
# #         "Q11_ans_score": "Q11_ans_score",
# #         "Q12_ans": "Q12_ans",
# #         "Q12_ans_score": "Q12_ans_score",
# #         "Q13_ans": "Q13_ans",
# #         "Q13_ans_score": "Q13_ans_score",
# #         "Q14_ans": "Q14_ans",
# #         "Q14_ans_score": "Q14_ans_score",
# #         "Q15_ans": "Q15_ans",
# #         "Q15_ans_score": "Q15_ans_score",
# #         "final_scores": "Final_scores",
# #         "final_result": "Final_result",
# #         "report": "report"
# #     },
# #     "dementia_screening": {
# #         "uuid": "uuid",
# #         "user_uuid": "User_uuid",
# #         "dem_test_id": "Dem_test_id",
# #         "created_at": "created_at",
# #         "sync_status": "sync_status",
# #         "Q1_ans": "Q1_ans",
# #         "Q1_P_point": "Q1_P_point",
# #         "Q1_E_point": "Q1_E_point",
# #         "Q2_ans": "Q2_ans",
# #         "Q2_P_point": "Q2_P_point",
# #         "Q2_E_point": "Q2_E_point",
# #         "Q3_ans": "Q3_ans",
# #         "Q3_P_point": "Q3_P_point",
# #         "Q3_E_point": "Q3_E_point",
# #         "Q4_ans": "Q4_ans",
# #         "Q4_P_point": "Q4_P_point",
# #         "Q4_E_point": "Q4_E_point",
# #         "Q5_ans": "Q5_ans",
# #         "Q5_P_point": "Q5_P_point",
# #         "Q5_E_point": "Q5_E_point",
# #         "Q6_ans": "Q6_ans",
# #         "Q6_P_point": "Q6_P_point",
# #         "Q6_E_point": "Q6_E_point",
# #         "Q7_ans": "Q7_ans",
# #         "Q7_P_point": "Q7_P_point",
# #         "Q7_E_point": "Q7_E_point",
# #         "Q8_ans": "Q8_ans",
# #         "Q8_P_point": "Q8_P_point",
# #         "Q8_E_point": "Q8_E_point",
# #         "Q9_ans": "Q9_ans",
# #         "Q9_P_point": "Q9_P_point",
# #         "Q9_E_point": "Q9_E_point",
# #         "Q10_ans": "Q10_ans",
# #         "Q10_P_point": "Q10_P_point",
# #         "Q10_E_point": "Q10_E_point",
# #         "Q11_ans": "Q11_ans",
# #         "Q11_P_point": "Q11_P_point",
# #         "Q11_E_point": "Q11_E_point",
# #         "Q12_ans": "Q12_ans",
# #         "Q12_P_point": "Q12_P_point",
# #         "Q12_E_point": "Q12_E_point",
# #         "total_earned_point": "Total_earned_point",
# #         "final_result": "Final_result",
# #         "report": "report"
# #     },
# #     "physicalfrailty": {
# #         "uuid": "uuid",
# #         "User_uuid": "User_uuid",
# #         "PF_test_id": "PF_test_id",
# #         "Walking_speed": "Walking_speed",
# #         "walking_speed_created_at": "walking_speed_created_at",
# #         "walking_speed_is_done": "walking_speed_is_done",
# #         "Functional_reach": "Functional_reach",
# #         "functional_reach_created_at": "functional_reach_created_at",
# #         "functional_reach_is_done": "functional_reach_is_done",
# #         "Standing_on_one_leg": "Standing_on_one_leg",
# #         "standing_on_one_leg_created_at": "standing_on_one_leg_created_at",
# #         "standing_on_one_leg_is_done": "standing_on_one_leg_is_done",
# #         "Time_up_and_go": "Time_up_and_go",
# #         "time_up_and_go_created_at": "time_up_and_go_created_at",
# #         "time_up_and_go_is_done": "time_up_and_go_is_done",
# #         "seated_forward_bend": "seated_forward_bend",
# #         "seated_forward_bend_created_at": "seated_forward_bend_created_at",
# #         "seated_forward_bend_is_done": "seated_forward_bend_is_done",
# #         "grip_strength": "grip_strength",
# #         "grip_strength_created_at": "grip_strength_created_at",
# #         "grip_strength_is_done": "grip_strength_is_done",
# #         "created_at": "created_at",
# #         "session_date": "session_date",
# #         "session_status": "session_status",
# #         "session_submitted_at": "session_submitted_at",
# #         "sync_status": "sync_status",
# #         "user": "user"
# #     },
# #     "report": {
# #         "uuid": "uuid",
# #         "Report_test_id": "Report_test_id",
# #         "user_uuid": "user_uuid",
# #         "Dep_test_id": "Dep_test_id",
# #         "Dem_test_id": "Dem_test_id",
# #         "PF_test_id": "PF_test_id",
# #         "created_at": "created_at",
# #         "generated_by": "generated_by",
# #         "updated_at": "updated_at",
# #         "sync_status": "sync_status",
# #         "remarks": "remarks"
# #     }
# # }
# #
# # async def sync_table(model_name, supabase_table):
# #     print(f"[{datetime.datetime.now()}] Online - Syncing {model_name} -> {supabase_table}...")
# #
# #     # Use model_name for local Prisma lookup
# #     model = getattr(prisma, model_name)
# #     unsynced_records = await model.find_many(where={"sync_status": 0})
# #
# #     if not unsynced_records:
# #         print(f"No pending records for {model_name}")
# #         return
# #
# #     async with httpx.AsyncClient() as client:
# #         for r in unsynced_records:
# #             # Use model_name to get the correct COLUMN_MAPPING
# #             payload = {
# #                 COLUMN_MAPPING[model_name].get(k, k): (v.isoformat() if isinstance(v, datetime.datetime) else v)
# #                 for k, v in r.__dict__.items()
# #                 if k not in RELATION_FIELDS and v is not None and k != "sync_status"
# #             }
# #
# #             try:
# #                 # Use supabase_table for the URL
# #                 url = f"{SUPABASE_URL}{supabase_table}"
# #                 response = await client.post(url, headers=HEADERS, json=payload)
# #
# #                 if response.status_code in (200, 201):
# #                     await model.update(where={"uuid": r.uuid}, data={"sync_status": 1})
# #                     print(f"Successfully synced {model_name} UUID: {r.uuid}")
# #                 else:
# #                     print(f"Failed {model_name}: {response.status_code} - {response.text}")
# #             except Exception as e:
# #                 print(f"Error syncing {model_name}: {e}")
# #
# # async def main():
# #     await prisma.connect()
# #     for model_name, supabase_table in RELATION_FIELDS.items():
# #         await sync_table(model_name, supabase_table)
# #     await prisma.disconnect()
# #
# # if __name__ == "__main__":
# #     asyncio.run(main())
#
# import asyncio
# import datetime
# import httpx
# import os
# from prisma import Prisma
# from dotenv import load_dotenv
#
# load_dotenv()
# prisma = Prisma()
#
# # --- CONFIGURATION ---
# SUPABASE_URL = os.getenv("SUPABASE_URL").rstrip("/") + "/rest/v1/"
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# HEADERS = {
#     "apikey": SUPABASE_KEY,
#     "Authorization": f"Bearer {SUPABASE_KEY}",
#     "Content-Type": "application/json",
#     "Prefer": "return=minimal"  # Optimization: don't ask Supabase to send data back
# }
#
# # Mapping Local Model -> Supabase Table
# TABLES_MAP = {
#     "user": "user",
#     "depression_screening": "Depression_Screening",
#     "dementia_screening": "Dementia_Screening",
#     "physicalfrailty": "physical_frailty",
#     "report": "report"
# }
#
# # Field mapping: Prisma field -> Supabase column
# COLUMN_MAPPING = {
#     "user": {
#         "uuid": "uuid",
#         "n_id": "N_ID",
#         "name": "Name",
#         "age": "Age",
#         "gender": "Gender",
#         "national_id": "National_ID",
#         "is_deleted": "is_deleted",
#         "assigned_doctor_uuid": "assigned_doctor_uuid",
#         "created_at": "created_at",
#         "updated_at": "updated_at",
#         "sync_status": "sync_status"
#     },
#     "depression_screening": {
#         "uuid": "uuid",
#         "user_uuid": "User_uuid",
#         "Dep_test_id": "Dep_test_id",
#         "created_at": "created_at",
#         "sync_status": "sync_status",
#         "session_status": "session_status",
#         "Q1_ans": "Q1_ans",
#         "Q1_ans_score": "Q1_ans_score",
#         "Q2_ans": "Q2_ans",
#         "Q2_ans_score": "Q2_ans_score",
#         "Q3_ans": "Q3_ans",
#         "Q3_ans_score": "Q3_ans_score",
#         "Q4_ans": "Q4_ans",
#         "Q4_ans_score": "Q4_ans_score",
#         "Q5_ans": "Q5_ans",
#         "Q5_ans_score": "Q5_ans_score",
#         "Q6_ans": "Q6_ans",
#         "Q6_ans_score": "Q6_ans_score",
#         "Q7_ans": "Q7_ans",
#         "Q7_ans_score": "Q7_ans_score",
#         "Q8_ans": "Q8_ans",
#         "Q8_ans_score": "Q8_ans_score",
#         "Q9_ans": "Q9_ans",
#         "Q9_ans_score": "Q9_ans_score",
#         "Q10_ans": "Q10_ans",
#         "Q10_ans_score": "Q10_ans_score",
#         "Q11_ans": "Q11_ans",
#         "Q11_ans_score": "Q11_ans_score",
#         "Q12_ans": "Q12_ans",
#         "Q12_ans_score": "Q12_ans_score",
#         "Q13_ans": "Q13_ans",
#         "Q13_ans_score": "Q13_ans_score",
#         "Q14_ans": "Q14_ans",
#         "Q14_ans_score": "Q14_ans_score",
#         "Q15_ans": "Q15_ans",
#         "Q15_ans_score": "Q15_ans_score",
#         "final_scores": "Final_scores",
#         "final_result": "Final_result",
#         "report": "report"
#     },
#     "dementia_screening": {
#         "uuid": "uuid",
#         "user_uuid": "User_uuid",
#         "dem_test_id": "Dem_test_id",
#         "created_at": "created_at",
#         "sync_status": "sync_status",
#         "Q1_ans": "Q1_ans",
#         "Q1_P_point": "Q1_P_point",
#         "Q1_E_point": "Q1_E_point",
#         "Q2_ans": "Q2_ans",
#         "Q2_P_point": "Q2_P_point",
#         "Q2_E_point": "Q2_E_point",
#         "Q3_ans": "Q3_ans",
#         "Q3_P_point": "Q3_P_point",
#         "Q3_E_point": "Q3_E_point",
#         "Q4_ans": "Q4_ans",
#         "Q4_P_point": "Q4_P_point",
#         "Q4_E_point": "Q4_E_point",
#         "Q5_ans": "Q5_ans",
#         "Q5_P_point": "Q5_P_point",
#         "Q5_E_point": "Q5_E_point",
#         "Q6_ans": "Q6_ans",
#         "Q6_P_point": "Q6_P_point",
#         "Q6_E_point": "Q6_E_point",
#         "Q7_ans": "Q7_ans",
#         "Q7_P_point": "Q7_P_point",
#         "Q7_E_point": "Q7_E_point",
#         "Q8_ans": "Q8_ans",
#         "Q8_P_point": "Q8_P_point",
#         "Q8_E_point": "Q8_E_point",
#         "Q9_ans": "Q9_ans",
#         "Q9_P_point": "Q9_P_point",
#         "Q9_E_point": "Q9_E_point",
#         "Q10_ans": "Q10_ans",
#         "Q10_P_point": "Q10_P_point",
#         "Q10_E_point": "Q10_E_point",
#         "Q11_ans": "Q11_ans",
#         "Q11_P_point": "Q11_P_point",
#         "Q11_E_point": "Q11_E_point",
#         "Q12_ans": "Q12_ans",
#         "Q12_P_point": "Q12_P_point",
#         "Q12_E_point": "Q12_E_point",
#         "total_earned_point": "Total_earned_point",
#         "final_result": "Final_result",
#         "session_status": "session_status",
#         "report": "report"
#     },
#     # "physicalfrailty": {
#     #     "uuid": "uuid",
#     #     "User_uuid": "User_uuid",
#     #     "PF_test_id": "PF_test_id",
#     #     "Walking_speed": "Walking_speed",
#     #     "walking_speed_created_at": "walking_speed_created_at",
#     #     "walking_speed_is_done": "walking_speed_is_done",
#     #     "Functional_reach": "Functional_reach",
#     #     "functional_reach_created_at": "functional_reach_created_at",
#     #     "functional_reach_is_done": "functional_reach_is_done",
#     #     "Standing_on_one_leg": "Standing_on_one_leg",
#     #     "standing_on_one_leg_created_at": "standing_on_one_leg_created_at",
#     #     "standing_on_one_leg_is_done": "standing_on_one_leg_is_done",
#     #     "Time_up_and_go": "Time_up_and_go",
#     #     "time_up_and_go_created_at": "time_up_and_go_created_at",
#     #     "time_up_and_go_is_done": "time_up_and_go_is_done",
#     #     "seated_forward_bend": "seated_forward_bend",
#     #     "seated_forward_bend_created_at": "seated_forward_bend_created_at",
#     #     "seated_forward_bend_is_done": "seated_forward_bend_is_done",
#     #     "grip_strength": "grip_strength",
#     #     "grip_strength_created_at": "grip_strength_created_at",
#     #     "grip_strength_is_done": "grip_strength_is_done",
#     #     "created_at": "created_at",
#     #     "session_date": "session_date",
#     #     "session_status": "session_status",
#     #     "session_submitted_at": "session_submitted_at",
#     #     "sync_status": "sync_status",
#     #     "user": "user"
#     # },
#     "physicalfrailty": {
#         "uuid": "uuid",
#         "User_uuid": "User_uuid",
#         "PF_test_id": "PF_test_id",
#         "Walking_speed_r1": "Walking_speed_r1",
#         "walking_speed_r1_created_at": "walking_speed_r1_created_at",
#         "walking_speed_r1_is_done": "walking_speed_r1_is_done",
#         "Walking_speed_r2": "Walking_speed_r2",
#         "walking_speed_r2_created_at": "walking_speed_r2_created_at",
#         "walking_speed_r2_is_done": "walking_speed_r2_is_done",
#         "Functional_reach_r1": "Functional_reach_r1",
#         "functional_reach_r1_created_at": "functional_reach_r1_created_at",
#         "functional_reach_r1_is_done": "functional_reach_r1_is_done",
#         "Functional_reach_r2": "Functional_reach_r2",
#         "functional_reach_r2_created_at": "functional_reach_r2_created_at",
#         "functional_reach_r2_is_done": "functional_reach_r2_is_done",
#         "Standing_on_one_leg_r1": "Standing_on_one_leg_r1",
#         "standing_on_one_leg_r1_created_at": "standing_on_one_leg_r1_created_at",
#         "standing_on_one_leg_r1_is_done": "standing_on_one_leg_r1_is_done",
#         "Standing_on_one_leg_r2": "Standing_on_one_leg_r2",
#         "standing_on_one_leg_r2_created_at": "standing_on_one_leg_r2_created_at",
#         "standing_on_one_leg_r2_is_done": "standing_on_one_leg_r2_is_done",
#         "Time_up_and_go_r1": "Time_up_and_go_r1",
#         "time_up_and_go_r1_created_at": "time_up_and_go_r1_created_at",
#         "time_up_and_go_r1_is_done": "time_up_and_go_r1_is_done",
#         "Time_up_and_go_r2": "Time_up_and_go_r2",
#         "time_up_and_go_r2_created_at": "time_up_and_go_r2_created_at",
#         "time_up_and_go_r2_is_done": "time_up_and_go_r2_is_done",
#         "seated_forward_bend_r1": "seated_forward_bend_r1",
#         "seated_forward_bend_r1_created_at": "seated_forward_bend_r1_created_at",
#         "seated_forward_bend_r1_is_done": "seated_forward_bend_r1_is_done",
#         "seated_forward_bend_r2": "seated_forward_bend_r2",
#         "seated_forward_bend_r2_created_at": "seated_forward_bend_r2_created_at",
#         "seated_forward_bend_r2_is_done": "seated_forward_bend_r2_is_done",
#         "created_at": "created_at",
#         "sync_status": "sync_status",
#         "user": "user"
#     },
#     "report": {
#         "uuid": "uuid",
#         "Report_test_id": "Report_test_id",
#         "user_uuid": "user_uuid",
#         "Dep_test_id": "Dep_test_id",
#         "Dem_test_id": "Dem_test_id",
#         "PF_test_id": "PF_test_id",
#         "created_at": "created_at",
#         "generated_by": "generated_by",
#         "updated_at": "updated_at",
#         "sync_status": "sync_status",
#         "remarks": "remarks"
#     }
# }
#
# # Fields to ignore (Prisma relations)
# IGNORE_FIELDS = ["DementiaScreenings", "DepressionScreenings", "physicalFrailty", "Reports", "user",
#                  "Dementia_Screening", "Depression_Screening", "assignedDoctor", "generator"]
#
#
# # --- HELPER: CHECK INTERNET ---
# async def is_internet_available():
#     try:
#         async with httpx.AsyncClient(timeout=3.0) as client:
#             # Try to hit Supabase's health/rest endpoint
#             response = await client.get(SUPABASE_URL, headers={"apikey": SUPABASE_KEY})
#             return response.status_code == 200
#     except Exception:
#         return False
#
#
# # --- SYNC LOGIC ---
# async def sync_table(model_name, supabase_table):
#     try:
#         model = getattr(prisma, model_name)
#         unsynced_records = await model.find_many(where={"sync_status": 0})
#
#         if not unsynced_records:
#             return 0
#
#         success_count = 0
#         async with httpx.AsyncClient() as client:
#             for r in unsynced_records:
#                 # Build payload
#                 payload = {}
#                 for k, v in r.__dict__.items():
#                     # Map the column name if exists, otherwise use k
#                     clean_key = COLUMN_MAPPING.get(model_name, {}).get(k, k)
#
#                     if k not in IGNORE_FIELDS and k != "sync_status" and v is not None:
#                         payload[clean_key] = v.isoformat() if isinstance(v, datetime.datetime) else v
#
#                 url = f"{SUPABASE_URL}{supabase_table}"
#                 response = await client.post(url, headers=HEADERS, json=payload)
#
#                 if response.status_code in (200, 201, 204):
#                     await model.update(where={"uuid": r.uuid}, data={"sync_status": 1})
#                     success_count += 1
#                 else:
#                     print(f"  [!] Failed {model_name} ({r.uuid}): {response.status_code}")
#
#         return success_count
#     except Exception as e:
#         print(f"  [!] Critical error in {model_name}: {e}")
#         return 0
#
#
# # --- MAIN LOOP ---
# async def main():
#     print("🚀 Sync Worker Started. Press Ctrl+C to stop.")
#     await prisma.connect()
#
#     try:
#         while True:
#             if await is_internet_available():
#                 total_synced = 0
#                 for model, table in TABLES_MAP.items():
#                     synced = await sync_table(model, table)
#                     total_synced += synced
#
#                 if total_synced > 0:
#                     print(f"✅ [{datetime.datetime.now().strftime('%H:%M:%S')}] Synced {total_synced} records.")
#             else:
#                 print(f"☁️ [{datetime.datetime.now().strftime('%H:%M:%S')}] Offline - Waiting for internet...")
#
#             # Wait for 30 seconds before checking again
#             await asyncio.sleep(30)
#
#     except asyncio.CancelledError:
#         print("Worker stopping...")
#     finally:
#         await prisma.disconnect()
#
#
# if __name__ == "__main__":
#     # Ensure your COLUMN_MAPPING from your previous snippet is included here!
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         pass

# import asyncio
# import datetime
# import httpx
# from prisma import Prisma
# import os
# from dotenv import load_dotenv
#
# load_dotenv()
# # Initialize Prisma client
# prisma = Prisma()
#
# # Supabase configuration
#
# SUPABASE_URL = os.getenv("SUPABASE_URL").rstrip("/") + "/rest/v1/"
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# print("SUPABASE_URL =", SUPABASE_URL)
# print("SUPABASE_KEY =", SUPABASE_KEY[:4] + "..." if SUPABASE_KEY else "None")
# HEADERS = {
#     "apikey": SUPABASE_KEY,
#     "Authorization": f"Bearer {SUPABASE_KEY}",
#     "Content-Type": "application/json"
# }
#
# # Tables and relation fields
# TABLES = ["user", "Depression_Screening", "Dementia_Screening", "physical_frailty", "report"]
#
# # Keys are local Prisma model names, Values are remote Supabase table names
# RELATION_FIELDS = {
#     "user": "user",
#     "depression_screening": "Depression_Screening",
#     "dementia_screening": "Dementia_Screening",
#     "physicalfrailty": "physical_frailty",
#     "report": "report"
# }
#
# # Field mapping: Prisma field -> Supabase column
# COLUMN_MAPPING = {
#     "user": {
#         "uuid": "uuid",
#         "n_id": "N_ID",
#         "name": "Name",
#         "age": "Age",
#         "gender": "Gender",
#         "national_id": "National_ID",
#         "is_deleted": "is_deleted",
#         "assigned_doctor_uuid": "assigned_doctor_uuid",
#         "created_at": "created_at",
#         "updated_at": "updated_at",
#         "sync_status": "sync_status"
#     },
#     "depression_screening": {
#         "uuid": "uuid",
#         "user_uuid": "User_uuid",
#         "Dep_test_id": "Dep_test_id",
#         "created_at": "created_at",
#         "sync_status": "sync_status",
#         "Q1_ans": "Q1_ans",
#         "Q1_ans_score": "Q1_ans_score",
#         "Q2_ans": "Q2_ans",
#         "Q2_ans_score": "Q2_ans_score",
#         "Q3_ans": "Q3_ans",
#         "Q3_ans_score": "Q3_ans_score",
#         "Q4_ans": "Q4_ans",
#         "Q4_ans_score": "Q4_ans_score",
#         "Q5_ans": "Q5_ans",
#         "Q5_ans_score": "Q5_ans_score",
#         "Q6_ans": "Q6_ans",
#         "Q6_ans_score": "Q6_ans_score",
#         "Q7_ans": "Q7_ans",
#         "Q7_ans_score": "Q7_ans_score",
#         "Q8_ans": "Q8_ans",
#         "Q8_ans_score": "Q8_ans_score",
#         "Q9_ans": "Q9_ans",
#         "Q9_ans_score": "Q9_ans_score",
#         "Q10_ans": "Q10_ans",
#         "Q10_ans_score": "Q10_ans_score",
#         "Q11_ans": "Q11_ans",
#         "Q11_ans_score": "Q11_ans_score",
#         "Q12_ans": "Q12_ans",
#         "Q12_ans_score": "Q12_ans_score",
#         "Q13_ans": "Q13_ans",
#         "Q13_ans_score": "Q13_ans_score",
#         "Q14_ans": "Q14_ans",
#         "Q14_ans_score": "Q14_ans_score",
#         "Q15_ans": "Q15_ans",
#         "Q15_ans_score": "Q15_ans_score",
#         "final_scores": "Final_scores",
#         "final_result": "Final_result",
#         "report": "report"
#     },
#     "dementia_screening": {
#         "uuid": "uuid",
#         "user_uuid": "User_uuid",
#         "dem_test_id": "Dem_test_id",
#         "created_at": "created_at",
#         "sync_status": "sync_status",
#         "Q1_ans": "Q1_ans",
#         "Q1_P_point": "Q1_P_point",
#         "Q1_E_point": "Q1_E_point",
#         "Q2_ans": "Q2_ans",
#         "Q2_P_point": "Q2_P_point",
#         "Q2_E_point": "Q2_E_point",
#         "Q3_ans": "Q3_ans",
#         "Q3_P_point": "Q3_P_point",
#         "Q3_E_point": "Q3_E_point",
#         "Q4_ans": "Q4_ans",
#         "Q4_P_point": "Q4_P_point",
#         "Q4_E_point": "Q4_E_point",
#         "Q5_ans": "Q5_ans",
#         "Q5_P_point": "Q5_P_point",
#         "Q5_E_point": "Q5_E_point",
#         "Q6_ans": "Q6_ans",
#         "Q6_P_point": "Q6_P_point",
#         "Q6_E_point": "Q6_E_point",
#         "Q7_ans": "Q7_ans",
#         "Q7_P_point": "Q7_P_point",
#         "Q7_E_point": "Q7_E_point",
#         "Q8_ans": "Q8_ans",
#         "Q8_P_point": "Q8_P_point",
#         "Q8_E_point": "Q8_E_point",
#         "Q9_ans": "Q9_ans",
#         "Q9_P_point": "Q9_P_point",
#         "Q9_E_point": "Q9_E_point",
#         "Q10_ans": "Q10_ans",
#         "Q10_P_point": "Q10_P_point",
#         "Q10_E_point": "Q10_E_point",
#         "Q11_ans": "Q11_ans",
#         "Q11_P_point": "Q11_P_point",
#         "Q11_E_point": "Q11_E_point",
#         "Q12_ans": "Q12_ans",
#         "Q12_P_point": "Q12_P_point",
#         "Q12_E_point": "Q12_E_point",
#         "total_earned_point": "Total_earned_point",
#         "final_result": "Final_result",
#         "report": "report"
#     },
#     "physicalfrailty": {
#         "uuid": "uuid",
#         "User_uuid": "User_uuid",
#         "PF_test_id": "PF_test_id",
#         "Walking_speed": "Walking_speed",
#         "walking_speed_created_at": "walking_speed_created_at",
#         "walking_speed_is_done": "walking_speed_is_done",
#         "Functional_reach": "Functional_reach",
#         "functional_reach_created_at": "functional_reach_created_at",
#         "functional_reach_is_done": "functional_reach_is_done",
#         "Standing_on_one_leg": "Standing_on_one_leg",
#         "standing_on_one_leg_created_at": "standing_on_one_leg_created_at",
#         "standing_on_one_leg_is_done": "standing_on_one_leg_is_done",
#         "Time_up_and_go": "Time_up_and_go",
#         "time_up_and_go_created_at": "time_up_and_go_created_at",
#         "time_up_and_go_is_done": "time_up_and_go_is_done",
#         "seated_forward_bend": "seated_forward_bend",
#         "seated_forward_bend_created_at": "seated_forward_bend_created_at",
#         "seated_forward_bend_is_done": "seated_forward_bend_is_done",
#         "grip_strength": "grip_strength",
#         "grip_strength_created_at": "grip_strength_created_at",
#         "grip_strength_is_done": "grip_strength_is_done",
#         "created_at": "created_at",
#         "session_date": "session_date",
#         "session_status": "session_status",
#         "session_submitted_at": "session_submitted_at",
#         "sync_status": "sync_status",
#         "user": "user"
#     },
#     "report": {
#         "uuid": "uuid",
#         "Report_test_id": "Report_test_id",
#         "user_uuid": "user_uuid",
#         "Dep_test_id": "Dep_test_id",
#         "Dem_test_id": "Dem_test_id",
#         "PF_test_id": "PF_test_id",
#         "created_at": "created_at",
#         "generated_by": "generated_by",
#         "updated_at": "updated_at",
#         "sync_status": "sync_status",
#         "remarks": "remarks"
#     }
# }
#
# async def sync_table(model_name, supabase_table):
#     print(f"[{datetime.datetime.now()}] Online - Syncing {model_name} -> {supabase_table}...")
#
#     # Use model_name for local Prisma lookup
#     model = getattr(prisma, model_name)
#     unsynced_records = await model.find_many(where={"sync_status": 0})
#
#     if not unsynced_records:
#         print(f"No pending records for {model_name}")
#         return
#
#     async with httpx.AsyncClient() as client:
#         for r in unsynced_records:
#             # Use model_name to get the correct COLUMN_MAPPING
#             payload = {
#                 COLUMN_MAPPING[model_name].get(k, k): (v.isoformat() if isinstance(v, datetime.datetime) else v)
#                 for k, v in r.__dict__.items()
#                 if k not in RELATION_FIELDS and v is not None and k != "sync_status"
#             }
#
#             try:
#                 # Use supabase_table for the URL
#                 url = f"{SUPABASE_URL}{supabase_table}"
#                 response = await client.post(url, headers=HEADERS, json=payload)
#
#                 if response.status_code in (200, 201):
#                     await model.update(where={"uuid": r.uuid}, data={"sync_status": 1})
#                     print(f"Successfully synced {model_name} UUID: {r.uuid}")
#                 else:
#                     print(f"Failed {model_name}: {response.status_code} - {response.text}")
#             except Exception as e:
#                 print(f"Error syncing {model_name}: {e}")
#
# async def main():
#     await prisma.connect()
#     for model_name, supabase_table in RELATION_FIELDS.items():
#         await sync_table(model_name, supabase_table)
#     await prisma.disconnect()
#
# if __name__ == "__main__":
#     asyncio.run(main())

import asyncio
import datetime
import httpx
import os
import requests
from prisma import Prisma
from dotenv import load_dotenv

load_dotenv()
prisma = Prisma()

# --- CONFIGURATION ---
SUPABASE_URL = os.getenv("SUPABASE_URL").rstrip("/") + "/rest/v1/"
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"  # Optimization: don't ask Supabase to send data back
}

# Mapping Local Model -> Supabase Table
TABLES_MAP = {
    "user": "user",
    "depression_screening": "Depression_Screening",
    "dementia_screening": "Dementia_Screening",
    "physicalfrailty": "physical_frailty",
    "report": "report"
}

# Field mapping: Prisma field -> Supabase column
COLUMN_MAPPING = {
    "user": {
        "uuid": "uuid",
        "n_id": "N_ID",
        "name": "Name",
        "age": "Age",
        "gender": "Gender",
        "national_id": "National_ID",
        "is_deleted": "is_deleted",
        "assigned_doctor_uuid": "assigned_doctor_uuid",
        "created_at": "created_at",
        "updated_at": "updated_at",
        "sync_status": "sync_status"
    },
    "depression_screening": {
        "uuid": "uuid",
        "user_uuid": "User_uuid",
        "Dep_test_id": "Dep_test_id",
        "created_at": "created_at",
        "sync_status": "sync_status",
        "is_submitted": "is_submitted",
        "completed_at": "completed_at",
        "Q1_ans": "Q1_ans",
        "Q1_ans_score": "Q1_ans_score",
        "Q2_ans": "Q2_ans",
        "Q2_ans_score": "Q2_ans_score",
        "Q3_ans": "Q3_ans",
        "Q3_ans_score": "Q3_ans_score",
        "Q4_ans": "Q4_ans",
        "Q4_ans_score": "Q4_ans_score",
        "Q5_ans": "Q5_ans",
        "Q5_ans_score": "Q5_ans_score",
        "Q6_ans": "Q6_ans",
        "Q6_ans_score": "Q6_ans_score",
        "Q7_ans": "Q7_ans",
        "Q7_ans_score": "Q7_ans_score",
        "Q8_ans": "Q8_ans",
        "Q8_ans_score": "Q8_ans_score",
        "Q9_ans": "Q9_ans",
        "Q9_ans_score": "Q9_ans_score",
        "Q10_ans": "Q10_ans",
        "Q10_ans_score": "Q10_ans_score",
        "Q11_ans": "Q11_ans",
        "Q11_ans_score": "Q11_ans_score",
        "Q12_ans": "Q12_ans",
        "Q12_ans_score": "Q12_ans_score",
        "Q13_ans": "Q13_ans",
        "Q13_ans_score": "Q13_ans_score",
        "Q14_ans": "Q14_ans",
        "Q14_ans_score": "Q14_ans_score",
        "Q15_ans": "Q15_ans",
        "Q15_ans_score": "Q15_ans_score",
        "final_scores": "Final_scores",
        "final_result": "Final_result",
        "report": "report"
    },
    "dementia_screening": {
        "uuid": "uuid",
        "user_uuid": "User_uuid",
        "dem_test_id": "Dem_test_id",
        "created_at": "created_at",
        "sync_status": "sync_status",
        "Q1_ans": "Q1_ans",
        "Q1_P_point": "Q1_P_point",
        "Q1_E_point": "Q1_E_point",
        "Q2_ans": "Q2_ans",
        "Q2_P_point": "Q2_P_point",
        "Q2_E_point": "Q2_E_point",
        "Q3_ans": "Q3_ans",
        "Q3_P_point": "Q3_P_point",
        "Q3_E_point": "Q3_E_point",
        "Q4_ans": "Q4_ans",
        "Q4_P_point": "Q4_P_point",
        "Q4_E_point": "Q4_E_point",
        "Q5_ans": "Q5_ans",
        "Q5_P_point": "Q5_P_point",
        "Q5_E_point": "Q5_E_point",
        "Q6_ans": "Q6_ans",
        "Q6_P_point": "Q6_P_point",
        "Q6_E_point": "Q6_E_point",
        "Q7_ans": "Q7_ans",
        "Q7_P_point": "Q7_P_point",
        "Q7_E_point": "Q7_E_point",
        "Q8_ans": "Q8_ans",
        "Q8_P_point": "Q8_P_point",
        "Q8_E_point": "Q8_E_point",
        "Q9_ans": "Q9_ans",
        "Q9_P_point": "Q9_P_point",
        "Q9_E_point": "Q9_E_point",
        "Q10_ans": "Q10_ans",
        "Q10_P_point": "Q10_P_point",
        "Q10_E_point": "Q10_E_point",
        "Q11_ans": "Q11_ans",
        "Q11_P_point": "Q11_P_point",
        "Q11_E_point": "Q11_E_point",
        "Q12_ans": "Q12_ans",
        "Q12_P_point": "Q12_P_point",
        "Q12_E_point": "Q12_E_point",
        "total_earned_point": "Total_earned_point",
        "final_result": "Final_result",
        "is_submitted": "is_submitted",
        "completed_at": "completed_at",
        "report": "report"
    },
    "physicalfrailty": {
        "uuid": "uuid",
        "User_uuid": "User_uuid",
        "PF_test_id": "PF_test_id",
        "Walking_speed_r1": "Walking_speed_r1",
        "walking_speed_r1_created_at": "walking_speed_r1_created_at",
        "walking_speed_r1_is_done": "walking_speed_r1_is_done",
        "Walking_speed_r2": "Walking_speed_r2",
        "walking_speed_r2_created_at": "walking_speed_r2_created_at",
        "walking_speed_r2_is_done": "walking_speed_r2_is_done",
        "Functional_reach_r1": "Functional_reach_r1",
        "functional_reach_r1_created_at": "functional_reach_r1_created_at",
        "functional_reach_r1_is_done": "functional_reach_r1_is_done",
        "Functional_reach_r2": "Functional_reach_r2",
        "functional_reach_r2_created_at": "functional_reach_r2_created_at",
        "functional_reach_r2_is_done": "functional_reach_r2_is_done",
        "Standing_on_one_leg_r1": "Standing_on_one_leg_r1",
        "standing_on_one_leg_r1_created_at": "standing_on_one_leg_r1_created_at",
        "standing_on_one_leg_r1_is_done": "standing_on_one_leg_r1_is_done",
        "Standing_on_one_leg_r2": "Standing_on_one_leg_r2",
        "standing_on_one_leg_r2_created_at": "standing_on_one_leg_r2_created_at",
        "standing_on_one_leg_r2_is_done": "standing_on_one_leg_r2_is_done",
        "Time_up_and_go_r1": "Time_up_and_go_r1",
        "time_up_and_go_r1_created_at": "time_up_and_go_r1_created_at",
        "time_up_and_go_r1_is_done": "time_up_and_go_r1_is_done",
        "Time_up_and_go_r2": "Time_up_and_go_r2",
        "time_up_and_go_r2_created_at": "time_up_and_go_r2_created_at",
        "time_up_and_go_r2_is_done": "time_up_and_go_r2_is_done",
        "seated_forward_bend_r1": "seated_forward_bend_r1",
        "seated_forward_bend_r1_created_at": "seated_forward_bend_r1_created_at",
        "seated_forward_bend_r1_is_done": "seated_forward_bend_r1_is_done",
        "seated_forward_bend_r2": "seated_forward_bend_r2",
        "seated_forward_bend_r2_created_at": "seated_forward_bend_r2_created_at",
        "seated_forward_bend_r2_is_done": "seated_forward_bend_r2_is_done",
        "created_at": "created_at",
        "sync_status": "sync_status",
        "user": "user"
    },
    "report": {
        "uuid": "uuid",
        "Report_test_id": "Report_test_id",
        "user_uuid": "user_uuid",
        "Dep_test_id": "Dep_test_id",
        "Dem_test_id": "Dem_test_id",
        "PF_test_id": "PF_test_id",
        "created_at": "created_at",
        "generated_by": "generated_by",
        "updated_at": "updated_at",
        "sync_status": "sync_status",
        "remarks": "remarks"
    }
}

import datetime

def serialize_value(value):
    """
    Convert datetime to ISO string if needed.
    Leave other values untouched.
    """
    try:
        if isinstance(value, datetime.datetime):
            return value.isoformat()
        return value
    except TypeError:
        # fallback for weird objects
        return str(value)

# Fields to ignore (Prisma relations)
IGNORE_FIELDS = ["DementiaScreenings", "DepressionScreenings", "physicalFrailty", "Reports", "user",
                 "Dementia_Screening", "Depression_Screening", "assignedDoctor", "generator"]


# --- HELPER: CHECK INTERNET ---
async def is_internet_available():
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            # Try to hit Supabase's health/rest endpoint
            response = await client.get(SUPABASE_URL, headers={"apikey": SUPABASE_KEY})
            return response.status_code == 200
    except Exception:
        return False


# --- SYNC LOGIC ---
PRIMARY_KEY = {
    "user": "uuid",
    "depression_screening": "uuid",
    "dementia_screening": "uuid",
    "physical_frailty": "PF_test_id",
    "report": "Report_test_id"
}

# --- SYNC LOGIC ---
async def sync_table(model_name, supabase_table):
    try:
        model = getattr(prisma, model_name)
        unsynced_records = await model.find_many(where={"sync_status": 0})
        if not unsynced_records:
            return 0

        success_count = 0
        PRIMARY_KEY = {
            "user": "uuid",
            "depression_screening": "uuid",
            "dementia_screening": "uuid",
            "physicalfrailty": "PF_test_id",
            "report": "Report_test_id"
        }

        key_field = PRIMARY_KEY.get(model_name, "uuid")

        async with httpx.AsyncClient() as client:
            for r in unsynced_records:
                # Build payload
                payload = {}
                for k, v in r.__dict__.items():
                    clean_key = COLUMN_MAPPING.get(model_name, {}).get(k, k)
                    if k not in IGNORE_FIELDS and k != "sync_status" and v is not None:
                        payload[clean_key] = serialize_value(v)

                # Make sure payload includes primary key
                payload[key_field] = getattr(r, key_field)

                # Try upsert
                response = await client.post(
                    f"{SUPABASE_URL}{supabase_table}",
                    headers=HEADERS,
                    json=payload,
                    # params={"on_conflict": [key_field]}  # upsert key
                    params={"on_conflict": key_field}
                )

                # Handle response
                if response.status_code in (200, 201, 204):
                    # success → mark local record synced
                    await model.update(
                        where={key_field: getattr(r, key_field)},
                        data={"sync_status": 1}
                    )
                    success_count += 1

                elif response.status_code == 409:
                    # fallback: update via PATCH if conflict
                    update_url = f"{SUPABASE_URL}{supabase_table}?{key_field}=eq.{getattr(r, key_field)}"
                    update_response = await client.patch(update_url, headers=HEADERS, json=payload)
                    if update_response.status_code in (200, 204):
                        await model.update(
                            where={key_field: getattr(r, key_field)},
                            data={"sync_status": 1}
                        )
                        success_count += 1
                    else:
                        print(f"  [!] Failed updating {model_name} ({getattr(r, key_field)}): {update_response.status_code}")

                else:
                    print(f"  [!] Failed {model_name} ({getattr(r, key_field)}): {response.status_code}")

        return success_count

    except Exception as e:
        print(f"  [!] Critical error in {model_name}: {e}")
        return 0


# --- MAIN LOOP ---
async def main():
    print("🚀 Sync Worker Started. Press Ctrl+C to stop.")
    await prisma.connect()

    try:
        while True:
            if await is_internet_available():
                total_synced = 0
                for model, table in TABLES_MAP.items():
                    synced = await sync_table(model, table)
                    total_synced += synced

                if total_synced > 0:
                    print(f"✅ [{datetime.datetime.now().strftime('%H:%M:%S')}] Synced {total_synced} records.")
            else:
                print(f"☁️ [{datetime.datetime.now().strftime('%H:%M:%S')}] Offline - Waiting for internet...")

            # Wait for 30 seconds before checking again
            await asyncio.sleep(30)

    except asyncio.CancelledError:
        print("Worker stopping...")
    finally:
        await prisma.disconnect()


if __name__ == "__main__":
    # Ensure your COLUMN_MAPPING from your previous snippet is included here!
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass