"""REST endpoints that orchestrate the existing RISC-V verification toolkit."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import random
import logging
import threading
import time
import uuid

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..comparator import compare_states
from ..cpu import CPUState
from ..coverage import Coverage
from ..isa import I_ARITH, R_TYPE, Mnemonic, SUPPORTED
from ..reference_model import ReferenceModel
from ..reporting import write_json
from ..runner import VerificationRunner, initial_state
from ..simulator import Simulator

router = APIRouter(prefix="/api")
MAX_TESTS = 10_000
MAX_TEST_ID = 10_000
REPORTS_DIR = Path(__file__).resolve().parents[3] / "reports"


class RunRequest(BaseModel):
    tests: int = Field(default=100, ge=1, le=MAX_TESTS)
    seed: int | None = Field(default=None, ge=0, le=(1 << 63) - 1)
    coverage_guided: bool = False
    min_length: int = Field(default=8, ge=1, le=256)
    max_length: int = Field(default=32, ge=1, le=256)
    memory_size: int = Field(default=4096, ge=4, le=65_536, multiple_of=4)


class ReplayRequest(BaseModel):
    seed: int = Field(ge=0, le=(1 << 63) - 1)
    test_id: int = Field(ge=1, le=MAX_TEST_ID)
    coverage_guided: bool = False
    min_length: int = Field(default=8, ge=1, le=256)
    max_length: int = Field(default=32, ge=1, le=256)
    memory_size: int = Field(default=4096, ge=4, le=65_536, multiple_of=4)


class JobStore:
    """Small in-memory job registry; only one verification run executes at once."""
    def __init__(self):
        self.jobs: dict[str, dict] = {}
        self.latest_id: str | None = None
        self.active_id: str | None = None
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="riscv-verify")

    def create(self, request: RunRequest, seed: int) -> dict:
        with self.lock:
            if self.active_id is not None:
                raise HTTPException(status_code=409, detail={"code": "run_in_progress", "message": "A verification job is already running."})
            job_id = uuid.uuid4().hex
            job = {
                "id": job_id,
                "status": "starting",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "started_at": None,
                "completed_at": None,
                "request": request.model_dump() if hasattr(request, "model_dump") else request.dict(),
                "seed": seed,
                "progress": {"completed": 0, "total": request.tests, "percent": 0.0},
                "summary": None,
                "results": [],
                "_programs": {},
                "_coverage": None,
                "_report_path": None,
                "error": None,
            }
            self.jobs[job_id] = job
            self.latest_id = job_id
            self.active_id = job_id
            # Keep memory bounded across multiple browser sessions.
            for old_id in list(self.jobs):
                if old_id != job_id and old_id != self.active_id:
                    del self.jobs[old_id]
            self.executor.submit(self._execute, job_id, request, seed)
            return job

    def _execute(self, job_id: str, request: RunRequest, seed: int) -> None:
        with self.lock:
            job = self.jobs[job_id]
            job["status"] = "running"
            job["started_at"] = datetime.now(timezone.utc).isoformat()
        start = time.perf_counter()
        try:
            if request.min_length > request.max_length:
                raise ValueError("min_length must be less than or equal to max_length")
            runner = VerificationRunner(seed, request.min_length, request.max_length, request.memory_size, request.coverage_guided)
            for test_id in range(1, request.tests + 1):
                test_start = time.perf_counter()
                result = runner.run_one(test_id)
                elapsed = time.perf_counter() - test_start
                row = serialize_result(result, elapsed)
                with self.lock:
                    job["results"].append(row)
                    job["_programs"][test_id] = result.program
                    completed = test_id
                    job["progress"] = {"completed": completed, "total": request.tests, "percent": 100.0 * completed / request.tests}
                    job["_coverage"] = runner.coverage.report()

            summary = {
                "seed": seed,
                "tests_requested": request.tests,
                "tests_run": len(runner.results),
                "passed": sum(item.passed for item in runner.results),
                "failed": sum(not item.passed for item in runner.results),
                "total_instructions_generated": sum(len(item.program) for item in runner.results),
                "total_instructions_executed": runner.total_instructions,
                "elapsed_seconds": time.perf_counter() - start,
                "coverage": runner.coverage.report(),
                "failures": runner.results_to_json([item for item in runner.results if not item.passed]),
            }
            report_path = REPORTS_DIR / "web-results.json"
            write_json({"generated_at": datetime.now(timezone.utc).isoformat(), **summary}, report_path)
            with self.lock:
                job["summary"] = summary
                job["_report_path"] = report_path
                job["status"] = "completed"
                job["completed_at"] = datetime.now(timezone.utc).isoformat()
        except Exception as exc:
            logging.getLogger(__name__).exception("Verification job %s failed", job_id)
            with self.lock:
                job["status"] = "failed"
                job["error"] = {"code": "verification_error", "message": "Verification could not be completed. Check the server log for details."}
                job["completed_at"] = datetime.now(timezone.utc).isoformat()
        finally:
            with self.lock:
                if self.active_id == job_id:
                    self.active_id = None

    def latest(self) -> dict | None:
        with self.lock:
            return self.jobs.get(self.latest_id) if self.latest_id else None

    def get(self, job_id: str) -> dict | None:
        with self.lock:
            return self.jobs.get(job_id)


store = JobStore()


def serialize_result(result, elapsed: float) -> dict:
    mismatches = [m.to_dict() if hasattr(m, "to_dict") else m for m in result.mismatches]
    first = mismatches[0] if mismatches else None
    label = f"{first.get('location')}: expected {first.get('expected')}, got {first.get('actual')}" if first else None
    return {
        "test_id": result.test_id,
        "seed": result.seed,
        "instructions_executed": result.instructions_executed,
        "status": "PASS" if result.passed else "FAIL",
        "mismatch_summary": label,
        "mismatches": mismatches,
        "execution_seconds": elapsed,
        "program": [str(instruction) for instruction in result.program],
    }


def public_job(job: dict) -> dict:
    return {key: value for key, value in job.items() if not key.startswith("_")}


def load_latest_job() -> dict:
    job = store.latest()
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "no_results", "message": "Run verification to create dashboard results."})
    return job


def detail_for_program(seed: int, test_id: int, program, mismatches=None, memory_size: int = 4096) -> dict:
    start_state = initial_state(seed + test_id, memory_size)
    actual = start_state.clone()
    expected = start_state.clone()
    executed = []
    Simulator(actual).run(program, on_step=lambda ins, _state: executed.append(ins))
    ReferenceModel(expected).execute_program(program)
    differences = compare_states(expected, actual)
    serialized = [item.to_dict() for item in differences]
    cause = None
    if serialized:
        mismatch = serialized[0]
        if mismatch["kind"] == "register":
            destination = int(mismatch["location"][1:])
            cause = next((str(ins) for ins in reversed(executed) if ins.rd == destination), None)
        elif mismatch["kind"] == "memory":
            cause = next((str(ins) for ins in reversed(executed) if ins.mnemonic == Mnemonic.SW), None)
        cause = cause or (str(executed[-1]) if executed else None)

    def memory_view(state: CPUState) -> dict:
        words = {}
        for address in range(0, state.memory.size - 3, 4):
            value = state.memory.load_word(address)
            if value:
                words[f"0x{address:08x}"] = value
        return {"size_bytes": state.memory.size, "nonzero_words": words}

    reported_mismatches = serialized or (mismatches or [])
    return {
        "test_id": test_id,
        "seed": seed,
        "status": "FAIL" if reported_mismatches else "PASS",
        "instruction_causing_failure": cause,
        "program": [str(ins) for ins in program],
        "executed_program": [str(ins) for ins in executed],
        "mismatches": reported_mismatches,
        "expected": {"registers": expected.registers, "pc": expected.pc, "memory": memory_view(expected)},
        "actual": {"registers": actual.registers, "pc": actual.pc, "memory": memory_view(actual)},
    }


@router.get("/health")
def health():
    return {"status": "ok", "service": "riscv-verify-api", "engine": "riscv_verify.VerificationRunner"}


@router.get("/summary")
def summary():
    job = store.latest()
    if job is None:
        return {"job_id": None, "status": "idle", "summary": None, "progress": None, "last_seed": None, "timestamp": None}
    return {"job_id": job["id"], "status": job["status"], "summary": job["summary"], "progress": job["progress"], "last_seed": job["seed"], "timestamp": job["completed_at"] or job["started_at"] or job["created_at"]}


@router.post("/run", status_code=202)
def start_run(request: RunRequest):
    if request.min_length > request.max_length:
        raise HTTPException(status_code=422, detail={"code": "invalid_length_range", "message": "min_length must be less than or equal to max_length."})
    seed = request.seed if request.seed is not None else random.SystemRandom().randrange(1 << 32)
    job = store.create(request, seed)
    return {"job_id": job["id"], "status": job["status"], "seed": seed, "status_url": f"/api/jobs/{job['id']}"}


@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "The requested verification job was not found."})
    return public_job(job)


@router.get("/results")
def results(offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=500), status: str = Query(default="all", pattern="^(all|PASS|FAIL)$")):
    job = load_latest_job()
    rows = job["results"]
    filtered = rows if status == "all" else [row for row in rows if row["status"] == status]
    return {"job_id": job["id"], "total": len(filtered), "offset": offset, "limit": limit, "results": filtered[offset:offset + limit]}


@router.get("/results/{test_id}")
def result_detail(test_id: int):
    if not 1 <= test_id <= MAX_TEST_ID:
        raise HTTPException(status_code=422, detail={"code": "invalid_test_id", "message": f"test_id must be between 1 and {MAX_TEST_ID}."})
    job = load_latest_job()
    if test_id > len(job["results"]):
        raise HTTPException(status_code=404, detail={"code": "test_not_found", "message": "No completed result exists for that test ID."})
    row = job["results"][test_id - 1]
    return detail_for_program(job["seed"], test_id, job["_programs"][test_id], row["mismatches"], job["request"]["memory_size"])


@router.get("/coverage")
def coverage():
    job = store.latest()
    if job is not None and job["_coverage"] is not None:
        return {"job_id": job["id"], "status": job["status"], **job["_coverage"]}
    if job is None or job["summary"] is None:
        empty = Coverage().report()
        return {"job_id": job["id"] if job else None, "status": job["status"] if job else "idle", **empty}
    return {"job_id": job["id"], "status": job["status"], **job["summary"]["coverage"]}


@router.get("/instructions")
def instructions():
    descriptions = {
        Mnemonic.ADD: "Adds two registers and writes the 32-bit result.", Mnemonic.SUB: "Subtracts the second register from the first.",
        Mnemonic.AND: "Bitwise AND of two registers.", Mnemonic.OR: "Bitwise OR of two registers.", Mnemonic.XOR: "Bitwise XOR of two registers.", Mnemonic.SLT: "Writes one when signed rs1 is less than signed rs2.",
        Mnemonic.ADDI: "Adds a sign-extended 12-bit immediate.", Mnemonic.ANDI: "Bitwise AND with a sign-extended immediate.", Mnemonic.ORI: "Bitwise OR with a sign-extended immediate.", Mnemonic.XORI: "Bitwise XOR with a sign-extended immediate.", Mnemonic.SLTI: "Writes one when signed rs1 is less than the immediate.",
        Mnemonic.LW: "Loads an aligned little-endian 32-bit word.", Mnemonic.SW: "Stores an aligned little-endian 32-bit word.",
        Mnemonic.BEQ: "Branches by a byte offset when the registers are equal.", Mnemonic.BNE: "Branches by a byte offset when the registers differ.",
        Mnemonic.LUI: "Places a 20-bit immediate in the upper register bits.", Mnemonic.AUIPC: "Adds a shifted upper immediate to the current PC.",
        Mnemonic.JAL: "Writes PC+4 to rd and jumps by a PC-relative offset.", Mnemonic.JALR: "Writes PC+4 and jumps to (rs1+imm) with bit zero cleared.",
    }
    category = {}
    for label, members in (("R-Type", R_TYPE), ("I-Type", I_ARITH), ("Memory", {Mnemonic.LW, Mnemonic.SW}), ("Branches", {Mnemonic.BEQ, Mnemonic.BNE}), ("Upper Immediate", {Mnemonic.LUI, Mnemonic.AUIPC}), ("Jumps", {Mnemonic.JAL, Mnemonic.JALR})):
        for mnemonic in members:
            category[mnemonic] = label
    return {"supported_count": len(SUPPORTED), "instructions": [{"mnemonic": m.value, "category": category[m], "description": descriptions[m]} for m in SUPPORTED]}


@router.post("/replay")
def replay(request: ReplayRequest):
    if request.test_id > MAX_TEST_ID:
        raise HTTPException(status_code=422, detail={"code": "invalid_test_id", "message": f"test_id must not exceed {MAX_TEST_ID}."})
    if request.min_length > request.max_length:
        raise HTTPException(status_code=422, detail={"code": "invalid_length_range", "message": "min_length must be less than or equal to max_length."})
    runner = VerificationRunner(request.seed, request.min_length, request.max_length, request.memory_size, request.coverage_guided)
    result = runner.replay(request.test_id)
    return detail_for_program(request.seed, request.test_id, result.program, runner.results_to_json([result])[0]["mismatches"], request.memory_size)


@router.get("/report")
def report():
    job = load_latest_job()
    if job["summary"] is None:
        return {"job_id": job["id"], "status": job["status"], "report": None}
    return {"job_id": job["id"], "status": job["status"], "generated_at": job["completed_at"], "seed": job["seed"], "summary": job["summary"], "download_url": "/api/report/download"}


@router.get("/report/download")
def download_report():
    job = load_latest_job()
    if job["_report_path"] is None:
        raise HTTPException(status_code=409, detail={"code": "report_not_ready", "message": "The verification report is not ready yet."})
    return FileResponse(job["_report_path"], media_type="application/json", filename="riscv-verification-report.json")
