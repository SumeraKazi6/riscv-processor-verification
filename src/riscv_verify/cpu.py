"""Architectural state shared as a data container, not as an execution engine."""
from dataclasses import dataclass, field
from .memory import Memory
from .isa import u32

@dataclass
class CPUState:
    registers: list[int] = field(default_factory=lambda: [0] * 32)
    pc: int = 0
    memory: Memory = field(default_factory=Memory)
    def __post_init__(self):
        if len(self.registers) != 32: raise ValueError("register file must contain 32 registers")
        self.registers = [u32(v) for v in self.registers]; self.registers[0] = 0; self.pc = u32(self.pc)
    def read(self, index: int) -> int:
        if not 0 <= index < 32: raise IndexError(f"invalid register x{index}")
        return 0 if index == 0 else self.registers[index]
    def write(self, index: int, value: int) -> None:
        if not 0 <= index < 32: raise IndexError(f"invalid register x{index}")
        if index: self.registers[index] = u32(value)
        self.registers[0] = 0
    def clone(self) -> "CPUState": return CPUState(self.registers.copy(), self.pc, self.memory.clone())
