@echo off
title Healthcare Clinic Local Node

:: 1. Force API to use Local PostgreSQL for Patient Testing
set DATABASE_URL=postgresql://postgres:admin123@localhost:5432/local_clinic

:: 2. Initialize Database (Safe Check)
python setup.py

:: 3. Start API (For Patients/Local Reports)
start "Clinic_API" cmd /k "uvicorn app.main:app --reload --port 8000"

:: 4. Start Sync Worker (Moves local data to Supabase when Online)
start "Sync_Worker" cmd /k "python sync_worker.py"

echo ---------------------------------------------------
echo PATIENT MODE: Always Active (Local DB)
echo ADMIN/DOCTOR MODE: Requires Internet (Supabase Sync)
echo ---------------------------------------------------
pause