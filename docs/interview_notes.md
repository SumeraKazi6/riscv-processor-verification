# Interview notes

## Project pitch

This project is a Python educational verification framework for a deliberately defined RV32I instruction subset. It executes seeded random instruction programs on a procedural simulator and a separately written architectural interpreter, then compares every register, the program counter, and all bytes of memory. It reports instruction occurrence and instruction coverage and can reconstruct a test from its seed, test ID, and generation settings.

## Key design choices

- **Problem:** implementation mistakes can corrupt data or control flow while simple examples still pass. Differential execution checks many combinations against an independently coded expected-behavior model.
- **Why RISC-V:** its open, regular instruction formats make a compact subset understandable and explainable without relying on proprietary ISA details.
- **Random tests:** constrained random programs explore combinations humans may not think to write. They complement directed unit tests; they do not prove correctness.
- **Reference model:** `Simulator` and `ReferenceModel` have separate execution code and integer interpretations. They share only state containers, decoded instruction values, and memory's specified interface. Shared bugs remain possible, so directed tests and independent review matter.
- **Differential testing:** run the same program from cloned initial states, then structurally compare register values, PC, and memory contents.
- **Coverage:** occurrence counts how many times an instruction ran. Instruction coverage counts supported mnemonics seen at least once divided by all 19 supported mnemonics. Category counts are also reported.
- **Seeds:** master seed plus one-based test ID derive independent test randomness. Coverage-guided replay regenerates preceding tests to rebuild the same coverage history and instruction weights. Reuse run length bounds, memory size, and guided-mode option.
- **Mismatch localization:** the comparator returns typed entries such as register `x5`, PC, or byte address, with expected and actual values. Reports include the generated program.
- **Memory:** 4096-byte default bytearray, little-endian 32-bit words, aligned word accesses only, and explicit bounds checks.
- **Branches:** BEQ/BNE compare 32-bit register bit patterns and add a signed byte offset to the current PC when taken. JAL/JALR save PC+4; JALR clears target bit 0. Generated control flow is limited to one forward control instruction at the first slot to keep random programs finite.
- **x0:** read always yields zero; writes are discarded. State repairs x0 after execution as an invariant.

## Bugs it can find

Wrong arithmetic, signed comparisons, immediate sign handling, wraparound, destination-register selection, x0 writes, load/store endianness or address calculations, branch decisions/PC offsets, jump link values, and some state corruption. The included faulty-simulator test deliberately changes ADD's output from 30 to 31 and asserts that the comparator identifies x3.

## Limitations and next steps

The toolkit is not a complete RV32I implementation or compliance suite: it has no binary decoder, pipeline, exceptions/traps, CSR, privilege modes, MMIO, byte/halfword loads, ELF loader, or hardware execution. Generated jumps are forward-constrained. The current runner compares final architectural state, not every intermediate retirement state. Future improvements could add instruction encoding/decoding, directed corner-case suites, shrinking, per-step trace comparison, a richer coverage model, and an RTL co-simulation adapter.

## Likely interviewer questions and answers

