"""Architectural state comparison with structured mismatch records."""
from dataclasses import asdict, dataclass
from .cpu import CPUState

@dataclass(frozen=True)
class Mismatch:
    kind: str
    location: str
    expected: int | str
    actual: int | str
    def to_dict(self): return asdict(self)

def compare_states(expected: CPUState, actual: CPUState) -> list[Mismatch]:
    errors=[]
    for i,(want,got) in enumerate(zip(expected.registers, actual.registers)):
        if want != got: errors.append(Mismatch("register", f"x{i}", want, got))
    if expected.pc != actual.pc: errors.append(Mismatch("pc", "pc", expected.pc, actual.pc))
    if expected.memory.size != actual.memory.size: errors.append(Mismatch("memory", "size", expected.memory.size, actual.memory.size))
    else:
        for i,(want,got) in enumerate(zip(expected.memory.data, actual.memory.data)):
            if want != got: errors.append(Mismatch("memory", f"0x{i:08x}", want, got))
    return errors
