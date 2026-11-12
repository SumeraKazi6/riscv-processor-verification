"""Independent architectural oracle using a separate, table-free implementation."""
from .cpu import CPUState
from .exceptions import ProgramCounterError
from .instruction import Instruction
from .isa import Mnemonic

class ReferenceModel:
    def __init__(self, state: CPUState | None = None): self.state = state or CPUState()
    def execute_program(self, code: list[Instruction], max_steps: int | None = None) -> int:
        """Interpret instructions independently from Simulator.step."""
        stop = 4 * len(code); count = 0; budget = max_steps if max_steps is not None else max(1, len(code) * 100)
        while self.state.pc != stop:
            address = self.state.pc
            if address % 4 or address < 0 or address >= stop: raise ProgramCounterError(f"reference PC 0x{address:x} outside program")
            if count >= budget: raise ProgramCounterError("reference execution step limit exceeded")
            op = code[address >> 2]; r = self.state.registers
            left = 0 if op.rs1 == 0 else r[op.rs1]
            right = 0 if op.rs2 == 0 else r[op.rs2]
            following = address + 4; value = None
            if op.mnemonic == Mnemonic.ADD: value = left + right
            elif op.mnemonic == Mnemonic.SUB: value = left + (~right + 1)
            elif op.mnemonic == Mnemonic.AND: value = left & right
            elif op.mnemonic == Mnemonic.OR: value = left | right
            elif op.mnemonic == Mnemonic.XOR: value = left ^ right
            elif op.mnemonic == Mnemonic.SLT:
                lhs = left if left < 0x80000000 else left - 0x100000000
                rhs = right if right < 0x80000000 else right - 0x100000000
                value = 1 if lhs < rhs else 0
            elif op.mnemonic == Mnemonic.ADDI: value = left + op.immediate
            elif op.mnemonic == Mnemonic.ANDI: value = left & (op.immediate & 0xffffffff)
            elif op.mnemonic == Mnemonic.ORI: value = left | (op.immediate & 0xffffffff)
            elif op.mnemonic == Mnemonic.XORI: value = left ^ (op.immediate & 0xffffffff)
            elif op.mnemonic == Mnemonic.SLTI:
                lhs = left if left < 0x80000000 else left - 0x100000000
                value = int(lhs < op.immediate)
            elif op.mnemonic == Mnemonic.LW:
                loc = (left + op.immediate) & 0xffffffff; value = self.state.memory.load_word(loc)
            elif op.mnemonic == Mnemonic.SW:
                loc = (left + op.immediate) & 0xffffffff; payload = 0 if op.rs2 == 0 else r[op.rs2]; self.state.memory.store_word(loc, payload)
            elif op.mnemonic == Mnemonic.BEQ:
                if left == right: following = address + op.immediate
            elif op.mnemonic == Mnemonic.BNE:
                if left != right: following = address + op.immediate
            elif op.mnemonic == Mnemonic.LUI: value = op.immediate * 4096
            elif op.mnemonic == Mnemonic.AUIPC: value = address + op.immediate * 4096
            elif op.mnemonic == Mnemonic.JAL: value, following = address + 4, address + op.immediate
            elif op.mnemonic == Mnemonic.JALR: value, following = address + 4, (left + op.immediate) & 0xfffffffe
            else: raise ValueError(f"oracle does not implement {op.mnemonic}")
            if value is not None and op.rd != 0: r[op.rd] = value & 0xffffffff
            r[0] = 0; self.state.pc = following & 0xffffffff; count += 1
        return count
