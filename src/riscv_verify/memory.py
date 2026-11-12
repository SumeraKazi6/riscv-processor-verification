"""Deterministic little-endian byte-addressable memory."""
from dataclasses import dataclass
from .exceptions import MemoryAccessError, MisalignedAccessError
from .isa import u32

@dataclass
class Memory:
    size: int = 4096
    data: bytearray | None = None
    def __post_init__(self):
        if self.size <= 0: raise ValueError("memory size must be positive")
        if self.data is None: self.data = bytearray(self.size)
        elif len(self.data) != self.size: raise ValueError("memory image size mismatch")
    def _check(self, address: int, width: int) -> None:
        if address % width: raise MisalignedAccessError(f"{width}-byte access at misaligned address 0x{address:x}")
        if address < 0 or address + width > self.size: raise MemoryAccessError(f"access [{address}, {address + width}) outside memory [0, {self.size})")
    def load_word(self, address: int) -> int:
        self._check(address, 4); return int.from_bytes(self.data[address:address+4], "little")
    def store_word(self, address: int, value: int) -> None:
        self._check(address, 4); self.data[address:address+4] = u32(value).to_bytes(4, "little")
    def clone(self) -> "Memory": return Memory(self.size, bytearray(self.data))
    def snapshot(self) -> bytes: return bytes(self.data)
