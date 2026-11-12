"""Small hand-authored program that stores and reloads an arithmetic result."""
from riscv_verify.instruction import Instruction
from riscv_verify.isa import Mnemonic
from riscv_verify.runner import initial_state
from riscv_verify.simulator import Simulator

program=[
    Instruction(Mnemonic.ADDI,1,0,0,10),
    Instruction(Mnemonic.ADDI,2,0,0,20),
    Instruction(Mnemonic.ADD,3,1,2),
    Instruction(Mnemonic.SW,0,0,3,0),
    Instruction(Mnemonic.LW,4,0,0,0),
]
state=initial_state(1); Simulator(state).run(program)
print(f"x3={state.read(3)}, x4={state.read(4)}, memory[0]={state.memory.load_word(0)}")
