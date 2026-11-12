import random
from riscv_verify.comparator import compare_states
from riscv_verify.cpu import CPUState
from riscv_verify.generator import ProgramGenerator
from riscv_verify.reference_model import ReferenceModel
from riscv_verify.runner import VerificationRunner
from riscv_verify.simulator import Simulator
from riscv_verify.instruction import Instruction
from riscv_verify.isa import Mnemonic

def test_generated_programs_match_for_many_seeds():
    for seed in range(100):
        rng=random.Random(seed); program=ProgramGenerator(rng).generate(40)
        initial=CPUState(); initial.registers=[0]+[rng.getrandbits(32) for _ in range(31)]
        a=initial.clone(); e=initial.clone(); Simulator(a).run(program); ReferenceModel(e).execute_program(program)
        assert compare_states(e,a)==[], f"seed {seed}"

def test_runner_replay_is_deterministic_in_guided_mode():
    first=VerificationRunner(91,5,12,coverage_guided=True); first.run(15)
    expected=first.results[8].program
    replay=VerificationRunner(91,5,12,coverage_guided=True).replay(9)
    assert replay.program==expected

def test_comparator_detects_intentionally_faulty_add():
    program=[Instruction(Mnemonic.ADDI,1,0,0,10),Instruction(Mnemonic.ADDI,2,0,0,20),Instruction(Mnemonic.ADD,3,1,2)]
    expected=CPUState(); actual=CPUState()
    class FaultySimulator(Simulator):
        def step(self, code):
            super().step(code)
            if self.state.pc==12: self.state.write(3,self.state.read(3)+1)
    FaultySimulator(actual).run(program); ReferenceModel(expected).execute_program(program)
    errors=compare_states(expected,actual)
    assert any(e.kind=="register" and e.location=="x3" and e.expected==30 and e.actual==31 for e in errors)

def test_coverage_occurrence_vs_instruction_coverage():
    runner=VerificationRunner(4,20,20); result=runner.run(2)
    cov=result["coverage"]
    assert sum(cov["occurrence_counts"].values())==result["total_instructions_executed"]
    assert 0 <= cov["instruction_coverage_percent"] <= 100
