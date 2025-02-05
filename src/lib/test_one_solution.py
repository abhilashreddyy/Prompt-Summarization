"""
Run solutions from one problem.
"""

import io
import json
import logging
import math
import numpy as np
import os
import pprint
import argparse
import time

# for timing debugging
from datetime import datetime, date
from tqdm import tqdm

from typing import List

logger = logging.getLogger('apiLogger')

def print_results(results, args):
    res = []
    per_prob_res = []
    all_correct = []
    for out in results.values():
        out = np.array(out[0])
        res.extend(out)
        out = np.where(out<=0, 0, out)
        per_prob_res.append(np.mean(out))
        all_correct.append(np.all(out))
    res = np.asarray(res)
    total_testcases = res.size
    compile_errors = np.count_nonzero(np.where(res==-2, 1, 0))
    runtime_errors = np.count_nonzero(np.where(res==-1, 1, 0))
    successes = np.count_nonzero(np.where(res==1, 1, 0))
    failures = total_testcases - compile_errors - runtime_errors - successes

    logger.info(f"number of compile errors = {compile_errors} avg = {compile_errors / total_testcases:.4f}")
    logger.info(f"number of runtime errors = {runtime_errors} avg = {runtime_errors / total_testcases:.4f}")
    logger.info(f"Test Case Average (average accuracy over problems) = {np.mean(per_prob_res):.4f}")
    logger.info(f"Strict Accuracy (all test cases passed / total problems) = {np.mean(all_correct):.4f}")

    logger.info(f"number of test cases run = {total_testcases}")
    
    # if total_testcases:
    #     logger.info(f"number of compile errors = {compile_errors} avg = {compile_errors / total_testcases:.4f}")
    #     logger.info(f"number of runtime errors = {runtime_errors} avg = {runtime_errors / total_testcases:.4f}")
    #     logger.info(f"Test Case Average (average accuracy over problems) = {np.mean(per_prob_res):.4f}")
    #     logger.info(f"Strict Accuracy (all test cases passed / total problems) = {np.mean(all_correct):.4f}")

def eval_and_save_problems(args):
    with open(args.test_loc, "r") as f:
        problems = json.load(f)

    logger.info(f'Testing {len(problems)} problems')
    gpt_codes = {}
    results = {}
    codes_loc = os.path.join(args.save, f"all_codes.json")
    if not os.path.exists(codes_loc):
        codes_loc = os.path.join(args.save, f"{args.start}-{args.end}_codes.json")

    if os.path.exists(codes_loc):
        results_loc = os.path.join(args.save, f"all_results.json") 
    else:
        results_loc = os.path.join(args.save, f"{args.start}-{args.end}_results.json") 
    logger.debug(f'Codes location {codes_loc}')
    logger.debug(f'Results save location {results_loc}')

    with open(codes_loc, "r") as f: 
        gpt_codes = json.load(f)

    if args.index:
        problems = [problems[args.index]]
    else:
        if args.start > len(problems) or args.start < 0:
            logger.critical(f"start index {args.start} > number of problems {len(problems)}")
            return
        start = args.start
        if args.end is None or args.end > len(problems):
            end = len(problems)
        else:
            end = args.end
        problems = problems[start:end]

    if args.stop_early:
        problems = problems[:args.stop_early]

    # main eval loop
    for index, problem in enumerate(tqdm(problems)):
        if args.debug:
            logger.debug(f"problem path = {problem}")
        output_str = gpt_codes[str(index+args.start)]

        problem_dir = os.path.dirname(problem)
        prob_path = os.path.join(args.root, problem_dir)
        
        if not os.path.exists(args.save):
            os.makedirs(args.save)

        res = []
        if args.debug:
            logger.debug(f"\nTesting this code\n{output_str}")
        curr_res = [-2]
        try:
            curr_res = test_util.run_test(prob_path=prob_path, test=output_str, debug=args.debug)
            fixed = []
            for e in curr_res:
                if isinstance(e, np.ndarray):
                   e = e.item(0)
                if isinstance(e, np.bool_):
                    e = bool(e)
                fixed.append(e)
            curr_res = fixed
            if not np.all(curr_res):
                logger.info(f"Results were not all True: {curr_res}")
        # There was no input output json
        except BaseException as e:
            logger.debug(f"{repr(e)}{e}")
            logger.error(f"Problem {problem} did not have test cases.")
            res = [[]]
            #res.append([])
        except Exception as e:
            logger.debug(f"test framework exception = {repr(e)}{e}")
            break
        finally:
            assert isinstance(curr_res, list)
            res.append(curr_res)

        logger.info(f"How to read results [-2] = compile error, [-1] = runtime error [False] = failed test case [True] = passed test case")
        logger.info(f"results = {res}")

        results[index+args.start+args.index] = res
        
        with open(results_loc, "w") as f:
            try:
                f.write(json.dumps(results))
            except Exception as e:
                import pdb; pdb.set_trace()
                logger.error("didn't save problem due to {e}")

    return results


def main(args):
    argsdict = vars(args)
    logger.info(pprint.pformat(argsdict))

    if args.print_results:
        results = {}
        codes_loc = os.path.join(args.save, f"all_codes.json")
        if os.path.exists(codes_loc):
            results_loc = os.path.join(args.save, f"all_results.json") 
        else:
            results_loc = os.path.join(args.save, f"{args.start}-{args.end}_results.json") 
        with open(results_loc, "r") as f: 
            results = json.load(f)
    else:
        results = eval_and_save_problems(args)

    print_results(results, args)


def parse_args(arg_str: str = None):
    parser = argparse.ArgumentParser(description="Testing a Language Model on Python Code")
    parser.add_argument("-t","--test_loc", default="../data_split/test.json", type=str, help="path to the json containing problem paths to be evaluated.")
    parser.add_argument("-r","--root", default="./", type=str, help="where the data is stored.")
    parser.add_argument("-s","--start", default=0, type=int)
    parser.add_argument("-e","--end", default=None, type=int, help="If you want to evaluate a subset of problems specify start and ending index. File with start and ending prefix must exist typically used with batch evaluation.")
    parser.add_argument("-i", "--index", default=0, type=int)
    parser.add_argument("-p", "--print_results", action="store_true", help="If you have already evaluated the results and only want to print them.")
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("--save", type=str, default="./results", help="Where the evaluated data is loaded from and results saved to.")
    parser.add_argument("--stop-early", default=None, type=int)

    args = parser.parse_args(arg_str)
    return args

if __name__ == "__main__":
    import testing_util as test_util
    import my_logger
    args = parse_args()
    main(args)
else:
    from . import my_logger
    from . import testing_util as test_util