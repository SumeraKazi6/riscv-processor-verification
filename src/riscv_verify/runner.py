"""Seeded differential test orchestration."""
from dataclasses import dataclass
import random
import time
import logging
from .comparator import compare_states
from .coverage import Coverage
from .cpu import CPUState
from .generator import ProgramGenerator
from .memory import Memory
from .reference_model import ReferenceModel
from .simulator import Simulator

@dataclass
class TestResult:
    test_id: int
    seed: int
    program: list
    passed: bool
    mismatches: list
    instructions_executed: int

def initial_state(seed: int, memory_size=4096) -> CPUState:
    rng=random.Random(seed ^ 0x5EED5EED)
    regs=[0]+[rng.getrandbits(32) for _ in range(31)]
    return CPUState(regs,0,Memory(memory_size))

class VerificationRunner:
    def __init__(self, seed: int, min_length=8, max_length=32, memory_size=4096, coverage_guided=False):
        if min_length < 1 or max_length < min_length: raise ValueError("require 1 <= min_length <= max_length")
        self.seed=seed; self.min_length=min_length; self.max_length=max_length; self.memory_size=memory_size
        self.coverage_guided=coverage_guided; self.coverage=Coverage(); self.results=[]; self.total_instructions=0
    def run_one(self, test_id: int, program=None) -> TestResult:
        rng=random.Random(self.seed+test_id)
        if program is None:
            length=rng.randint(self.min_length,self.max_length)
            program=ProgramGenerator(rng,self.memory_size).generate(length,self.coverage.counts,self.coverage_guided)
        logging.getLogger(__name__).debug("Generated test %d (%d instructions)",test_id,len(program))
        state=initial_state(self.seed+test_id,self.memory_size)
        actual=state.clone(); expected=state.clone()
        try:
            executed=Simulator(actual).run(program,on_step=self.coverage.record)
            ref_executed=ReferenceModel(expected).execute_program(program)
            mismatches=compare_states(expected,actual)
            if executed != ref_executed: mismatches.append({"kind":"execution_count","location":"count","expected":ref_executed,"actual":executed})
        except Exception as exc:
            # A generated program error is a test failure; preserve enough context for diagnosis.
            executed=0; mismatches=[{"kind":"execution_error","location":"program","expected":"successful execution","actual":f"{type(exc).__name__}: {exc}"}]
        result=TestResult(test_id,self.seed,program,not mismatches,mismatches,executed)
        self.results.append(result); self.total_instructions += executed
        logging.getLogger(__name__).debug("Test %d %s (%d instructions executed)",test_id,"PASS" if result.passed else "FAIL",executed)
        return result
    def run(self, tests: int, stop_on_failure=False):
        if tests < 1: raise ValueError("tests must be positive")
        start=time.perf_counter()
        for test_id in range(1,tests+1):
            result=self.run_one(test_id)
            if stop_on_failure and not result.passed: break
        return {"seed":self.seed,"tests_requested":tests,"tests_run":len(self.results),"passed":sum(r.passed for r in self.results),"failed":sum(not r.passed for r in self.results),"total_instructions_generated":sum(len(r.program) for r in self.results),"total_instructions_executed":self.total_instructions,"elapsed_seconds":time.perf_counter()-start,"coverage":self.coverage.report(),"failures":self.results_to_json([r for r in self.results if not r.passed])}
    @staticmethod
    def results_to_json(results):
        return [{"test_id":r.test_id,"seed":r.seed,"program":[str(i) for i in r.program],"mismatches":[m.to_dict() if hasattr(m,"to_dict") else m for m in r.mismatches]} for r in results]
    def replay(self, test_id: int):
        if test_id < 1: raise ValueError("test-id is one-based and must be positive")
        # Rebuild the coverage history so coverage-guided generation follows the
        # exact same probability weights as the original run.
        for index in range(1,test_id+1):
            rng=random.Random(self.seed+index); length=rng.randint(self.min_length,self.max_length)
            program=ProgramGenerator(rng,self.memory_size).generate(length,self.coverage.counts,self.coverage_guided)
            result=self.run_one(index,program)
        return result
