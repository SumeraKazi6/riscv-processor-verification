"""Seeded constrained-random program generation."""
import random
from .instruction import Instruction
from .isa import I_ARITH, R_TYPE, Mnemonic, SUPPORTED

class ProgramGenerator:
    def __init__(self, rng: random.Random, memory_size: int = 4096): self.rng=rng; self.memory_size=memory_size
    def generate(self, length: int, coverage_counts=None, coverage_guided=False) -> list[Instruction]:
        if length < 1: raise ValueError("program length must be positive")
        weights=[]
        for m in SUPPORTED:
            count=(coverage_counts or {}).get(m.value,0)
            weights.append(1.0/(1.0+count) if coverage_guided else 1.0)
        program=[]
        for index in range(length):
            # Control-flow instructions occur only at slot zero; their targets are
            # forward and aligned, keeping generated programs finite and replayable.
            choices=list(SUPPORTED)
            if index != 0: choices=[m for m in choices if m not in {Mnemonic.BEQ,Mnemonic.BNE,Mnemonic.JAL,Mnemonic.JALR}]
            if index == length-1: choices=[m for m in choices if m not in {Mnemonic.BEQ,Mnemonic.BNE,Mnemonic.JAL,Mnemonic.JALR}]
            selected=self.rng.choices(choices, weights=[weights[SUPPORTED.index(m)] for m in choices], k=1)[0]
            rd=self.rng.randrange(1,32) if self.rng.random()<0.85 else 0
            r1=self.rng.randrange(32); r2=self.rng.randrange(32); imm=0
            if selected in R_TYPE: pass
            elif selected in I_ARITH: imm=self.rng.randint(-2048,2047)
            elif selected in {Mnemonic.LW,Mnemonic.SW}:
                # x0-relative addresses stay inside the deterministic memory image.
                r1=0; imm=self.rng.randrange(0,min(self.memory_size,2048),4)
            elif selected in {Mnemonic.BEQ,Mnemonic.BNE}:
                imm=self.rng.randrange(1,max(2,length))*4
            elif selected == Mnemonic.LUI: imm=self.rng.randrange(1<<20)
            elif selected == Mnemonic.AUIPC: imm=self.rng.randrange(-(1<<19),1<<20)
            elif selected == Mnemonic.JAL: imm=self.rng.randrange(1,max(2,length))*4
            elif selected == Mnemonic.JALR: r1=0; imm=4
            program.append(Instruction(selected,rd,r1,r2,imm))
        return program
