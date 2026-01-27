"""
Node functions for The Refactoring Swarm graph.

Each function represents a node in the LangGraph state machine.
"""

from typing import Literal

from src.graph.state import RefactoringState
from src.agents.auditor import AuditorAgent
from src.agents.fixer import FixerAgent
from src.agents.judge import JudgeAgent
from src.llm import get_llm_provider
from src.config import get_config


def _get_api_key(config) -> str:
    if config.llm_provider == "mistral":
        return config.mistral_api_key or ""
    else:
        return config.google_api_key or ""


def _get_llm_instance(config):
    provider = config.llm_provider or "mistral"
    api_key = _get_api_key(config)
    model = config.llm_model
    return get_llm_provider(provider=provider, api_key=api_key, model=model)


def auditor_node(state: RefactoringState) -> dict:
    """
    Run the Auditor agent to analyze code and create a refactoring plan.

    This is the entry point of the graph. The Auditor:
    1. Scans the target directory for Python files
    2. Runs Pylint on each file
    3. Generates a structured refactoring plan
    """
    print("\n" + "=" * 70)
    print("🔍 AUDITOR AGENT - Analyzing codebase...")
    print("=" * 70)

    config = get_config()
    llm = _get_llm_instance(config)

    auditor = AuditorAgent(llm=llm, target_dir=state["target_dir"])
    result = auditor.analyze()

    print(f"✅ Found {len(result['files'])} Python files")
    print(f"📊 Baseline Pylint Score: {result['pylint_baseline']:.2f}/10")
    print(f"📝 Generated refactoring plan")
    print("=" * 70)

    return {
        "files": result["files"],
        "plan": result["plan"],
        "pylint_baseline": result["pylint_baseline"],
        "pylint_current": result["pylint_baseline"],
        "current_iteration": 1,
    }


def judge_generate_tests_node(state: RefactoringState) -> dict:
    """
    Run the Judge agent in test generation mode (TDD Phase 1).

    The Judge:
    1. Reads the refactoring plan
    2. Generates pytest tests that validate correct behavior
    3. Tests should FAIL on buggy code, PASS on correct code
    """
    print("\n" + "=" * 70)
    print(f"⚖️  JUDGE AGENT - Generating tests (Iteration {state['current_iteration']})")
    print("=" * 70)

    config = get_config()
    llm = _get_llm_instance(config)

    judge = JudgeAgent(llm=llm, target_dir=state["target_dir"])
    result = judge.generate_tests(
        plan=state["plan"],
        files=state["files"],
    )

    tests_count = len(result["generated_tests"]) if result["generated_tests"] else 0
    print(f"✅ Generated {tests_count} test files")

    if result["test_results"].get("passed", 0) > 0:
        print(
            f"⚠️  WARNING: {result['test_results']['passed']} tests already pass (should fail on buggy code)"
        )
    if result["test_results"].get("failed", 0) > 0:
        print(f"✅ Good: {result['test_results']['failed']} tests fail (exposing bugs)")

    print("=" * 70)

    return {
        "generated_tests": result["generated_tests"],
        "test_results": result["test_results"],
        "error_logs": result["error_logs"],
    }


def fixer_node(state: RefactoringState) -> dict:
    """
    Run the Fixer agent to apply code fixes.

    The Fixer:
    1. Reads the refactoring plan
    2. Reads error logs from previous test runs
    3. Applies fixes to the code
    4. Runs Pylint to verify improvements
    """
    print("\n" + "=" * 70)
    print(f"🔧 FIXER AGENT - Applying fixes (Iteration {state['current_iteration']})")
    print("=" * 70)

    if state.get("error_logs"):
        print(f"📋 Processing {len(state['error_logs'])} error logs from tests")

    config = get_config()
    llm = _get_llm_instance(config)

    fixer = FixerAgent(llm=llm, target_dir=state["target_dir"])
    result = fixer.fix(
        plan=state["plan"],
        files=state["files"],
        error_logs=state.get("error_logs", []),
        previous_attempts=state.get("fix_attempts", []),  # Pass previous attempts
    )

    print(f"📊 New Pylint Score: {result['pylint_current']:.2f}/10")
    baseline = state.get("pylint_baseline", 0)
    if result["pylint_current"] >= baseline:
        print(
            f"✅ Score improved/maintained (+{result['pylint_current'] - baseline:.2f})"
        )
    else:
        print(f"⚠️  Score decreased ({result['pylint_current'] - baseline:.2f})")

    # Set iteration on new fix attempts and merge with existing
    new_attempts = result.get("fix_attempts", [])
    for attempt in new_attempts:
        attempt["iteration"] = state["current_iteration"]

    all_attempts = state.get("fix_attempts", []) + new_attempts

    if new_attempts:
        print(f"📝 Recorded {len(new_attempts)} fix attempt(s)")

    print("=" * 70)

    return {
        "pylint_current": result["pylint_current"],
        "fix_attempts": all_attempts,  # Return accumulated fix attempts
    }


