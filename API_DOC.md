# Screening Frailty API Documentation

This document provides detailed API information for the **Frailty Screening APIs**.

---

## 1. Users

### Create a User
- **POST** `/users`
- **Body (JSON)**:
```json
{
  "name": "user test1",
  "age": 65,
  "gender": "Male",
  "national_id": "123-65-6689"
}
```
---

## 2. Depression Tests

### Submit Depression Test
- **POST** `/depression`
- **Body (JSON)**:
```json
{
  "n_id": N_ID,
  "answers": [
    { "question_no": 1, "answer": true, "score": 0 },
    { "question_no": 2, "answer": false, "score": 1 },
    { "question_no": 3, "answer": true, "score": 0 },
    { "question_no": 4, "answer": false, "score": 1 },
    { "question_no": 5, "answer": true, "score": 0 },
    { "question_no": 6, "answer": false, "score": 1 },
    { "question_no": 7, "answer": true, "score": 0 },
    { "question_no": 8, "answer": false, "score": 1 },
    { "question_no": 9, "answer": true, "score": 0 },
    { "question_no": 10, "answer": false, "score": 1 },
    { "question_no": 11, "answer": false, "score": 1 },
    { "question_no": 12, "answer": false, "score": 1 },
    { "question_no": 13, "answer": false, "score": 1 },
    { "question_no": 14, "answer": false, "score": 1 },
    { "question_no": 15, "answer": false, "score": 1 }
  ]
}

{
  "user_uuid": "f1ae78ae-f350-47b3-b50b-626ec7471e2d",
  "answers": [
    {
      "question_no": 1,
      "answer": true,
      "score": 1
    }
  ]
}
{
  "test_id": 1,
  "answers": [
    {"question_no": 1, "answer": true, "score": 1},
    {"question_no": 2, "answer": false, "score": 0},
    {"question_no": 3, "answer": true, "score": 1}
  ]
}

{
  "test_id": 3,
  "submit_test": true
}


```
### Update Depression Tests by test ID
- **POST** `/depression/update/{Dep_test_id}`
- **Body (JSON)**:
```json
{
  "user_uuid": "uuid-of-user",
  "answers": [
   { "question_no": 8, "answer": true, "score": 0 },
    { "question_no": 9, "answer": false, "score": 1 }
  ]
}
```
---

## 3. Dementia Tests

### Submit Dementia Test
- **POST** `/dementia`
- **Body (JSON)**:
```json
{
  "n_id": N_ID,
   "questions": [
    {
      "no": 1,
      "answer": "2026",
      "possible": 5,
      "earned": 5
    },
    {
      "no": 2,
      "answer": "Hospital",
      "possible": 5,
      "earned": 0
    },
    {
      "no": 3,
      "answer": "Apple",
      "possible": 3,
      "earned": 3
    },
    {
      "no": 4,
      "answer": "93",
      "possible": 5,
      "earned": 5
    },
    {
      "no": 5,
      "answer": "Pen",
      "possible": 4,
      "earned": 4
    },
    {
      "no": 6,
      "answer": " Apple",
      "possible": 3,
      "earned": 3
    },
    {
    "no": 7,
    "answer": "Watch",
    "possible": 1,
    "earned": 1
    },
    {
    "no": 8,
    "answer": "Accept",
    "possible": 1,
    "earned": 1
    },
    {
    "no": 9,
    "answer": "Accept",
    "possible": 3,
    "earned": 3
    },
    {
    "no": 10,
    "answer": "Reject",
    "possible": 1,
    "earned": 0
    },
    {
    "no": 11,
    "answer": "Accept",
    "possible": 1,
    "earned": 1
    },
    {
    "no": 12,
    "answer":
    "Accept",
    "possible": 1,
     "earned": 1
     }
  ]

}

{
  "user_uuid": "5257ae53-075c-4307-9ce0-9c6add7e5145",
  "questions": [
    {"no":1,"answer":"A","possible":1,"earned":1}
  ]
}

{
  "test_id": 3,
  "questions": [
    {"no":2,"answer":"B","possible":1,"earned":0}
  ]
}

{
  "test_id": 3,
  "submit_test": true
}
```
### Update Dementia Test by test ID
- **POST** `/dementia/update/{Dem_test_id}`
- **Body (JSON)**:
```json
{
  "user_uuid": "uuid-of-user",
  "questions": [
  {
      "no": 4,
      "answer": "100",
      "possible": 5,
      "earned": 0
    }
  ]
}


```
---

## 3. Physical Frailty Tests

### Submit PF Test
- **POST** `/physicalfrailty/round1
- **POST** `/physicalfrailty/round2
Add the tests one by one:

```json
{
  "n_id": N_ID,
  "test": "walking_speed",
  "value": 5.2
}
```

```json
{
  "n_id": N_ID,
  "test": "functional_reach",
  "value": 38.0
}
```

```json
{
  "n_id": N_ID,
  "test": "standing_on_one_leg",
  "value": 14.5
}
```

