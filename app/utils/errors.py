from fastapi import HTTPException

def not_found(message="Resource not found"):
    raise HTTPException(status_code=404, detail=message)

def forbidden(message="Forbidden"):
    raise HTTPException(status_code=403, detail=message)

def unauthorized(message="Unauthorized"):
    raise HTTPException(status_code=401, detail=message)

def bad_request(message="Bad request"):
    raise HTTPException(status_code=400, detail=message)

def conflict(message="Conflict"):
    raise HTTPException(status_code=409, detail=message)

def internal_server_error(message="Internal server error"):
    raise HTTPException(status_code=500, detail=message)