def judge_validate_node(state: RefactoringState) -> dict:
    """
    Run the Judge agent in validation mode (TDD Phase 2).

    The Judge:
    1. Runs the generated tests
    2. Reports success or failure
    3. Provides error context for the Fixer if tests fail
    4. Determines final status (including max_iterations check)
    """
    print("\n" + "=" * 70)
    print(f"⚖️  JUDGE AGENT - Validating fixes (Iteration {state['current_iteration']})")
    print("=" * 70)

    config = get_config()
    llm = _get_llm_instance(config)

    judge = JudgeAgent(llm=llm, target_dir=state["target_dir"])
    result = judge.validate()

    # Display test results
    test_results = result.get("test_results", {})
    passed = test_results.get("passed", 0)
    failed = test_results.get("failed", 0)
    errors = test_results.get("errors", 0)
    total = passed + failed + errors

    print(f"📊 Test Results: {passed}/{total} passed")
    if failed > 0:
        print(f"❌ {failed} tests failed")
    if errors > 0:
        print(f"⚠️  {errors} tests with errors")

    # Determine final status (moved from should_continue to keep it pure)
    status = result["status"]
    new_iteration = state["current_iteration"] + 1

    # Check for max iterations - this is the ONLY place we set this status
    if status not in ("success", "error") and new_iteration > state["max_iterations"]:
        status = "max_iterations"
        print(f"⏹️  Max iterations ({state['max_iterations']}) reached")

    # Display decision
    if status == "success":
        print("✅ All tests pass! Refactoring complete.")
    elif status == "max_iterations":
        print(f"⏹️  Stopping - max iterations reached")
    elif status == "error":
        print(f"❌ Error state - stopping")
    else:
        print(f"🔄 Tests still failing - continuing to next iteration")
        if result.get("error_logs"):
            print(f"📋 {len(result['error_logs'])} error logs available for Fixer")

    print("=" * 70)

    return {
        "test_results": result["test_results"],
        "error_logs": result["error_logs"],
        "status": status,
        "current_iteration": new_iteration,
    }


def should_continue(state: RefactoringState) -> Literal["continue", "end"]:
    """
    Decide whether to continue the Fixer-Judge loop.

    This is a PURE routing function - it does NOT mutate state.
    All status updates happen in judge_validate_node().

    Returns:
        "end" if tests pass, error occurred, or max iterations reached
        "continue" if tests fail and more iterations available
    """
    print("\n" + "=" * 70)
    print("🔀 DECISION POINT - Should continue loop?")
    print("=" * 70)

    print(
        f"📍 Current Iteration: {state['current_iteration']}/{state['max_iterations']}"
    )
    print(f"📊 Current Status: {state['status']}")

    # Route based on status (already set by judge_validate_node)
    if state["status"] == "success":
        print("✅ DECISION: END - All tests pass!")
        print("=" * 70)
        return "end"

    if state["status"] == "error":
        print("❌ DECISION: END - Error state (no tests found)")
        print("=" * 70)
        return "end"

    if state["status"] == "max_iterations":
        print(f"⏹️  DECISION: END - Max iterations ({state['max_iterations']}) reached")
        print("=" * 70)
        return "end"

    print(
        f"🔄 DECISION: CONTINUE - Tests still failing, trying iteration {state['current_iteration']}"
    )
    print("=" * 70)
    return "continue"