```json
{
  "n_id": N_ID,
  "test": "time_up_and_go",
  "value": 9.3
}
```

```json
{
  "user_uuid": "n_id": N_ID,
  "test": "seated_forward_bend",
  "value": 23.0
}
```

### Sloss PF Tests session
- **POST** `/physicalfrailty/end-session/{pf_test_id}`
---

## 4. Report

### Generate Report
- **POST** `/report/generate/{user_uuid}`

### Update Report
- **POST** `/report/update/{report_test_id}`
```json
{
  "depression_answers": [
    { "question_no": 1, "answer": true, "score": 0 },
    { "question_no": 2, "answer": true, "score": 0 },
    { "question_no": 3, "answer": false, "score": 1 },
    { "question_no": 4, "answer": false, "score": 1 }
  ],
  "dementia_answers": [
    { "no": 1, "answer": "2026", "possible": 5, "earned": 5 },
    { "no": 2, "answer": "Clinic", "possible": 5, "earned": 4 }
  ]
} OR
{
    "remarks": "Patient needs follow-up for memory assessment."
}

OR

{
  "dementia_answers": [
    {
      "no": 3,
      "answer": "Apple",
      "possible": 3,
      "earned": 3
    }
  ],
  "remarks": "Patient needs follow-up for memory assessment."
}
```

## 5. Admin and Doctor

⚠ All protected APIs require login first (cookie-based session).

------------------------------------------------------------------------

# 🔐 LOGIN (Doctor or Super Admin)

POST /auth/login

Body (JSON): { "email": "admin@gmail.com", "password": "newadmin123" }

After login: - Open Postman → Cookies - Confirm `session` cookie is
stored - Expiry should be 3 days

------------------------------------------------------------------------

# 👑 SUPER ADMIN APIs

## Create Doctor

POST /admin/create-doctor

{ "name": "Dr xyx", "email": "dr2@example.com", "password": "123456" }

## View All Doctors

GET /admin/doctors

## Delete Doctor

POST /admin/delete-doctor

## Reset Doctor Password

POST /admin/reset-doctor-password/{doctor_uuid}

{ "new_password": "newpass123" }

## Assign Doctor to Patient

POST /admin/assign-doctor/{user_uuid}

{ "doctor_uuid": "doctor-uuid-here" }



## Edit User

POST /admin/update/{user_uuid}

{ "name": "Updated Name", "age": 65, "gender": "Male", "national_id":
"1234512345123" }

## Delete User

DELETE /admin/delete-user/{user_uuid}

## Delete Invalid Test

DELETE /admin/delete-test/{test_type}/{test_id}

Examples: /admin/delete-test/depression/1 /admin/delete-test/dementia/2
/admin/delete-test/physical/3

## View All Reports

GET /admin/reports

## Delete Report

DELETE /admin/delete-report/{report_id}

## Track Report Generator

GET /admin/report-generator/{report_id}

------------------------------------------------------------------------

# 👨‍⚕️ DOCTOR APIs

## View My Patients

GET /admin/my-patients

------------------------------------------------------------------------

# 👨‍⚕️👑 DOCTOR + ADMIN APIs

## View Report by Report_test_id

GET /admin/reportid/{report_test_id}

## View Reports by Serial ID (N_ID)

GET /admin/serial/{n_id}3

## View Reports by National ID

GET /admin/national/{national_id} 123446789

GET /admin/tests/by-national/{national_id}

## View All Users

GET /admin/users

## View All Tests

GET /admin/tests

------------------------------------------------------------------------

# 🔑 CHANGE PASSWORD (Doctor + Super Admin)

POST /admin/change-password

{ "old_password": "123456", "new_password": "newsecure123" }

------------------------------------------------------------------------

# Doctor getting data

### Get User
- **GET** `/read/{national_id}`

### Get User Tests
- **GET** `/read/tests/{national_id}`

### Get Depression Tests by N_ID
- **GET** `/read/depression/id/{n_id}`

### Get Depression Test by National_ID
- **GET** `/read/depression/Nid/{national_id}`

### Get Single Depression Test with User
- **GET** `/read/depressiontest/{Dep_test_id}`

### Get Dementia Tests by N_ID
- **GET** `/read/dementia/id/{n_id}`

### Get Dementia Test by National_ID
- **GET** `/read/dementia/Nid/{national_id}`

### Get Single Dementia Test with User
- **GET** `/read/dementia/test/{Dem_test_id}`

### Get PF Tests by N_ID
- **GET** `/read/frailty/id/{n_id}`

### Get PF Tests by National_ID
- **GET** `/read/frailty/nid/{national_id}`

### Get Single PF Test with User
- **GET** `/read/frailty/test/{pf_test_id}`

### Get Report by Report_test_id
- **GET** `/read/report/reportid/{report_test_id}`

### Get Reports by N_ID
- **GET** `/read/report/nid/{n_id}`

### Get Reports by National_ID
- **GET** `/read/report/national/{national_id}`