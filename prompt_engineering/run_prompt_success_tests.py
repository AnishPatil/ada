#!/usr/bin/env python3
"""Run repeated ADA prompt tests and write Excel-friendly CSV results.

Examples:
    python prompt_engineering/run_prompt_success_tests.py \
        --prompt "give me an airfoil" \
        --iterations 25 \
        --criterion geometry-exact \
        --expected-geometries 1

    python prompt_engineering/run_prompt_success_tests.py \
        --setup-prompt "generate a naca2412 airfoil" \
        --prompt "change all 8 K parameters on the upper surface" \
        --iterations 10 \
        --criterion coefficients-changed \
        --surface upper \
        --min-coefficients-changed 8
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
import io
import os
from pathlib import Path
import re
import sys
import time
from typing import Any


#find ADA project folder and make it importable to Python
#allows running ADA through the script itself, without GUI
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
os.environ.setdefault("PATH_TO_ADA", str(REPO_ROOT) + os.sep)
LOCAL_CACHE_DIR = REPO_ROOT / "prompt_engineering" / ".cache"
LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("XDG_CACHE_HOME", str(LOCAL_CACHE_DIR))
MPL_CACHE_DIR = REPO_ROOT / "prompt_engineering" / ".matplotlib_cache"
MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))

from ada.ui.llm_runtime import resolve_model  # noqa: E402
from ada.ui.uiManager import UIHandler  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run ADA prompts repeatedly with a fresh UIHandler per iteration."
    )
    prompt_source = parser.add_mutually_exclusive_group(required=True)
    #if you want to test a single prompt that you type out
    prompt_source.add_argument("--prompt", help="Single prompt to test.")
    #if you have a file containing multiple prompts (must be one per line)
    prompt_source.add_argument(
        "--prompt-file",
        type=Path,
        help="Text file containing one prompt per non-empty line.",
    )

    #to specify number of iterations (Default 25)
    parser.add_argument("--iterations", type=int, default=25)
    #use function-calling mode
    parser.add_argument("--mode", default="Functions")
    #if the prompt you need to test requires setup e.g. making an airfoil first, you can specify setup prompt to run beforehand
    parser.add_argument(
        "--setup-prompt",
        action="append",
        default=[],
        help="Prompt to run before each measured test prompt. Can be repeated.",
    )
    #specify criteria to test for success, e.g. no errors, geometry count (exact or at least), data count, analysis case count, or coefficient changes
    #can add more if needed
    parser.add_argument(
        "--criterion",
        choices=[
            "no-error",
            "geometry-exact",
            "geometry-at-least",
            "data-at-least",
            "analysis-at-least",
            "coefficients-changed",
        ],
        default="geometry-exact",
    )
    #specify the count for each criteria, e.g. how many geometries generated, how many coefficients changed, etc
    parser.add_argument("--expected-geometries", type=int, default=1)
    parser.add_argument("--expected-data-items", type=int, default=1)
    parser.add_argument("--expected-analysis-cases", type=int, default=1)
    parser.add_argument("--min-coefficients-changed", type=int, default=1)
    #can check for upper, lower, or both surfaces for K coefficient changes
    parser.add_argument(
        "--surface",
        choices=["upper", "lower", "both"],
        default="both",
        help="Surface to inspect for the coefficients-changed criterion.",
    )
    #specify prompt test CSV result output path
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="CSV output path. Defaults to prompt_engineering/results/<model>/<timestamp>.csv.",
    )
    parser.add_argument(
        "--session-root",
        type=Path,
        default=None,
        help="Directory for per-iteration ADA session files. Defaults to a model-specific directory.",
    )
    parser.add_argument(
        "--show-ada-logs",
        action="store_true",
        help="Show ADA/model debug logs while each prompt runs.",
    )
    parser.add_argument("--notes-max-chars", type=int, default=500)
    return parser.parse_args()


def load_prompts(args: argparse.Namespace) -> list[str]:
    #if single prompt is given, return it as a list
    if args.prompt is not None:
        return [args.prompt]

    #if prompt file is given, put each prompt into a list (ignores empty lines)
    with args.prompt_file.open("r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def make_handler(session_dir: Path) -> UIHandler:
    #creates a new ADA session for every prompt, so they are tested equally
    #creates session directory for every test
    session_dir.mkdir(parents=True, exist_ok=True)
    handler = UIHandler(print_calls=False)
    handler.sessionDirectory = str(session_dir)
    handler.relativeSessionDirectory = str(session_dir)
    handler.workingDirectory = str(session_dir)
    return handler


def run_prompt(handler: UIHandler, prompt: str, mode: str, show_logs: bool) -> tuple[float, str | None]:
    #calls UIHandler.makeCall() for the list of prompts made earlier
    #track elapsed time for each prompt call by recording start time then subtracting it from end time
    start = time.perf_counter()
    try:
        if show_logs:
            handler.makeCall(prompt, mode)
        else:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                handler.makeCall(prompt, mode)
        return time.perf_counter() - start, None
    except Exception as exc:
        return time.perf_counter() - start, repr(exc)


def response_text(handler: UIHandler) -> str:
    #returns the most recent recorded response by ADA
    if not handler.calls:
        return ""
    return str(handler.calls[-1].response)


def count_analysis_cases(handler: UIHandler) -> int:
    return sum(len(cases) for cases in handler.analysisItems.values())


def geometry_snapshot(handler: UIHandler) -> dict[str, Any]:
    #records the K coefficients of the geometry
    #this is called before and after making changes to it, to find out how the K coefficiets changed
    geometries = []
    for geometry in handler.geometryItems:
        geometries.append(
            {
                "upper": [float(value) for value in geometry.upperCoefficients],
                "lower": [float(value) for value in geometry.lowerCoefficients],
            }
        )
    return {
        "active_geometry": handler.activeGeometry,
        "geometries": geometries,
    }


def _active_geometry_coefficients(snapshot: dict[str, Any], surface: str) -> list[float]:
    #obtain K coefficients of the selected active geometry by ADA for specified surface, using the snapshot
    geometries = snapshot["geometries"]
    if not geometries:
        return []

    active_index = snapshot["active_geometry"]
    #if the current active geometry index is valid, use the last geometry in the list of geometries stored in the snapshot
    if active_index is None or active_index < 0 or active_index >= len(geometries):
        active_index = len(geometries) - 1

    return geometries[active_index][surface]


def count_coefficient_changes(
    #compare the K coefficients before and after they are changed, and count the number of K coefficients changed
    before: dict[str, Any],
    after: dict[str, Any],
    surface: str,
    tolerance: float = 1e-12,
) -> int:
    surfaces = ["upper", "lower"] if surface == "both" else [surface]
    changed = 0

    for current_surface in surfaces:
        before_values = _active_geometry_coefficients(before, current_surface)
        after_values = _active_geometry_coefficients(after, current_surface)
        for before_value, after_value in zip(before_values, after_values):
            if abs(after_value - before_value) > tolerance:
                changed += 1

    return changed


def has_failure_text(text: str) -> bool:
    #check if there are any obvious failure messages in ADA's final response
    upper_text = text.upper()
    return "ERROR" in upper_text or "FAILURE" in upper_text


def score_iteration(
    args: argparse.Namespace,
    handler: UIHandler,
    before_prompt_snapshot: dict[str, Any],
    after_prompt_snapshot: dict[str, Any],
    error: str | None,
) -> tuple[bool, str, int]:
    #Function decided whether a test is a success or not
    #Takes in chosen prompt/criteria, ADA UIHandler state, snapshots before and after, and any Python errors that might have occurred


    geometry_count = len(handler.geometryItems)
    data_count = len(handler.dataItems)
    analysis_count = count_analysis_cases(handler)
    final_response = response_text(handler)
    coefficients_changed = count_coefficient_changes(
        before_prompt_snapshot,
        after_prompt_snapshot,
        args.surface,
    )

    #checks for any obvious ADA response or Python errors
    if error is not None:
        return False, f"Exception while running prompt: {error}", coefficients_changed
    if has_failure_text(final_response):
        return False, f"Response contains ERROR/FAILURE: {final_response}", coefficients_changed
    if args.criterion == "no-error":
        return True, "No exception or failure text detected.", coefficients_changed

    #check if each criteria type is satisfied, return success boolean/notes accordingly
    if args.criterion == "geometry-exact":
        success = geometry_count == args.expected_geometries
        note = f"Expected {args.expected_geometries} geometries; observed {geometry_count}."
        return success, note, coefficients_changed

    if args.criterion == "geometry-at-least":
        success = geometry_count >= args.expected_geometries
        note = f"Expected at least {args.expected_geometries} geometries; observed {geometry_count}."
        return success, note, coefficients_changed

    if args.criterion == "data-at-least":
        success = data_count >= args.expected_data_items
        note = f"Expected at least {args.expected_data_items} data items; observed {data_count}."
        return success, note, coefficients_changed

    if args.criterion == "analysis-at-least":
        success = analysis_count >= args.expected_analysis_cases
        note = f"Expected at least {args.expected_analysis_cases} analysis cases; observed {analysis_count}."
        return success, note, coefficients_changed

    if args.criterion == "coefficients-changed":
        success = coefficients_changed >= args.min_coefficients_changed
        note = (
            f"Expected at least {args.min_coefficients_changed} changed coefficients "
            f"on {args.surface}; observed {coefficients_changed}."
        )
        return success, note, coefficients_changed

    raise ValueError(f"Unsupported criterion: {args.criterion}")


def truncate(value: str, max_chars: int) -> str:
    #truncates long (exceeding specified max chars) csv entries if needed
    return value if len(value) <= max_chars else value[:max_chars] + "...(truncated)"


def model_directory_name(model_name: str) -> str:
    """Create a portable folder name while keeping the exact model name in the CSV."""
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", model_name.strip())
    return safe_name.strip(".-") or "unknown-model"


def default_output_path(model_folder: str, timestamp: str) -> Path:
    #specify default output path for result CSV file, grouped by selected model
    return (
        REPO_ROOT
        / "prompt_engineering"
        / "results"
        / model_folder
        / f"prompt_success_{timestamp}.csv"
    )



def main() -> int:
    #use above functions to obtain setup arguments (criteria, iterations, etc), prompts, and output path
    args = parse_args()
    prompts = load_prompts(args)
    model_name = resolve_model()
    model_folder = model_directory_name(model_name)
    timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    output_path = args.output or default_output_path(model_folder, timestamp)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    #create root folder and CSV file with specified columns
    session_root = args.session_root or (
        REPO_ROOT / "prompt_engineering" / "test_sessions" / model_folder / timestamp
    )

    print(f"Testing model: {model_name} (output folder: {model_folder})")

    fieldnames = [
        "model",
        "prompt_index",
        "iteration_number",
        "prompt",
        "success",
        "time_seconds",
        "cumulative_success_rate",
        "notes",
        "criterion",
        "geometry_count",
        "analysis_case_count",
        "data_count",
        "coefficients_changed",
        "final_response",
        "error",
        "session_directory",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()


        for prompt_index, prompt in enumerate(prompts, start=1):
            #calculate success counter for each prompt iteration. The success rate is calculated by dividing total success score by number of iterations
            successes = 0
            for iteration in range(1, args.iterations + 1):
                session_dir = session_root / f"prompt_{prompt_index:03d}" / f"iteration_{iteration:03d}"
                handler = make_handler(session_dir)

                setup_errors = []
                #runs any setup prompts if specified
                for setup_prompt in args.setup_prompt:
                    _setup_time, setup_error = run_prompt(
                        handler,
                        setup_prompt,
                        args.mode,
                        args.show_ada_logs,
                    )
                    if setup_error:
                        setup_errors.append(f"Setup prompt failed: {setup_error}")

                #records snapshots before and after the prompt has ran
                before_prompt_snapshot = geometry_snapshot(handler)
                time_seconds, error = run_prompt(handler, prompt, args.mode, args.show_ada_logs)
                after_prompt_snapshot = geometry_snapshot(handler)
                if setup_errors and error is None:
                    error = "; ".join(setup_errors)

                success, notes, coefficients_changed = score_iteration(
                    args,
                    handler,
                    before_prompt_snapshot,
                    after_prompt_snapshot,
                    error,
                )
                if success:
                    #increment success counter if all the error checks are passed
                    successes += 1

                cumulative_success_rate = successes / iteration
                final_response = response_text(handler)

                #populate CSV columns with output information
                writer.writerow(
                    {
                        "model": model_name,
                        "prompt_index": prompt_index,
                        "iteration_number": iteration,
                        "prompt": prompt,
                        "success": "yes" if success else "no",
                        "time_seconds": f"{time_seconds:.3f}",
                        "cumulative_success_rate": f"{cumulative_success_rate:.4f}",
                        "notes": truncate(notes, args.notes_max_chars),
                        "criterion": args.criterion,
                        "geometry_count": len(handler.geometryItems),
                        "analysis_case_count": count_analysis_cases(handler),
                        "data_count": len(handler.dataItems),
                        "coefficients_changed": coefficients_changed,
                        "final_response": truncate(final_response, args.notes_max_chars),
                        "error": truncate(error or "", args.notes_max_chars),
                        "session_directory": str(session_dir),
                    }
                )
                csv_file.flush()

                print(
                    f"Prompt {prompt_index}/{len(prompts)}, iteration {iteration}/{args.iterations}: "
                    f"{'success' if success else 'failure'} "
                    f"({cumulative_success_rate:.2%} cumulative, {time_seconds:.2f}s)"
                )

    print(f"Wrote results to {output_path}")
    return 0

#only run the main function when this file is directly ran. if it is imported in another file, the helper functions can be used
if __name__ == "__main__":
    raise SystemExit(main())
