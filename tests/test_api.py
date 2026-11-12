import time

from fastapi.testclient import TestClient

from riscv_verify.api import routes
from riscv_verify.api.main import app
from riscv_verify.instruction import Instruction
from riscv_verify.isa import Mnemonic
from riscv_verify.simulator import Simulator

client = TestClient(app)


def wait_for_job(job_id: str, timeout: float = 5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(0.02)
    raise AssertionError("verification job did not finish before timeout")


def test_frontend_health_and_instruction_catalogue():
    page = client.get("/")
    assert page.status_code == 200
    assert "RISC-V Verify" in page.text
    assert client.get("/api/health").json()["status"] == "ok"
    data = client.get("/api/instructions").json()
    assert data["supported_count"] == 19
    assert {item["mnemonic"] for item in data["instructions"]} >= {"ADD", "JALR", "LW", "BEQ"}


def test_run_results_summary_and_architectural_details():
    response = client.post("/api/run", json={"tests": 4, "seed": 314, "min_length": 5, "max_length": 8})
    assert response.status_code == 202
    started = response.json()
    job = wait_for_job(started["job_id"])
    assert job["status"] == "completed"
    assert job["summary"]["tests_run"] == 4
    assert job["summary"]["failed"] == 0
    assert job["progress"]["completed"] == 4

    summary = client.get("/api/summary").json()
    assert summary["last_seed"] == 314
    assert summary["summary"]["total_instructions_generated"] >= 20
    rows = client.get("/api/results?limit=10").json()["results"]
    assert len(rows) == 4
    assert all(item["status"] == "PASS" for item in rows)

    detail = client.get("/api/results/1").json()
    assert detail["status"] == "PASS"
    assert len(detail["expected"]["registers"]) == 32
    assert detail["expected"]["pc"] == detail["actual"]["pc"]
    assert detail["expected"]["memory"] == detail["actual"]["memory"]
    assert client.get("/api/coverage").json()["supported_instructions"] == 19
    report = client.get("/api/report")
    assert report.status_code == 200
    assert report.json()["summary"]["seed"] == 314
    assert client.get("/api/report/download").status_code == 200


def test_replay_returns_engine_program_and_architectural_state():
    response = client.post("/api/replay", json={"seed": 42, "test_id": 5, "min_length": 5, "max_length": 9})
    assert response.status_code == 200
    data = response.json()
    assert data["test_id"] == 5
    assert data["seed"] == 42
    assert data["status"] == "PASS"
    assert data["program"]
    assert data["expected"] == data["actual"]


def test_validation_errors_are_structured_and_bounded():
    response = client.post("/api/run", json={"tests": 0, "seed": -1})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    invalid_range = client.post("/api/run", json={"tests": 1, "seed": 3, "min_length": 9, "max_length": 2})
    assert invalid_range.status_code == 422
    assert invalid_range.json()["detail"]["code"] == "invalid_length_range"


def test_failure_details_use_structured_comparator_mismatches(monkeypatch):
    class FaultySimulator(Simulator):
        def step(self, program):
            super().step(program)
            if self.state.pc == 12:
                self.state.write(3, self.state.read(3) + 1)

    monkeypatch.setattr(routes, "Simulator", FaultySimulator)
    program = [
        Instruction(Mnemonic.ADDI, 1, 0, 0, 10),
        Instruction(Mnemonic.ADDI, 2, 0, 0, 20),
        Instruction(Mnemonic.ADD, 3, 1, 2),
    ]
    # The run endpoint stores actual generated programs; replace this one stored
    # program and inject the defect only for the selected-result detail request.
    job = routes.store.latest()
    if job is None:
        started = client.post("/api/run", json={"tests": 1, "seed": 6}).json()
        wait_for_job(started["job_id"])
        job = routes.store.latest()
    job["_programs"][1] = program
    job["results"][0]["mismatches"] = []
    response = client.get("/api/results/1")
    assert response.status_code == 200
    detail = response.json()
    assert detail["status"] == "FAIL"
    mismatch = detail["mismatches"][0]
    assert mismatch == {"kind": "register", "location": "x3", "expected": 30, "actual": 31}
    assert detail["instruction_causing_failure"] == "ADD x3, x1, x2"
