# Assessment Session Database API Design

## Overview

Each test session saves **2 entries per test** to the database. When a session is initiated for a recipient, the table is populated with all required entries upfront, including placeholder rows for both values of each test.

---

## Session Initialization

When session `XYZ` is started for **Recipient A**, the database is initialized with the following structure:

```python
session = {
    "session_id": "XYZ",
    "recipient_id": "A",
    "created_at": "<timestamp>"
}
```

---

## Test Variables & API Format

### Test 1 — Walking Speed

| Entry | Variable | Description         |
|-------|----------|---------------------|
| 1     | `time1`  | First timing value  |
| 2     | `time2`  | Second timing value |

```python
# POST - Save Walking Speed values
payload = {
    "session_id": "XYZ",
    "recipient_id": "A",
    "test": "walking_speed",
    "time1": <value>,   # Entry 1 — value to be saved
    "time2": <value>    # Entry 2 — value to be saved
}
```

---

### Test 2 — Functional Reach

| Entry | Variable    | Description            |
|-------|-------------|------------------------|
| 1     | `distance1` | First distance value   |
| 2     | `distance2` | Second distance value  |

```python
# POST - Save Functional Reach values
payload = {
    "session_id": "XYZ",
    "recipient_id": "A",
    "test": "functional_reach",
    "distance1": <value>,   # Entry 1 — value to be saved
    "distance2": <value>    # Entry 2 — value to be saved
}
```

---

### Test 3 — Seated Forward Bend

| Entry | Variable    | Description            |
|-------|-------------|------------------------|
| 1     | `distance1` | First distance value   |
| 2     | `distance2` | Second distance value  |

```python
# POST - Save Seated Forward Bend values
payload = {
    "session_id": "XYZ",
    "recipient_id": "A",
    "test": "seated_forward_bend",
    "distance1": <value>,   # Entry 1 — value to be saved
    "distance2": <value>    # Entry 2 — value to be saved
}
```

---

### Test 4 — Standing on One Leg

| Entry | Variable | Description         |
|-------|----------|---------------------|
| 1     | `time1`  | First timing value  |
| 2     | `time2`  | Second timing value |

```python
# POST - Save Standing on One Leg values
payload = {
    "session_id": "XYZ",
    "recipient_id": "A",
    "test": "standing_one_leg",
    "time1": <value>,   # Entry 1 — value to be saved
    "time2": <value>    # Entry 2 — value to be saved
}
```

---

### Test 5 — Timed Up and Go (TUG)

| Entry | Variable | Description         |
|-------|----------|---------------------|
| 1     | `time1`  | First timing value  |
| 2     | `time2`  | Second timing value |

```python
# POST - Save Timed Up and Go values
payload = {
    "session_id": "XYZ",
    "recipient_id": "A",
    "test": "timed_up_and_go",
    "time1": <value>,   # Entry 1 — value to be saved
    "time2": <value>    # Entry 2 — value to be saved
}
```

---

## Full Session Payload (All Tests)

A complete session submission with all 5 tests (10 entries total):

```python
full_session_payload = {
    "session_id": "XYZ",
    "recipient_id": "A",
    "tests": {
        "walking_speed": {
            "time1": <value>,
            "time2": <value>
        },
        "functional_reach": {
            "distance1": <value>,
            "distance2": <value>
        },
        "seated_forward_bend": {
            "distance1": <value>,
            "distance2": <value>
        },
        "standing_one_leg": {
            "time1": <value>,
            "time2": <value>
        },
        "timed_up_and_go": {
            "time1": <value>,
            "time2": <value>
        }
    }
}
```

---

## Summary Table

| Test                  | Variable 1   | Variable 2   | Unit     |
|-----------------------|--------------|--------------|----------|
| Walking Speed         | `time1`      | `time2`      | seconds  |
| Functional Reach      | `distance1`  | `distance2`  | cm / in  |
| Seated Forward Bend   | `distance1`  | `distance2`  | cm / in  |
| Standing on One Leg   | `time1`      | `time2`      | seconds  |
| Timed Up and Go       | `time1`      | `time2`      | seconds  |

> **Total DB entries per session:** 5 tests × 2 entries = **10 entries**
