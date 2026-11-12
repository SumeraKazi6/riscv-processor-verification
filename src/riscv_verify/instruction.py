"""Typed decoded instruction representation and readable assembly format."""
from dataclasses import dataclass
from .isa import I_ARITH, Mnemonic, R_TYPE
from .exceptions import InvalidInstructionError

@dataclass(frozen=True, slots=True)
class Instruction:
    mnemonic: Mnemonic
    rd: int = 0
    rs1: int = 0
    rs2: int = 0
    immediate: int = 0

    def __post_init__(self):
        try: object.__setattr__(self, "mnemonic", Mnemonic(self.mnemonic))
        except ValueError as exc: raise InvalidInstructionError(f"Unsupported mnemonic: {self.mnemonic}") from exc
        for name in ("rd", "rs1", "rs2"):
            value = getattr(self, name)
            if not isinstance(value, int) or not 0 <= value < 32:
                raise InvalidInstructionError(f"{name} must be in [0, 31], got {value!r}")
        m = self.mnemonic
        if m in R_TYPE and not -2048 <= self.immediate <= 2047: # immediate is unused; normalize not required
            raise InvalidInstructionError("unused immediate must be a signed 12-bit value")
        if m in I_ARITH or m in {Mnemonic.LW, Mnemonic.SW, Mnemonic.JALR}:
            if not -2048 <= self.immediate <= 2047: raise InvalidInstructionError(f"{m.value} immediate must fit signed 12 bits")
        if m in {Mnemonic.BEQ, Mnemonic.BNE}:
            if self.immediate % 2 or not -4096 <= self.immediate <= 4094: raise InvalidInstructionError("branch offset must be even and fit signed 13 bits")
        if m == Mnemonic.JAL and (self.immediate % 2 or not -(1<<20) <= self.immediate <= (1<<20)-2):
            raise InvalidInstructionError("JAL offset must be even and fit signed 21 bits")
        if m == Mnemonic.LUI and not 0 <= self.immediate <= 0xFFFFF: raise InvalidInstructionError("LUI immediate must be 20-bit unsigned")
        if m == Mnemonic.AUIPC and not -(1<<19) <= self.immediate < (1<<20): raise InvalidInstructionError("AUIPC immediate must fit 20 bits")

    def __str__(self) -> str:
        m = self.mnemonic.value
        if self.mnemonic in R_TYPE: return f"{m} x{self.rd}, x{self.rs1}, x{self.rs2}"
        if self.mnemonic in I_ARITH: return f"{m} x{self.rd}, x{self.rs1}, {self.immediate}"
        if self.mnemonic == Mnemonic.LW: return f"LW x{self.rd}, {self.immediate}(x{self.rs1})"
        if self.mnemonic == Mnemonic.SW: return f"SW x{self.rs2}, {self.immediate}(x{self.rs1})"
        if self.mnemonic in {Mnemonic.BEQ, Mnemonic.BNE}: return f"{m} x{self.rs1}, x{self.rs2}, {self.immediate}"
        if self.mnemonic in {Mnemonic.LUI, Mnemonic.AUIPC}:
            immediate = f"-0x{-self.immediate:x}" if self.immediate < 0 else f"0x{self.immediate:x}"
            return f"{m} x{self.rd}, {immediate}"
        if self.mnemonic == Mnemonic.JAL: return f"JAL x{self.rd}, {self.immediate}"
        return f"JALR x{self.rd}, {self.immediate}(x{self.rs1})"
