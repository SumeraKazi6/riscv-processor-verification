"""Instruction, category, register and memory access coverage counters."""
from collections import Counter
from .isa import I_ARITH, R_TYPE, Mnemonic, SUPPORTED

class Coverage:
    def __init__(self):
        self.counts=Counter(); self.registers=Counter(); self.loads=0; self.stores=0; self.addresses=set(); self.aligned=0
    def record(self, instruction, state_before=None):
        m=instruction.mnemonic; self.counts[m.value]+=1
        for reg in (instruction.rd, instruction.rs1, instruction.rs2): self.registers[reg]+=1
        if m == Mnemonic.LW or m == Mnemonic.SW:
            if state_before is not None:
                addr=(state_before.read(instruction.rs1)+instruction.immediate)&0xffffffff
                self.addresses.add(addr); self.aligned += addr % 4 == 0
            if m == Mnemonic.LW: self.loads+=1
            else: self.stores+=1
    @property
    def covered(self): return sum(self.counts[m.value] > 0 for m in SUPPORTED)
    @property
    def percentage(self): return 100.0*self.covered/len(SUPPORTED)
    def report(self):
        categories={"R-type":R_TYPE,"I-type":I_ARITH,"memory":{Mnemonic.LW,Mnemonic.SW},"branch":{Mnemonic.BEQ,Mnemonic.BNE},"upper":{Mnemonic.LUI,Mnemonic.AUIPC},"jump":{Mnemonic.JAL,Mnemonic.JALR}}
        return {"supported_instructions":len(SUPPORTED),"covered_instructions":self.covered,"instruction_coverage_percent":self.percentage,"occurrence_counts":{m.value:self.counts[m.value] for m in SUPPORTED},"categories":{name:{"covered":sum(self.counts[x.value]>0 for x in group),"total":len(group)} for name,group in categories.items()},"registers_used":sorted(self.registers),"memory":{"loads":self.loads,"stores":self.stores,"unique_addresses":len(self.addresses),"aligned_accesses":self.aligned}}
