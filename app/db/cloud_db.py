#
# from supabase import create_client
# from app.config import settings
# import os
#
# url: str = os.getenv("SUPABASE_URL")
# key: str = os.getenv("SUPABASE_KEY")
#
# # Use cloud DB / Supabase
# supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
#
# # Debugging
# print(f"--- Supabase Config Check ---")
# print(f"URL found: {settings.SUPABASE_URL}")
# print(f"Key found: {'[HIDDEN]' if settings.SUPABASE_KEY else 'None'}")
# print(f"-----------------------------")

from supabase import create_client
from app.config import settings

# Initialize the Supabase Client
# Note: create_client uses the HTTPS URL, not the postgresql:// string
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def check_supabase():
    print(f"--- Supabase Config Check ---")
    print(f"URL: {settings.SUPABASE_URL}")
    print(f"Key: {'[FOUND]' if settings.SUPABASE_KEY else '[MISSING]'}")
    print(f"-----------------------------")

check_supabase()