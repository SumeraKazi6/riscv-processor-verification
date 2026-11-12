"""Command-line interface for random differential verification."""
import argparse
import json
import logging
import random
from . import __version__
from .coverage import Coverage
from .generator import ProgramGenerator
from .reporting import print_summary, write_json
from .runner import VerificationRunner

def parser():
    root=argparse.ArgumentParser(prog="riscv-verify",description="Verify a defined RV32I subset by seeded differential testing")
    sub=root.add_subparsers(dest="command",required=True)
    run=sub.add_parser("run",help="run randomized differential tests")
    run.add_argument("--tests",type=int,default=100); run.add_argument("--seed",type=int,default=None)
    run.add_argument("--min-length",type=int,default=8); run.add_argument("--max-length",type=int,default=32)
    run.add_argument("--memory-size",type=int,default=4096); run.add_argument("--coverage-guided",action="store_true")
    run.add_argument("--stop-on-failure",action="store_true"); run.add_argument("--json",dest="json_path",default="reports/results.json")
    run.add_argument("--verbose",action="store_true")
    replay=sub.add_parser("replay",help="regenerate and execute a test by seed and one-based ID")
    replay.add_argument("--seed",type=int,required=True); replay.add_argument("--test-id",type=int,required=True)
    replay.add_argument("--min-length",type=int,default=8); replay.add_argument("--max-length",type=int,default=32)
    replay.add_argument("--memory-size",type=int,default=4096); replay.add_argument("--coverage-guided",action="store_true")
    replay.add_argument("--json",dest="json_path",default=None)
    sub.add_parser("coverage",help="show the supported instruction coverage model")
    sub.add_parser("version",help="show version")
    return root

def main(argv=None):
    args=parser().parse_args(argv)
    if args.command=="version": print(__version__); return 0
    if args.command=="coverage":
        print(json.dumps(Coverage().report(),indent=2)); return 0
    if args.command=="run":
        seed=args.seed if args.seed is not None else random.SystemRandom().randrange(1<<32)
        logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,format="[%(levelname)s] %(message)s")
        logging.info("Seed: %d",seed)
        runner=VerificationRunner(seed,args.min_length,args.max_length,args.memory_size,args.coverage_guided)
        summary=runner.run(args.tests,args.stop_on_failure); print_summary(summary)
        if args.json_path: print(f"JSON report: {write_json(summary,args.json_path)}")
        return int(summary["failed"]>0)
    if args.command=="replay":
        runner=VerificationRunner(args.seed,args.min_length,args.max_length,args.memory_size,args.coverage_guided)
        result=runner.replay(args.test_id)
        print(f"Replay test {result.test_id} with seed {result.seed}: {'PASS' if result.passed else 'FAIL'}")
        print("Program:"); [print(f"  {ins}") for ins in result.program]
        [print(f"Mismatch: {m}") for m in result.mismatches]
        if args.json_path:
            summary={"seed":args.seed,"test_id":result.test_id,"passed":result.passed,"program":[str(i) for i in result.program],"mismatches":runner.results_to_json([result])[0]["mismatches"]}
            write_json(summary,args.json_path)
        return int(not result.passed)
    return 2

if __name__=="__main__": raise SystemExit(main())