1. **What does this project verify?** A defined set of RV32I-like architectural semantics, by differential execution of generated programs.
2. **Is this formal verification?** No. It is simulation-based randomized and directed testing.
3. **Why a reference model?** It supplies expected architectural results without requiring a second hardware implementation.
4. **How is independence maintained?** The simulator uses a procedural dispatch and helpers such as `signed32`; the oracle uses a separate interpreter, explicit signed conversions, and separate state updates.
5. **Can independent models share a bug?** Yes. Directed tests, spec review, and additional independent tools reduce that risk.
6. **What is differential testing?** Executing equivalent inputs in two implementations and comparing observable outputs.
7. **What state is compared?** All 32 registers, PC, memory size, and each memory byte.
8. **How is x0 enforced?** Reads return zero and writes to index zero are discarded.
9. **How is overflow handled?** Results are masked to 32 bits at architectural write boundaries.
10. **How is SLT signed?** Each 32-bit pattern is interpreted in two's-complement signed form before comparison.
11. **How do immediates work?** The instruction stores decoded signed integers for signed 12-bit operations; bitwise operations mask the immediate to 32 bits.
12. **How is memory represented?** A bytearray with checked, aligned 32-bit little-endian accesses.
13. **What happens on misalignment?** A specific `MisalignedAccessError` is raised; it is not silently rounded.
14. **How does BEQ update PC?** A taken branch adds its byte displacement to the current instruction PC; otherwise PC advances four bytes.
15. **What does JAL write?** PC+4 to `rd`, then jumps by its signed byte displacement.
16. **What is JALR's special rule?** Its target is `(rs1 + imm) & ~1`, and it writes PC+4.
17. **Why use byte offsets with a 4-byte instruction width?** It follows the architectural PC/address convention even though this subset has no compressed instructions.
18. **How is randomness reproducible?** Each program uses a `random.Random` derived from master seed and test ID; settings are part of replay configuration.
19. **Why constrain control flow?** It keeps random programs bounded and easier to replay while still exercising branch/jump semantics.
20. **Does coverage mean correctness?** No. It only measures whether supported mnemonics executed and how often.
21. **Occurrence versus coverage?** Occurrence is execution count; coverage is whether an instruction was seen at least once.
22. **How does guided generation work?** It weights each mnemonic inversely with prior occurrence count, a simple probability adjustment.
23. **What if a mismatch occurs?** The run records the test ID, seed, program, and structured state differences; the test is replayable.
24. **Why compare memory byte by byte?** It detects partial corruption and makes mismatches precise, even though current operations move words.
25. **Why clone the initial state?** Both implementations must start from identical registers, PC, and memory.
26. **Why not compare after every instruction?** This version keeps the runner simple and fast; final-state comparison can miss transient divergences that later cancel.
27. **How would you improve bug localization?** Compare retirement snapshots after each instruction and report the first divergence.
28. **What does the intentional fault test show?** The comparator detects a real altered result; it does not prove every bug is detectable.
29. **Why Python?** It makes the model and test strategy readable, fast to iterate on, and dependency-light for a portfolio project.
30. **Could this verify RTL?** With an adapter that feeds identical programs/states and extracts architectural state, it could compare an RTL DUT; no such adapter is included.
31. **Does it decode machine code?** No, it operates on structured instruction objects.
32. **What is the address range?** The default memory spans byte addresses 0 through 4095.
33. **How are invalid PC values handled?** Misaligned or out-of-program execution raises `ProgramCounterError`; the exact end PC terminates normally.
34. **What are the main blind spots?** Missing instructions and system behavior, limited control-flow generation, no intermediate trace comparison, and potential common-mode model errors.
35. **What would you add first?** Per-step comparison and program shrinking, because they make failures easier to isolate and explain.

## Web frontend architecture

The frontend is a static HTML/CSS/vanilla-JavaScript dashboard served by FastAPI from the same origin. JavaScript sends JSON requests and polls job status; FastAPI validates inputs and calls the existing `VerificationRunner`, coverage tracker, simulator/reference model, comparator, and JSON report writer. The interface displays only API results. It has no hardcoded sample metrics and no alternate verification implementation. Jobs are kept in memory for the lifetime of the local server, while each completed web run also writes a JSON report beneath `reports/`.

### Frontend interview questions and answers

1. **Why add a frontend?** It makes run configuration, progress, coverage, failures, replay, and reports easier to inspect than terminal output alone.
2. **How does the frontend communicate with Python?** It uses `fetch()` to call JSON REST endpoints exposed by FastAPI.
3. **Why FastAPI?** It provides typed request validation, concise route definitions, generated API docs, and integrates naturally with Python code.
4. **Why a REST API?** It creates a clear interface between presentation and verification and can serve both the dashboard and other clients.
5. **How do dashboard metrics stay real?** They are fetched from the latest completed job produced by `VerificationRunner`; JavaScript only formats returned values.
6. **How is a failed test displayed?** The API returns the comparator's structured mismatch kind, location, expected value, and actual value; the details view also shows program and state.
7. **How does the frontend start random tests?** It posts validated options to `/api/run`; the job worker invokes `runner.run_one()` for each test.
8. **How does replay work?** The API calls `VerificationRunner.replay()` with the provided seed, one-based ID, lengths, and coverage-guided option.
9. **How was the verification logic protected?** No instruction semantics or generator logic were copied into JavaScript; the web app calls the existing Python engine.
10. **How is presentation separated from verification?** FastAPI is an adapter and job boundary, while the simulator, reference model, comparator, generator, and coverage modules remain the engine. The browser only renders API responses.
11. **How does progress work?** The job worker updates its completed count after every actual generated test; the browser polls that count while work is running.
12. **Why not persist jobs in a database?** This is a local portfolio application; an in-memory registry and JSON reports meet the current needs without adding infrastructure.
13. **Can the UI run multiple jobs simultaneously?** The local API intentionally accepts one campaign at a time to keep CPU and memory use predictable.
14. **How are architectural details generated?** The API reruns the selected retained instruction objects through the simulator and oracle from the same seeded initial state and returns their compared state.
15. **What is the frontend's main limitation?** Job history is process-local and disappears on restart; generated JSON report files remain on disk.
16. **How is CORS configured?** The app is served same-origin; optional development origins are explicitly limited to localhost port 5500.
17. **How are requests secured?** Pydantic bounds numeric inputs, no user code or shell commands are accepted, and internal exceptions are returned without traces.
18. **How are charts implemented?** Small CSS conic gradients and bars use values from the API, avoiding a browser chart dependency.
