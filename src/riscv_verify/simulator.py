"""Procedural RV32I subset simulator."""
import logging
from .cpu import CPUState
from .exceptions import ProgramCounterError
from .instruction import Instruction
from .isa import I_ARITH, R_TYPE, Mnemonic, signed32, u32

class Simulator:
    def __init__(self, state: CPUState | None = None): self.state = state or CPUState()
    def reset(self, state: CPUState | None = None): self.state = state.clone() if state else CPUState()
    def step(self, program: list[Instruction]) -> None:
        pc = self.state.pc
        if pc % 4 or pc < 0 or pc >= len(program) * 4: raise ProgramCounterError(f"PC 0x{pc:x} is outside executable program")
        ins = program[pc // 4]; a = self.state.read(ins.rs1); b = self.state.read(ins.rs2); m = ins.mnemonic
        logging.getLogger(__name__).debug("SIM pc=0x%08x %s", pc, ins)
        next_pc = pc + 4; result = None
        if m == Mnemonic.ADD: result = a + b
        elif m == Mnemonic.SUB: result = a - b
        elif m == Mnemonic.AND: result = a & b
        elif m == Mnemonic.OR: result = a | b
        elif m == Mnemonic.XOR: result = a ^ b
        elif m == Mnemonic.SLT: result = int(signed32(a) < signed32(b))
        elif m == Mnemonic.ADDI: result = a + ins.immediate
        elif m == Mnemonic.ANDI: result = a & u32(ins.immediate)
        elif m == Mnemonic.ORI: result = a | u32(ins.immediate)
        elif m == Mnemonic.XORI: result = a ^ u32(ins.immediate)
        elif m == Mnemonic.SLTI: result = int(signed32(a) < ins.immediate)
        elif m == Mnemonic.LW: result = self.state.memory.load_word(u32(a + ins.immediate))
        elif m == Mnemonic.SW: self.state.memory.store_word(u32(a + ins.immediate), self.state.read(ins.rs2))
        elif m == Mnemonic.BEQ:
            if a == b: next_pc = pc + ins.immediate
        elif m == Mnemonic.BNE:
            if a != b: next_pc = pc + ins.immediate
        elif m == Mnemonic.LUI: result = ins.immediate << 12
        elif m == Mnemonic.AUIPC: result = pc + (ins.immediate << 12)
        elif m == Mnemonic.JAL: result = pc + 4; next_pc = pc + ins.immediate
        elif m == Mnemonic.JALR: result = pc + 4; next_pc = (a + ins.immediate) & ~1
        else: raise ValueError(f"unsupported instruction {m}")
        if result is not None: self.state.write(ins.rd, result)
        self.state.pc = u32(next_pc)
        self.state.registers[0] = 0
        if m not in {Mnemonic.SW, Mnemonic.BEQ, Mnemonic.BNE}:
            logging.getLogger(__name__).debug("SIM %s = 0x%08x", f"x{ins.rd}", self.state.read(ins.rd))
    def run(self, program: list[Instruction], max_steps: int | None = None, on_step=None) -> int:
        """Execute until PC reaches the byte immediately after the program."""
        end = len(program) * 4; limit = max_steps if max_steps is not None else max(1, len(program) * 100)
        executed = 0
        while self.state.pc != end:
            if executed >= limit: raise ProgramCounterError(f"execution exceeded step limit {limit} (possible control-flow loop)")
            if on_step is not None: on_step(program[self.state.pc // 4], self.state)
            self.step(program); executed += 1
        return executed
