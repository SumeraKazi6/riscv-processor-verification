"""FastAPI application serving the verification API and local dashboard."""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .routes import router

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app = FastAPI(
    title="RISC-V Processor Verification Toolkit",
    description="REST API and dashboard for the existing seeded RV32I differential verification engine.",
    version="1.0.0",
)

# FastAPI serves the frontend on the same origin by default. These explicit
# development origins support an optional local static server on port 5500.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(router)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="frontend")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(part) for part in item["loc"] if part != "body"), "message": item["msg"]} for item in exc.errors()]
    return JSONResponse(status_code=422, content={"error": {"code": "invalid_request", "message": "Check the submitted values and try again.", "fields": errors}})


@app.exception_handler(Exception)
async def unexpected_error_handler(_request: Request, _exc: Exception):
    # Do not return stack traces or local filesystem paths to browser clients.
    return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "The server could not complete this request."}})


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(FRONTEND_DIR / "index.html")
