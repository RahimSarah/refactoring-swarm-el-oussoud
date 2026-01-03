#!/usr/bin/env python3
"""
The Refactoring Swarm - Main Entry Point

An autonomous multi-agent system for Python code refactoring.

Usage:
    python main.py --target_dir <path>

The system will:
1. Analyze the code with the Auditor agent
2. Generate tests with the Judge agent (TDD)
3. Apply fixes with the Fixer agent
4. Validate fixes with the Judge agent
5. Loop until all tests pass or max iterations reached
"""

import argparse
import sys
import os

from dotenv import load_dotenv

from src.config import get_config, set_config, Config
from src.graph.state import initialize_state
from src.graph.builder import compile_graph
from src.utils.logger import log_experiment, ActionType


def main():
    """Main entry point for The Refactoring Swarm."""
    # Load environment variables from .env file
    load_dotenv()

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="The Refactoring Swarm - Autonomous Python code refactoring"
    )
    parser.add_argument(
        "--target_dir",
        type=str,
        required=True,
        help="Path to the directory containing code to refactor",
    )
    parser.add_argument(
        "--max_iterations",
        type=int,
        default=10,
        help="Maximum number of iterations (default: 10)",
    )
    args = parser.parse_args()

    # Validate target directory
    if not os.path.exists(args.target_dir):
        print(f"Error: Directory '{args.target_dir}' not found.")
        sys.exit(1)

    if not os.path.isdir(args.target_dir):
        print(f"Error: '{args.target_dir}' is not a directory.")
        sys.exit(1)

    # Load and validate configuration
    try:
        config = Config.from_env()
        config.max_iterations = args.max_iterations
        config.validate()
        set_config(config)
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)

    # Log startup
    print(f"Starting The Refactoring Swarm on: {args.target_dir}")
    log_experiment(
        agent_name="System",
        model_used="N/A",
        action=ActionType.ANALYSIS,
        details={
            "input_prompt": f"python main.py --target_dir {args.target_dir}",
            "output_response": "System startup",
            "target_dir": args.target_dir,
            "max_iterations": args.max_iterations,
        },
        status="SUCCESS",
    )

    # Initialize state
    initial_state = initialize_state(
        target_dir=args.target_dir,
        max_iterations=args.max_iterations,
    )

    # Build and compile the graph
    try:
        app = compile_graph()
    except Exception as e:
        print(f"Error building graph: {e}")
        log_experiment(
            agent_name="System",
            model_used="N/A",
            action=ActionType.DEBUG,
            details={
                "input_prompt": "compile_graph()",
                "output_response": f"ERROR: {e}",
                "error": str(e),
            },
            status="FAILURE",
        )
        sys.exit(1)

    # Execute the graph
    print("Running refactoring pipeline...")
    try:
        # Calculate recursion limit based on max_iterations
        # Each iteration uses ~3-4 graph steps, plus initial setup
        recursion_limit = (args.max_iterations * 5) + 10
        config = {"recursion_limit": recursion_limit}

        final_state = app.invoke(initial_state, config=config)

        # Report results
        status = final_state.get("status", "unknown")
        iterations = final_state.get("current_iteration", 0)
        pylint_baseline = final_state.get("pylint_baseline", 0)
        pylint_current = final_state.get("pylint_current", 0)

        print("\n" + "=" * 50)
        print("REFACTORING COMPLETE")
        print("=" * 50)
        print(f"Status: {status.upper()}")
        print(f"Iterations: {iterations}")
        print(f"Pylint Score: {pylint_baseline:.2f} → {pylint_current:.2f}")

        if pylint_current >= pylint_baseline:
            print("Pylint score IMPROVED or maintained")
        else:
            print("WARNING: Pylint score decreased")

        # Log completion
        log_experiment(
            agent_name="System",
            model_used="N/A",
            action=ActionType.ANALYSIS,
            details={
                "input_prompt": "Graph execution complete",
                "output_response": f"Status: {status}, Iterations: {iterations}",
                "final_status": status,
                "iterations": iterations,
                "pylint_baseline": pylint_baseline,
                "pylint_current": pylint_current,
            },
            status="SUCCESS" if status == "success" else "FAILURE",
        )

        # Print final message
        if status == "success":
            print("\nMISSION_COMPLETE: All tests passed!")
        elif status == "max_iterations":
            print(
                f"\nMax iterations ({args.max_iterations}) reached. Best effort applied."
            )
        else:
            print(f"\nCompleted with status: {status}")

    except Exception as e:
        print(f"\nError during execution: {e}")
        log_experiment(
            agent_name="System",
            model_used="N/A",
            action=ActionType.DEBUG,
            details={
                "input_prompt": "app.invoke(initial_state)",
                "output_response": f"ERROR: {e}",
                "error": str(e),
            },
            status="FAILURE",
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
