"""Supported instruction set and architectural constants."""
from enum import Enum

XLEN = 32
MASK32 = (1 << XLEN) - 1
REGISTER_COUNT = 32
INSTRUCTION_BYTES = 4

class Mnemonic(str, Enum):
    ADD="ADD"; SUB="SUB"; AND="AND"; OR="OR"; XOR="XOR"; SLT="SLT"
    ADDI="ADDI"; ANDI="ANDI"; ORI="ORI"; XORI="XORI"; SLTI="SLTI"
    LW="LW"; SW="SW"; BEQ="BEQ"; BNE="BNE"; LUI="LUI"; AUIPC="AUIPC"
    JAL="JAL"; JALR="JALR"

R_TYPE = frozenset({Mnemonic.ADD, Mnemonic.SUB, Mnemonic.AND, Mnemonic.OR, Mnemonic.XOR, Mnemonic.SLT})
I_ARITH = frozenset({Mnemonic.ADDI, Mnemonic.ANDI, Mnemonic.ORI, Mnemonic.XORI, Mnemonic.SLTI})
SUPPORTED = tuple(Mnemonic)

def signed32(value: int) -> int:
    value &= MASK32
    return value - (1 << 32) if value & (1 << 31) else value

def u32(value: int) -> int:
    return value & MASK32
