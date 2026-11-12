import pytest
from riscv_verify.cpu import CPUState
from riscv_verify.exceptions import MemoryAccessError, MisalignedAccessError, InvalidInstructionError
from riscv_verify.instruction import Instruction
from riscv_verify.isa import Mnemonic
from riscv_verify.memory import Memory
from riscv_verify.simulator import Simulator

def ins(m, rd=0, rs1=0, rs2=0, imm=0): return Instruction(m,rd,rs1,rs2,imm)

def test_register_zero_and_wraparound():
    s=CPUState(); s.write(0,99); assert s.read(0)==0
    s.write(1,0xffffffff); s.write(2,1)
    Simulator(s).run([ins(Mnemonic.ADD,3,1,2),ins(Mnemonic.ADDI,0,3,0,4)])
    assert s.read(3)==0 and s.read(0)==0

@pytest.mark.parametrize("m,a,b,want",[(Mnemonic.ADD,8,5,13),(Mnemonic.SUB,8,5,3),(Mnemonic.AND,12,10,8),(Mnemonic.OR,12,10,14),(Mnemonic.XOR,12,10,6),(Mnemonic.SLT,0xffffffff,1,1)])
def test_r_type(m,a,b,want):
    s=CPUState(); s.write(1,a); s.write(2,b); Simulator(s).run([ins(m,3,1,2)]); assert s.read(3)==want

@pytest.mark.parametrize("m,imm,want",[(Mnemonic.ADDI,-1,6),(Mnemonic.ANDI,-1,7),(Mnemonic.ORI,8,15),(Mnemonic.XORI,3,4),(Mnemonic.SLTI,0,1)])
def test_i_type(m,imm,want):
    s=CPUState(); s.write(1,0xffffffff if m==Mnemonic.SLTI else 7); Simulator(s).run([ins(m,2,1,0,imm)]); assert s.read(2)==want

def test_lw_sw_little_endian_and_x0():
    s=CPUState(); s.write(1,0x12345678)
    Simulator(s).run([ins(Mnemonic.SW,0,0,1,8),ins(Mnemonic.LW,2,0,0,8),ins(Mnemonic.LW,0,0,0,8)])
    assert s.read(2)==0x12345678 and s.read(0)==0
    assert s.memory.data[8:12]==bytes.fromhex("78563412")

@pytest.mark.parametrize("address,exc",[(1,MisalignedAccessError),(4096,MemoryAccessError),(-4,MemoryAccessError)])
def test_memory_errors(address,exc):
    with pytest.raises(exc): Memory().load_word(address)

def test_control_flow_and_upper_instructions():
    # Set x1=5, branch over the wrong-path ADDI, then exercise link and AUIPC.
    p=[ins(Mnemonic.ADDI,1,0,0,5),ins(Mnemonic.BEQ,0,1,1,8),ins(Mnemonic.ADDI,2,0,0,99),ins(Mnemonic.LUI,3,0,0,1),ins(Mnemonic.AUIPC,4,0,0,1),ins(Mnemonic.JAL,5,0,0,8),ins(Mnemonic.ADDI,6,0,0,99),ins(Mnemonic.ADDI,7,0,0,7)]
    s=CPUState(); Simulator(s).run(p)
    assert s.read(2)==0 and s.read(3)==4096 and s.read(4)==4112 and s.read(5)==24 and s.read(7)==7

def test_jalr_clears_low_bit():
    s=CPUState(); s.write(1,8)
    Simulator(s).run([ins(Mnemonic.JALR,2,1,0,1),ins(Mnemonic.ADDI,3,0,0,30),ins(Mnemonic.ADDI,4,0,0,40)])
    assert s.pc==12 and s.read(2)==4 and s.read(3)==0 and s.read(4)==40

def test_bne_taken_and_not_taken():
    # Taken BNE skips the first body instruction; equal values fall through.
    s=CPUState(); s.write(1,5); s.write(2,6)
    Simulator(s).run([ins(Mnemonic.BNE,0,1,2,8),ins(Mnemonic.ADDI,3,0,0,90),ins(Mnemonic.ADDI,4,0,0,7)])
    assert s.read(3)==0 and s.read(4)==7
    t=CPUState(); t.write(1,5); t.write(2,5)
    Simulator(t).run([ins(Mnemonic.BNE,0,1,2,8),ins(Mnemonic.ADDI,3,0,0,90),ins(Mnemonic.ADDI,4,0,0,7)])
    assert t.read(3)==90 and t.read(4)==7

def test_reset_restores_state():
    state=CPUState(); state.write(3,123); state.pc=8
    sim=Simulator(state); sim.reset()
    assert sim.state.read(3)==0 and sim.state.pc==0

def test_invalid_instruction_fields():
    with pytest.raises(InvalidInstructionError): Instruction(Mnemonic.ADD,32)
    with pytest.raises(InvalidInstructionError): Instruction(Mnemonic.ADDI,1,1,0,2048)
    with pytest.raises(InvalidInstructionError): Instruction(Mnemonic.BEQ,1,2,3,3)
