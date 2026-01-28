# Technical Specification: The Refactoring Swarm

**Project**: TP IGL 2025-2026  
**Version**: 1.2.0  
**Last Updated**: January 9, 2026  
**Status**: Draft  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [Agent Specifications](#3-agent-specifications)
4. [Tool Specifications](#4-tool-specifications)
5. [Data Flow & State Management](#5-data-flow--state-management)
6. [Iteration & Termination Logic](#6-iteration--termination-logic)
7. [Logging & Telemetry](#7-logging--telemetry)
8. [LLM Provider Interface](#8-llm-provider-interface)
9. [Project Structure](#9-project-structure)
10. [Implementation Roadmap](#10-implementation-roadmap)
11. [Open Questions (TBD)](#11-open-questions-tbd)
- [Appendix A: System Prompts](#appendix-a-system-prompts)
- [Appendix B: Example Refactoring Plan](#appendix-b-example-refactoring-plan)
- [Appendix C: State Schema](#appendix-c-state-schema)

---

## 1. Executive Summary

### 1.1 Mission

Build an autonomous multi-agent system ("The Refactoring Swarm") that takes buggy, undocumented, untested Python code and delivers a clean, functional, validated version without human intervention.

### 1.2 Key Constraints

| Constraint | Value |
|------------|-------|
| Framework | LangGraph (v0.0.25) |
| LLM Provider | Google Gemini (configurable) |
| Max Iterations | 10 total |
| Entry Point | `python main.py --target_dir <path>` |
| Output | Modified files in `target_dir` + `logs/experiment_data.json` |

### 1.3 Success Criteria

1. **Primary**: All unit tests pass (Judge validates)
2. **Secondary**: Pylint score must **IMPROVE** (final ≥ baseline)
3. **Fallback**: Best effort after max iterations

> ⚠️ **Pylint Score Requirement** (from Doc 1):
> - Final `pylint_current` must be **≥** `pylint_baseline`
> - Temporary drops are allowed during intermediate iterations
> - The grading bot checks: "Le score Pylint a-t-il **augmenté** ?"

### 1.4 Grading Breakdown (Per Spec)

| Dimension | Weight | Criteria |
|-----------|--------|----------|
| Performance | 40% | Tests pass, Pylint score improved |
| Technical Robustness | 30% | No crashes, no infinite loops, respects `--target_dir` |
| Data Quality | 30% | Valid `experiment_data.json` with complete action history |

---

## 2. System Architecture

### 2.1 High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR                            │
│                      (LangGraph StateGraph)                     │
└─────────────────────────────────────────────────────────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│     AUDITOR     │   │      FIXER      │   │      JUDGE      │
│   (The Auditor) │   │  (The Fixer)    │   │   (The Judge)   │
├─────────────────┤   ├─────────────────┤   ├─────────────────┤
│ - Read code     │   │ - Read plan     │   │ - Run tests     │
│ - Run Pylint    │   │ - Modify files  │   │ - Validate      │
│ - Generate plan │   │ - Apply fixes   │   │ - Route result  │
└─────────────────┘   └─────────────────┘   └─────────────────┘
         │                      │                      │
         └──────────────────────┴──────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │      SHARED STATE     │
                    │   (RefactoringState)  │
                    └───────────────────────┘
```

### 2.2 Agent Flow (TDD Approach)

```
                    ┌─────────┐
                    │  START  │
                    └────┬────┘
                         │
                         ▼
                  ┌──────────────┐
                  │   AUDITOR    │ ◄─── Iteration 1: Analyze & Plan
                  │  (analyze)   │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │    JUDGE     │ ◄─── Generate Tests (TDD)
                  │ (gen tests)  │      Write tests that EXPOSE bugs
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
             ┌───►│    FIXER     │ ◄─── Iterations 2-9: Fix code
             │    │   (repair)   │
             │    └──────┬───────┘
             │           │
             │           ▼
             │    ┌──────────────┐
             │    │    JUDGE     │ ◄─── Run tests to validate
             │    │  (validate)  │
             │    └──────┬───────┘
             │           │
             │           ▼
             │    ┌──────────────┐
             │    │ Tests Pass?  │
             │    └──────┬───────┘
             │           │
             │     ┌─────┴─────┐
             │     │           │
             │    NO          YES
             │     │           │
             │     ▼           ▼
             └─────┘      ┌─────────┐
                         │   END   │
                         └─────────┘

Legend:
- Auditor: Analyzes code, produces refactoring plan
- Judge (Gen): Creates tests based on plan (TDD - tests should FAIL initially)
- Fixer: Applies fixes to make tests pass
- Judge (Val): Runs tests to verify fixes work
```

### 2.3 LangGraph State Machine Definition

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Literal

class RefactoringState(TypedDict):
    target_dir: str
    files: list[str]
    plan: str
    generated_tests: list[str]  # NEW: Tests created by Judge
    current_iteration: int
    max_iterations: int
    pylint_baseline: float
    pylint_current: float
    test_results: str
    error_logs: list[str]
    status: Literal["in_progress", "success", "failure"]

# Graph definition (TDD Flow)
graph = StateGraph(RefactoringState)

# Nodes
graph.add_node("auditor", auditor_node)
graph.add_node("judge_generate", judge_generate_tests_node)  # NEW: Test generation
graph.add_node("fixer", fixer_node)
graph.add_node("judge_validate", judge_validate_node)

# Entry point
graph.set_entry_point("auditor")

# Edges (TDD Flow)
graph.add_edge("auditor", "judge_generate")        # Auditor → Judge generates tests
graph.add_edge("judge_generate", "fixer")          # Judge → Fixer (with failing tests)
graph.add_edge("fixer", "judge_validate")          # Fixer → Judge validates

# Conditional: Loop or End
graph.add_conditional_edges(
    "judge_validate",
    should_continue,
    {
        "continue": "fixer",    # Tests failed → back to Fixer
        "end": END              # Tests passed → done!
    }
)

app = graph.compile()
```

---

## 3. Agent Specifications

### 3.1 Auditor Agent (The Auditor)

#### Purpose
Analyze the target codebase, run static analysis, and produce a structured refactoring plan.

#### Inputs
| Input | Source | Description |
|-------|--------|-------------|
| `target_dir` | CLI argument | Path to code directory |
| `files` | Directory scan | List of Python files |

#### Outputs
| Output | Destination | Description |
|--------|-------------|-------------|
| `plan` | State | Structured Markdown refactoring plan |
| `pylint_baseline` | State | Initial Pylint score |

#### Tools Available
| Tool | Purpose |
|------|---------|
| `read_file(path)` | Read file contents |
| `list_directory(path)` | List files in directory |
| `run_pylint(path)` | Execute Pylint analysis |
| `run_tests(path)` | Discover and run existing tests |

#### Behavior
1. Scan `target_dir` for all `.py` files
2. Run Pylint on each file, record baseline score
3. Run existing tests (if any) to understand current state
4. Analyze code for issues:
   - Syntax errors
   - Missing docstrings
   - Naming convention violations
   - Unused imports/variables
   - Code complexity issues
   - Missing type hints
   - Bug patterns
5. Generate structured refactoring plan (see [Appendix B](#appendix-b-example-refactoring-plan))

#### ActionType Mapping
- Primary: `ActionType.ANALYSIS`
- Test discovery: `ActionType.ANALYSIS`

---

### 3.2 Fixer Agent (The Fixer)

#### Purpose
Read the refactoring plan and apply fixes to the code files.

#### Inputs
| Input | Source | Description |
|-------|--------|-------------|
| `plan` | State (from Auditor) | Refactoring plan |
| `error_logs` | State (from Judge) | Previous test failures (if any) |
| `current_iteration` | State | Current loop iteration |

#### Outputs
| Output | Destination | Description |
|--------|-------------|-------------|
| Modified files | `target_dir` | Updated Python files |
| `pylint_current` | State | Post-fix Pylint score |

#### Tools Available
| Tool | Purpose |
|------|---------|
| `read_file(path)` | Read file contents |
| `write_file(path, content)` | Write complete file (full replacement) |
| `run_pylint(path)` | Verify fix quality |

#### Behavior
1. Parse the refactoring plan
2. For each file with issues (sequential processing):
   a. Read current file content
   b. Apply fixes based on plan + error logs
   c. Write complete fixed file (full replacement strategy)
   d. Run Pylint to verify improvement
3. Update `pylint_current` in state
4. Log all modifications

#### Code Output Strategy
**Full File Replacement** (chosen over diff/patch for reliability):

```python
# Fixer outputs complete file content
def apply_fix(file_path: str, new_content: str) -> None:
    """Replace entire file content with fixed version."""
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
```

#### Error Recovery
When `error_logs` contains previous failures:
1. Parse the error message and stack trace
2. Identify the failing test and relevant code
3. Prioritize fixing the specific failure over plan items
4. Avoid repeating previous fix attempts (tracked in state)

#### ActionType Mapping
- Code modification: `ActionType.FIX`
- Error analysis: `ActionType.DEBUG`

---

### 3.3 Judge Agent (The Judge)

#### Purpose
**Generate tests** to validate fixes (TDD approach) and decide whether to continue or terminate.

> **CRITICAL**: The hidden dataset has NO existing tests. The Judge must CREATE tests based on the Auditor's plan to validate the Fixer's corrections. The professor's bot will run its own hidden tests for final grading.

#### Two Levels of Testing

| Level | Owner | Purpose |
|-------|-------|---------|
| **Generated Tests** | Judge Agent (you) | Validate that Fixer's corrections work |
| **Hidden Tests** | Professor's Bot | Grade final code quality (syntax, logic, docstrings) |

#### Inputs
| Input | Source | Description |
|-------|--------|-------------|
| `target_dir` | State | Path to modified code |
| `plan` | State (from Auditor) | Issues to write tests for |
| `current_iteration` | State | Current loop count |

#### Outputs
| Output | Destination | Description |
|--------|-------------|-------------|
| `generated_tests` | `target_dir/tests/` | Test files created by Judge |
| `test_results` | State | Test execution summary |
| `error_logs` | State | Failure details (if any) |
| `status` | State | `success` or `in_progress` |
| Decision | Router | `continue` or `end` |

#### Tools Available
| Tool | Purpose |
|------|---------|
| `read_file(path)` | Read source code to understand what to test |
| `write_file(path, content)` | Write generated test files |
| `run_tests(path)` | Execute pytest on generated tests |

#### TDD Workflow (Test-Driven Development)

```
┌─────────────────────────────────────────────────────────────────┐
│                     JUDGE TDD WORKFLOW                          │
└─────────────────────────────────────────────────────────────────┘

Phase 1: BEFORE Fixer runs (First iteration only)
┌─────────────────────────────────────────────────────────────────┐
│ 1. Read Auditor's plan (issues identified)                      │
│ 2. For each bug/issue in plan:                                  │
│    a. Analyze the buggy code                                    │
│    b. SEMANTIC ANALYSIS: Infer INTENT from function names       │
│       (e.g., "average" → expects mean calculation)              │
│    c. Write a test that validates CORRECT BEHAVIOR              │
│       (should FAIL on buggy code, PASS on correct code)         │
│    d. Save test to target_dir/tests/test_<module>.py           │
│ 3. Run tests → Expect FAILURES (confirms bugs exist)            │
│ 4. Pass error logs to Fixer                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    [Fixer applies fixes]
                              │
                              ▼
Phase 2: AFTER Fixer runs (Every subsequent iteration)
┌─────────────────────────────────────────────────────────────────┐
│ 1. Run the same tests again                                     │
│ 2. If all tests PASS → SUCCESS (bugs are fixed!)                │
│ 3. If tests still FAIL → Return to Fixer with error context     │
└─────────────────────────────────────────────────────────────────┘
```

#### ⚠️ CRITICAL: Functional Correctness (Professor's Clarification - Jan 2026)

> **"L'Agent Testeur ne regarde pas seulement le code tel qu'il est, mais il essaie de deviner ce qu'il DEVRAIT être."**

The Judge Agent must:

1. **Analyze function NAMES semantically** to understand the INTENDED behavior
2. **Generate tests for business logic correctness**, not just error handling
3. **Test that computations return CORRECT values**

##### Example: Logic Bug Detection

```
Buggy Code:
┌────────────────────────────────────────┐
│ def calculate_average(numbers):        │
│     return sum(numbers)  # BUG: Missing division! │
└────────────────────────────────────────┘

Judge's Semantic Analysis:
1. Function name: "calculate_average" 
2. Intent: Calculate the MEAN of numbers
3. Expected behavior: sum(numbers) / len(numbers)

Judge Generates Test:
┌────────────────────────────────────────┐
│ def test_calculate_average():          │
│     assert calculate_average([10, 20]) == 15  # EXPECTS MEAN │
└────────────────────────────────────────┘

Test Execution on Buggy Code:
- Actual result: 30 (sum)
- Expected result: 15 (mean)
- Test FAILS: "AssertionError: assert 30 == 15"

Fixer Receives Error:
"Expected 15, got 30" → Deduces division is missing → Fixes code
```

##### ⚠️ WARNING from Professor:
> "Si vos tests vérifie uniquement la syntaxe et l'exécution, vous ne détecterez jamais ces bugs de 'logique', et votre correction sera rejetée par le Bot de Correction final lorsqu'on va exécuter à la fin votre code sur notre dataset de codes."

**Translation**: If your tests only verify syntax and execution (not logic), you will NEVER detect logic bugs, and your corrections will be REJECTED by the final grading bot.

#### Behavior

**First Iteration (Test Generation Phase):**
1. Read the Auditor's refactoring plan
2. For each identified bug/issue:
   a. Read the relevant source code
   b. Generate a pytest test that validates correct behavior
   c. The test should FAIL on buggy code, PASS on correct code
3. Write tests to `{target_dir}/tests/test_generated.py`
4. Run tests (expect failures - this confirms bugs exist)
5. Pass failure context to Fixer

**Subsequent Iterations (Validation Phase):**
1. Re-run the generated tests
2. If all pass: Set `status = "success"`, return `"end"`
3. If failures remain: Extract context, return `"continue"`

#### Test Generation Strategy

The Judge must generate tests that validate **both**:
1. **Functional Correctness** (business logic is correct)
2. **Error Handling** (edge cases are handled properly)

##### Strategy 1: Semantic Analysis of Function Names

```python
# CRITICAL: Analyze function name to understand INTENT
# Function: "calculate_average" → Intent: compute mean value

def test_calculate_average_returns_mean():
    """Test that calculate_average returns the arithmetic mean."""
    # This tests the LOGIC, not just execution
    assert calculate_average([10, 20]) == 15.0  # (10+20)/2 = 15
    assert calculate_average([1, 2, 3, 4, 5]) == 3.0
    assert calculate_average([100]) == 100.0

def test_calculate_average_empty_list():
    """Test edge case: empty list handling."""
    with pytest.raises(ValueError, match="[Cc]annot calculate average of empty"):
        calculate_average([])
```

##### Strategy 2: Error Handling Tests

```python
# Example: If Auditor found "Division by zero bug in divide()"
# Judge generates:

def test_divide_by_zero_handling():
    """Test that divide() handles zero divisor correctly."""
    # This should NOT raise ZeroDivisionError
    # It should either return a safe value or raise ValueError
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(10, 0)

def test_divide_normal_operation():
    """Test that divide() works for normal inputs."""
    assert divide(10, 2) == 5
    assert divide(9, 3) == 3
```

##### Key Principle: Test INTENT, Not Implementation

| Function Name | Inferred Intent | Test Should Verify |
|---------------|-----------------|-------------------|
| `calculate_average()` | Compute mean | Returns `sum/count`, not just `sum` |
| `sort_descending()` | Sort in descending order | Returns `[5,4,3,2,1]`, not `[1,2,3,4,5]` |
| `find_maximum()` | Find largest value | Returns max, not min or first element |
| `count_words()` | Count words in text | Returns correct count, not character count |
| `is_palindrome()` | Check if palindrome | Returns `True` for "radar", `False` for "hello" |

#### Test File Structure

```
{target_dir}/
├── src/
│   ├── calculator.py      # Buggy code (original)
│   └── utils.py
└── tests/                  # Created by Judge
    ├── __init__.py
    ├── test_calculator.py  # Tests for calculator.py
    └── test_utils.py       # Tests for utils.py
```

#### Error Context Tiering
| Iteration | Context Provided to Fixer |
|-----------|---------------------------|
| 1st failure | Generated test code + expected vs actual + stack trace |
| 2nd failure | Above + summary of previous fix attempt |
| 3rd+ failure | Compressed summary + "tried X, Y, Z - try different approach" |

#### ActionType Mapping
- Test generation (writing test code): `ActionType.GENERATION`
- Semantic analysis (inferring function intent): `ActionType.ANALYSIS`
- Test execution (running pytest): `ActionType.ANALYSIS`
- Error analysis (parsing failures): `ActionType.DEBUG`

---

## 4. Tool Specifications

### 4.1 File Operations

> **⚠️ SECURITY REQUIREMENT** (from Doc 1):
> - All file operations MUST be restricted to `target_dir` (the sandbox)
> - Agents are **forbidden** from writing outside the sandbox
> - Path traversal attacks (`../`) must be blocked

#### Path Validation (MANDATORY)

```python
from pathlib import Path

def validate_path(path: str, target_dir: str) -> str:
    """
    Validate that path is within target_dir (sandbox).
    
    Args:
        path: Path to validate (absolute or relative)
        target_dir: The sandbox directory (from --target_dir CLI arg)
        
    Returns:
        Resolved absolute path if valid
        
    Raises:
        PermissionError: If path escapes sandbox
    """
    # Resolve both paths to absolute
    sandbox = Path(target_dir).resolve()
    target = Path(path).resolve()
    
    # Check if target is within sandbox
    try:
        target.relative_to(sandbox)
    except ValueError:
        raise PermissionError(
            f"🚫 Security violation: Path '{path}' is outside sandbox '{target_dir}'"
        )
    
    return str(target)
```

#### `read_file(path: str, target_dir: str) -> str`
```python
def read_file(path: str, target_dir: str) -> str:
    """
    Read and return file contents (with sandbox validation).
    
    Args:
        path: Absolute or relative path to file
        target_dir: Sandbox directory for validation
        
    Returns:
        File contents as string
        
    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If path is outside sandbox
    """
    # SECURITY: Validate path is within sandbox
    safe_path = validate_path(path, target_dir)
    
    with open(safe_path, 'r', encoding='utf-8') as f:
        return f.read()
```

#### `write_file(path: str, content: str, target_dir: str) -> bool`
```python
def write_file(path: str, content: str, target_dir: str) -> bool:
    """
    Write content to file (with sandbox validation).
    
    Args:
        path: Absolute or relative path to file
        content: Complete file content
        target_dir: Sandbox directory for validation
        
    Returns:
        True if successful
        
    Raises:
        PermissionError: If path is outside sandbox
    """
    # SECURITY: Validate path is within sandbox
    safe_path = validate_path(path, target_dir)
    
    # Create parent directories if needed
    Path(safe_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(safe_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return True
```

#### `list_directory(path: str, target_dir: str) -> list[str]`
```python
def list_directory(path: str, target_dir: str, pattern: str = "*.py") -> list[str]:
    """
    List files matching pattern in directory (with sandbox validation).
    
    Args:
        path: Directory path
        target_dir: Sandbox directory for validation
        pattern: Glob pattern (default: *.py)
        
    Returns:
        List of file paths (all within sandbox)
    """
    # SECURITY: Validate path is within sandbox
    safe_path = validate_path(path, target_dir)
    
    return [str(p) for p in Path(safe_path).rglob(pattern)]
```

### 4.2 Analysis Tools

#### `run_pylint(path: str) -> PylintResult`
```python
from dataclasses import dataclass

@dataclass
class PylintResult:
    score: float           # 0.0 to 10.0
    messages: list[dict]   # Individual issues
    raw_output: str        # Complete output

def run_pylint(path: str, timeout: int = 30) -> PylintResult:
    """
    Run Pylint on file or directory.
    
    Args:
        path: File or directory to analyze
        timeout: Max execution time in seconds
        
    Returns:
        PylintResult with score and messages
        
    Raises:
        TimeoutError: If Pylint hangs
    """
    import subprocess
    import json
    
    result = subprocess.run(
        ["pylint", path, "--output-format=json", "--score=y"],
        capture_output=True,
        text=True,
        timeout=timeout
    )
    
    # Parse output...
    return PylintResult(score=score, messages=messages, raw_output=result.stdout)
```

### 4.3 Test Execution

#### `run_tests(path: str) -> TestResult`
```python
@dataclass
class TestResult:
    passed: int
    failed: int
    errors: int
    skipped: int
    total: int
    success: bool
    output: str
    failures: list[dict]  # Detailed failure info

def run_tests(path: str, timeout: int = 60) -> TestResult:
    """
    Execute pytest on target directory.
    
    Args:
        path: Directory containing tests
        timeout: Max execution time in seconds
        
    Returns:
        TestResult with pass/fail counts and details
        
    Raises:
        TimeoutError: If tests hang
    """
    import subprocess
    
    result = subprocess.run(
        ["pytest", path, "-v", "--tb=short", "-q"],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=path
    )
    
    # Parse output...
    return TestResult(...)
```

---

## 5. Data Flow & State Management

### 5.1 LangGraph State Schema

> **⚠️ SIMPLIFICATION**: The state schema has been simplified to match Doc 1/Doc 2 requirements.
> Complex types like `FixAttempt`, `TestFailure` with full stack traces are NOT required.
> The grader expects minimal state; detailed history is reconstructed from `experiment_data.json`.

```python
from typing import TypedDict, Literal, Annotated
from operator import add

class RefactoringState(TypedDict):
    """
    Minimal state schema - matches grader expectations.
    Detailed action history is logged to experiment_data.json, not stored in state.
    """
    
    # === INPUT ===
    target_dir: str                    # Path to code directory
    
    # === DISCOVERY ===
    files: list[str]                   # List of Python file paths
    
    # === AUDITOR OUTPUT ===
    plan: str                          # Markdown refactoring plan
    pylint_baseline: float             # Initial Pylint score
    
    # === ITERATION TRACKING ===
    current_iteration: int             # Current loop count
    max_iterations: int                # Hard limit (default: 10)
    
    # === FIXER OUTPUT ===
    pylint_current: float              # Latest Pylint score
    
    # === JUDGE OUTPUT ===
    test_results: str                  # Test execution summary
    error_logs: Annotated[list[str], add]  # Accumulated error messages
    
    # === TERMINATION ===
    status: Literal["in_progress", "success", "failure", "max_iterations"]
```

#### Why This Schema is Minimal

| What's Included | Why |
|-----------------|-----|
| `plan` | Needed for Fixer to know what to fix |
| `files` | Needed to iterate over target files |
| `pylint_baseline` / `pylint_current` | Needed to verify score improvement |
| `test_results` / `error_logs` | Needed for Fixer error recovery |
| `current_iteration` / `max_iterations` | Needed to enforce 10-iteration limit |
| `status` | Needed for termination logic |

| What's NOT Included | Why |
|---------------------|-----|
| `FixAttempt` with `changes_summary` | Logged to JSON, not needed in state |
| `TestFailure` with full stack traces | `error_logs` is sufficient |
| `final_summary` | Not required by grader |
| `completion_time` | Timestamp is in logs |
| `files_modified` | Can reconstruct from logs |

> **Principle**: State = minimal data for agent communication. Logs = full history for grading.

### 5.2 Agent Communication Protocol

Agents communicate **exclusively through state**. No direct agent-to-agent calls.

```
┌─────────────────────────────────────────────────────────────────┐
│                           STATE                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Auditor WRITES:           Fixer READS:                        │
│  - plan                    - plan                              │
│  - pylint_baseline         - error_logs                        │
│  - files                   - fix_attempts (to avoid repeats)   │
│                                                                 │
│  Fixer WRITES:             Judge READS:                        │
│  - fix_attempts            - target_dir                        │
│  - pylint_current          - current_iteration                 │
│  - (modifies files)                                            │
│                                                                 │
│  Judge WRITES:             Orchestrator READS:                 │
│  - test_results            - status                            │
│  - error_logs              - current_iteration                 │
│  - status                                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 Plan Format (Structured Markdown)

The Auditor produces a plan in this format:

```markdown
# Refactoring Plan

## Summary
- **Files Analyzed**: 3
- **Total Issues Found**: 12
- **Pylint Baseline Score**: 4.5/10

## File: src/utils.py

### Issue 1: Missing Docstring (Line 1)
- **Type**: `MISSING_DOCSTRING`
- **Severity**: Medium
- **Location**: Module level
- **Description**: Module lacks a docstring
- **Suggested Fix**: Add module docstring describing purpose

### Issue 2: Naming Convention (Line 45-52)
- **Type**: `NAMING_VIOLATION`
- **Severity**: Low
- **Location**: Function `calc`
- **Current**: `def calc(x, y):`
- **Suggested**: `def calculate_total(price, quantity):`
- **Reason**: Function name should be descriptive

### Issue 3: Potential Bug (Line 78)
- **Type**: `BUG`
- **Severity**: High
- **Location**: Function `process_data`
- **Description**: Division by zero possible when `count == 0`
- **Suggested Fix**: Add zero-check before division

## File: src/main.py

### Issue 4: Unused Import (Line 3)
- **Type**: `UNUSED_IMPORT`
- **Severity**: Low
- **Location**: `import os`
- **Suggested Fix**: Remove unused import

...
```

---

## 6. Iteration & Termination Logic

### 6.1 Budget Allocation

| Phase | Iterations | Description |
|-------|------------|-------------|
| Auditor | 1 | Initial analysis (always runs once) |
| Fixer ↔ Judge Loop | 8 max | Self-healing cycle |
| Final | 1 | Reserved for wrap-up |
| **Total** | **10** | Hard limit |

### 6.2 Router Logic

```python
def should_continue(state: RefactoringState) -> Literal["continue", "end"]:
    """Decide whether to continue the Fixer-Judge loop."""
    
    # Success: tests pass
    if state["status"] == "success":
        return "end"
    
    # Max iterations reached
    if state["current_iteration"] >= state["max_iterations"]:
        state["status"] = "max_iterations"
        return "end"
    
    # Continue loop
    return "continue"
```

### 6.3 Success Criteria

```python
def evaluate_success(state: RefactoringState) -> bool:
    """
    Determine if mission is complete.
    
    Primary: All tests pass
    Secondary: Pylint score must IMPROVE (or stay equal)
    """
    # Parse test results
    test_result = parse_test_output(state["test_results"])
    
    # Primary criterion: tests pass
    tests_pass = test_result.failed == 0 and test_result.errors == 0
    
    # Secondary criterion: Pylint score improved
    pylint_improved = state["pylint_current"] >= state["pylint_baseline"]
    
    return tests_pass and pylint_improved
```

#### ⚠️ Pylint Score Rules

| Phase | Requirement |
|-------|-------------|
| Intermediate iterations | Score may temporarily drop (work in progress) |
| **Final iteration** | `pylint_current` **MUST** be ≥ `pylint_baseline` |

> **From Doc 1**: "Le score Pylint a-t-il **augmenté** ?" is part of the 40% Performance grade.

### 6.4 Failure Handling Matrix

| Failure Type | Detection | Recovery |
|--------------|-----------|----------|
| **Syntax error in generated code** | `ast.parse()` fails | Re-prompt Fixer with error |
| **Pylint hangs** | Timeout (30s) | Kill, log warning, continue |
| **Tests hang** | Timeout (60s) | Kill, mark as "untestable" |
| **LLM returns malformed response** | JSON parse error | Retry with clarification |
| **Agent refuses to fix** | Detect "cannot", "impossible" | Force retry with different prompt |
| **Same fix attempted twice** | Hash comparison | Inject "already tried" context |
| **Max iterations reached** | Counter check | Terminate with best effort |

### 6.5 Iteration Tracking

```python
def update_iteration(state: RefactoringState) -> RefactoringState:
    """Increment iteration counter after each Fixer-Judge cycle."""
    state["current_iteration"] += 1
    return state
```

---

## 7. Logging & Telemetry

### 7.1 Required Format

> **⚠️ CRITICAL**: Every significant agent action must be logged, including:
> - LLM calls (prompts and responses)
> - Tool executions (Pylint runs, pytest runs)
> - Routing decisions
> - Error handling
>
> The decorator pattern in 7.4 only covers LLM calls. **Tools must log explicitly.**

All agent actions must be logged using the provided `log_experiment()` function:

```python
from src.utils.logger import log_experiment, ActionType

log_experiment(
    agent_name="Auditor",           # "Auditor" | "Fixer" | "Judge"
    model_used="gemini-1.5-flash",  # Dynamic from config (or "N/A" for tool-only actions)
    action=ActionType.ANALYSIS,     # From ActionType enum
    details={
        "input_prompt": "...",      # REQUIRED: Exact prompt sent to LLM
        "output_response": "...",   # REQUIRED: Raw LLM response
        "file_analyzed": "...",     # Additional context
        "issues_found": 5,
    },
    status="SUCCESS"                # "SUCCESS" | "FAILURE" | "INFO"
)
```

#### 7.1.1 Logging Tool Executions

For non-LLM actions (Pylint, pytest), you must still log with `input_prompt` and `output_response`:

```python
# Example: Logging a Pylint run
log_experiment(
    agent_name="Auditor",
    model_used="N/A",  # No LLM involved
    action=ActionType.ANALYSIS,
    details={
        "input_prompt": f"pylint {file_path} --output-format=json",  # Command executed
        "output_response": pylint_output,  # Raw Pylint output
        "pylint_score": score,
        "file_analyzed": file_path
    },
    status="SUCCESS"
)

# Example: Logging a pytest run
log_experiment(
    agent_name="Judge",
    model_used="N/A",
    action=ActionType.ANALYSIS,
    details={
        "input_prompt": f"pytest {test_path} -v --tb=short",  # Command executed
        "output_response": pytest_output,  # Raw pytest output
        "tests_passed": 5,
        "tests_failed": 2
    },
    status="SUCCESS" if tests_passed else "FAILURE"
)
```

### 7.2 ActionType Mapping

> **⚠️ CRITICAL**: The `ActionType` enum values in `src/utils/logger.py` are:
> - `ActionType.ANALYSIS` → logs as `"CODE_ANALYSIS"`
> - `ActionType.GENERATION` → logs as `"CODE_GEN"`
> - `ActionType.DEBUG` → logs as `"DEBUG"`
> - `ActionType.FIX` → logs as `"FIX"`
>
> Always use the enum (`ActionType.ANALYSIS`), NOT the string value directly.

| Agent | Action | ActionType (use enum) | Logged as |
|-------|--------|----------------------|-----------|
| Auditor | Analyzing code | `ActionType.ANALYSIS` | `CODE_ANALYSIS` |
| Auditor | Running Pylint | `ActionType.ANALYSIS` | `CODE_ANALYSIS` |
| Auditor | Discovering tests | `ActionType.ANALYSIS` | `CODE_ANALYSIS` |
| Fixer | Reading error logs | `ActionType.DEBUG` | `DEBUG` |
| Fixer | Modifying code | `ActionType.FIX` | `FIX` |
| Judge | Generating tests | `ActionType.GENERATION` | `CODE_GEN` |
| Judge | Running tests | `ActionType.ANALYSIS` | `CODE_ANALYSIS` |
| Judge | Analyzing failures | `ActionType.DEBUG` | `DEBUG` |

### 7.3 Log Entry Schema (STRICT - Must Match Logger)

Each entry in `logs/experiment_data.json` must follow this **exact** schema:

```json
{
  "id": "uuid-v4",
  "timestamp": "2026-01-02T15:30:00.000000",
  "agent": "Auditor",
  "model": "gemini-1.5-flash",
  "action": "CODE_ANALYSIS",
  "details": {
    "input_prompt": "You are an expert Python code auditor...",
    "output_response": "I have analyzed the code and found...",
    "files_analyzed": ["utils.py", "main.py"],
    "issues_found": 7,
    "pylint_score": 4.5
  },
  "status": "SUCCESS"
}
```

#### ⚠️ MANDATORY Fields in `details`:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `input_prompt` | `string` | **YES** | Exact prompt sent to LLM |
| `output_response` | `string` | **YES** | Raw LLM response |
| *(others)* | `any` | No | Additional context as needed |

> **CRITICAL**: The logger validates that `input_prompt` and `output_response` exist. If missing, `ValueError` is raised and the program crashes.

#### Field Naming Convention: **snake_case**

| ✅ Correct | ❌ Wrong |
|-----------|----------|
| `input_prompt` | `inputPrompt` |
| `output_response` | `outputResponse` |
| `files_analyzed` | `filesAnalyzed` |
| `issues_found` | `issuesFound` |
| `pylint_score` | `pylintScore` |

### 7.4 Logging Wrapper

```python
from functools import wraps
from src.utils.logger import log_experiment, ActionType

def log_agent_action(agent_name: str, action_type: ActionType):
    """Decorator to automatically log agent LLM calls."""
    def decorator(func):
        @wraps(func)
        def wrapper(prompt: str, *args, **kwargs):
            try:
                response = func(prompt, *args, **kwargs)
                log_experiment(
                    agent_name=agent_name,
                    model_used=get_model_name(),
                    action=action_type,
                    details={
                        "input_prompt": prompt,
                        "output_response": response,
                        **kwargs.get("extra_details", {})
                    },
                    status="SUCCESS"
                )
                return response
            except Exception as e:
                log_experiment(
                    agent_name=agent_name,
                    model_used=get_model_name(),
                    action=action_type,
                    details={
                        "input_prompt": prompt,
                        "output_response": str(e),
                        "error": str(e)
                    },
                    status="FAILURE"
                )
                raise
        return wrapper
    return decorator
```

---

## 8. LLM Provider Interface

### 8.1 Abstraction Layer

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str

@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict  # token counts

class LLMProvider(Protocol):
    """Protocol for LLM providers (Gemini, OpenAI, etc.)"""
    
    @property
    def model_name(self) -> str:
        """Return the model identifier for logging."""
        ...
    
    def complete(
        self, 
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> LLMResponse:
        """Generate completion from messages."""
        ...
```

### 8.2 Gemini Implementation

```python
import google.generativeai as genai
from typing import Optional

class GeminiProvider:
    """Google Gemini LLM provider."""
    
    def __init__(
        self, 
        api_key: str,
        model: str = "gemini-1.5-flash"
    ):
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model)
        self._model_name = model
    
    @property
    def model_name(self) -> str:
        return self._model_name
    
    def complete(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> LLMResponse:
        # Convert messages to Gemini format
        prompt = self._format_messages(messages)
        
        response = self._model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
        )
        
        return LLMResponse(
            content=response.text,
            model=self._model_name,
            usage={"prompt_tokens": 0, "completion_tokens": 0}  # Gemini doesn't expose this easily
        )
    
    def _format_messages(self, messages: list[Message]) -> str:
        """Convert message list to single prompt."""
        parts = []
        for msg in messages:
            if msg.role == "system":
                parts.append(f"Instructions: {msg.content}\n")
            elif msg.role == "user":
                parts.append(f"User: {msg.content}\n")
            elif msg.role == "assistant":
                parts.append(f"Assistant: {msg.content}\n")
        return "\n".join(parts)
```

### 8.3 Configuration

```python
# src/config.py
import os
from dataclasses import dataclass

@dataclass
class Config:
    # LLM
    llm_provider: str = "gemini"
    llm_model: str = "gemini-1.5-flash"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096
    
    # Iteration limits
    max_iterations: int = 10
    
    # Timeouts (seconds)
    pylint_timeout: int = 30
    test_timeout: int = 60
    llm_timeout: int = 120
    
    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            llm_model=os.getenv("LLM_MODEL", "gemini-1.5-flash"),
            # ... other env vars
        )

def get_llm_provider(config: Config) -> LLMProvider:
    """Factory function for LLM provider."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")
    
    if config.llm_provider == "gemini":
        return GeminiProvider(api_key, config.llm_model)
    else:
        raise ValueError(f"Unknown provider: {config.llm_provider}")
```

---

## 9. Project Structure

### 9.1 Directory Layout

```
/tp-igl
├── main.py                      # [LOCKED] Entry point
├── requirements.txt             # [LOCKED] Dependencies
├── check_setup.py               # [LOCKED] Environment check
├── .env                         # API keys (gitignored)
├── .env.example                 # Template
├── .gitignore
│
├── /src
│   ├── __init__.py
│   │
│   ├── /agents                  # Agent implementations
│   │   ├── __init__.py
│   │   ├── base.py              # Base agent class
│   │   ├── auditor.py           # Auditor agent
│   │   ├── fixer.py             # Fixer agent
│   │   └── judge.py             # Judge agent
│   │
│   ├── /tools                   # Tool implementations
│   │   ├── __init__.py
│   │   ├── file_ops.py          # read_file, write_file, list_directory
│   │   ├── pylint_tool.py       # run_pylint
│   │   └── test_runner.py       # run_tests
│   │
│   ├── /prompts                 # System prompts
│   │   ├── __init__.py
│   │   ├── auditor_prompt.py    # Auditor system prompt
│   │   ├── fixer_prompt.py      # Fixer system prompt
│   │   └── judge_prompt.py      # Judge system prompt
│   │
│   ├── /llm                     # LLM provider abstraction
│   │   ├── __init__.py
│   │   ├── base.py              # Protocol/ABC
│   │   └── gemini.py            # Gemini implementation
│   │
│   ├── /graph                   # LangGraph orchestration
│   │   ├── __init__.py
│   │   ├── state.py             # State schema
│   │   ├── nodes.py             # Node functions
│   │   └── builder.py           # Graph construction
│   │
│   ├── /utils                   # Utilities
│   │   ├── __init__.py
│   │   └── logger.py            # [PROVIDED] Logging
│   │
│   └── config.py                # Configuration
│
├── /logs
│   ├── .gitkeep
│   └── experiment_data.json     # [TRACKED] Output
│
├── /sandbox                     # [GITIGNORED] Working directory
│
├── /tests                       # Project tests (optional)
│   ├── __init__.py
│   ├── test_tools.py
│   ├── test_agents.py
│   └── test_integration.py
│
└── /docs
    ├── ENONCE.md
    ├── SPEC.md                  # This document
    └── *.pdf
```

### 9.2 Module Responsibilities

| Module | Owner Role | Responsibility |
|--------|------------|----------------|
| `main.py` | Orchestrator | CLI parsing, graph execution |
| `src/graph/*` | Orchestrator | LangGraph state machine |
| `src/tools/*` | Toolsmith | Tool implementations, sandboxing |
| `src/prompts/*` | Prompt Engineer | System prompts |
| `src/agents/*` | Shared | Agent logic (uses tools + prompts) |
| `src/llm/*` | Toolsmith | LLM provider abstraction |
| `src/utils/logger.py` | Data Officer | Logging (provided) |
| `src/config.py` | Orchestrator | Configuration management |

---

## 10. Implementation Roadmap

### 10.1 Phase 1: Core Tools (Days 1-3)

**Owner**: Toolsmith

| Task | Priority | Deliverable |
|------|----------|-------------|
| Implement `read_file()` | High | `src/tools/file_ops.py` |
| Implement `write_file()` | High | `src/tools/file_ops.py` |
| Implement `list_directory()` | High | `src/tools/file_ops.py` |
| Implement `run_pylint()` | High | `src/tools/pylint_tool.py` |
| Implement `run_tests()` | High | `src/tools/test_runner.py` |
| Add timeout handling | Medium | All tools |
| Add path validation | Medium | `src/tools/file_ops.py` |

**Acceptance Criteria**:
- All tools work standalone
- Timeouts prevent hangs
- Tools only access `target_dir`

### 10.2 Phase 2: Agents (Days 3-6)

**Owner**: Prompt Engineer + Toolsmith

| Task | Priority | Deliverable |
|------|----------|-------------|
| Write Auditor system prompt | High | `src/prompts/auditor_prompt.py` |
| Write Fixer system prompt | High | `src/prompts/fixer_prompt.py` |
| Write Judge system prompt | High | `src/prompts/judge_prompt.py` |
| Implement LLM provider | High | `src/llm/gemini.py` |
| Implement Auditor agent | High | `src/agents/auditor.py` |
| Implement Fixer agent | High | `src/agents/fixer.py` |
| Implement Judge agent | High | `src/agents/judge.py` |

**Acceptance Criteria**:
- Each agent works in isolation
- Prompts produce consistent output format
- Logging works correctly

### 10.3 Phase 3: Orchestration (Days 6-9)

**Owner**: Orchestrator

| Task | Priority | Deliverable |
|------|----------|-------------|
| Define state schema | High | `src/graph/state.py` |
| Implement node functions | High | `src/graph/nodes.py` |
| Build graph | High | `src/graph/builder.py` |
| Implement router logic | High | `src/graph/nodes.py` |
| Wire up `main.py` | High | `main.py` |
| Add iteration tracking | Medium | `src/graph/nodes.py` |

**Acceptance Criteria**:
- Full pipeline runs end-to-end
- State flows correctly between agents
- Iteration limit enforced

### 10.4 Phase 4: Testing & Hardening (Days 9-12)

**Owner**: Data Officer + All

| Task | Priority | Deliverable |
|------|----------|-------------|
| Create test dataset | High | `sandbox/test_cases/` |
| Validate JSON logging | High | Manual verification |
| Test edge cases | High | Various |
| Performance testing | Medium | Timing logs |
| Error recovery testing | Medium | Various |
| Final integration test | High | Full run |

**Acceptance Criteria**:
- System handles "trap" files gracefully
- `experiment_data.json` is valid and complete
- No infinite loops
- Graceful degradation on failures

### 10.5 Milestone Schedule

| Day | Milestone |
|-----|-----------|
| 3 | All tools implemented and tested |
| 6 | All agents working in isolation |
| 9 | Full pipeline operational |
| 12 | Hardened and submission-ready |
| 14 | Buffer / polish |

---

## 11. Open Questions (TBD)

### ~~11.1 Test Generation~~ ✅ RESOLVED

**Answer from Professor (Jan 2026)**:
- The hidden dataset has NO existing tests
- Judge Agent MUST generate tests (TDD approach)
- Final grading uses professor's hidden tests
- Your generated tests validate the Fixer's corrections

### 11.1b Functional Correctness ✅ RESOLVED (Additional Clarification - Jan 2026)

**Professor's Answer**:
> "OUI, l'Agent Testeur doit absolument générer des assertions qui valident la logique métier (Functional Correctness)."

**Key Points**:
1. The Judge Agent must NOT only test syntax and execution
2. The Judge must perform **SEMANTIC ANALYSIS** of function names to understand INTENT
3. Tests must verify that functions return **CORRECT VALUES** (business logic)

**Example Workflow**:
```
1. Function name: "calculate_average" 
   → Agent infers: "intention is to calculate a MEAN"

2. Agent generates test:
   assert calculate_average([10, 20]) == 15

3. Buggy code returns 30 (sum instead of mean)
   → Test FAILS: "Expected 15, got 30"

4. Fixer Agent receives error and deduces:
   → "Missing division by length" → Fixes the code
```

**⚠️ WARNING from Professor**:
> "Si vos tests vérifie uniquement la syntaxe et l'exécution, vous ne détecterez jamais ces bugs de 'logique', et votre correction sera rejetée par le Bot de Correction final."

**Impact**: If tests only check that code runs without errors, logic bugs will go undetected and **final grade will be 0 for Performance**.

### 11.2 External Dependencies

**Question**: What if target code imports libraries not in `requirements.txt`?

**Options**:
- A) Attempt to install missing dependencies
- B) Skip files with unresolvable imports
- C) Fail with clear error

**Recommendation**: Option B (graceful degradation)

### 11.3 Circular Imports

**Question**: How to handle circular import errors in target code?

**Recommendation**: Log as unfixable, skip file, continue with others.

### 11.4 Test Quality Assurance

**Question**: How to ensure Judge-generated tests are valid and meaningful?

**Options**:
- A) Judge validates its own tests compile before running
- B) Use simple assertion patterns only
- C) Generate multiple test cases per issue

**Recommendation**: All three - validate syntax, keep tests simple, cover edge cases.

---

## Appendix A: System Prompts

### A.1 Auditor System Prompt

```python
AUDITOR_SYSTEM_PROMPT = """
You are The Auditor, an expert Python code analyst. Your mission is to analyze code and produce a detailed refactoring plan.

## Your Capabilities
- Deep understanding of Python best practices (PEP 8, PEP 257)
- Static analysis interpretation (Pylint)
- Bug pattern recognition
- Code smell detection

## Your Task
1. Analyze all Python files in the target directory
2. Review Pylint output for each file
3. Identify issues in these categories:
   - SYNTAX_ERROR: Code that won't parse
   - BUG: Logic errors, potential runtime failures
   - NAMING_VIOLATION: Non-PEP8 names
   - MISSING_DOCSTRING: Undocumented modules/classes/functions
   - UNUSED_CODE: Unused imports, variables, functions
   - COMPLEXITY: Overly complex code
   - TYPE_HINT: Missing type annotations

## Output Format
You MUST output a structured Markdown plan following this exact format:

```markdown
# Refactoring Plan

## Summary
- **Files Analyzed**: <count>
- **Total Issues Found**: <count>
- **Pylint Baseline Score**: <score>/10

## File: <path>

### Issue <N>: <Title> (Line <line_number>)
- **Type**: `<ISSUE_TYPE>`
- **Severity**: High | Medium | Low
- **Location**: <specific location>
- **Description**: <what's wrong>
- **Suggested Fix**: <how to fix>
```

## Rules
- Be thorough but prioritize HIGH severity issues
- Always include line numbers
- Provide actionable fix suggestions
- Do not modify any files yourself
- Output ONLY the Markdown plan, no other text
"""
```

### A.2 Fixer System Prompt

```python
FIXER_SYSTEM_PROMPT = """
You are The Fixer, an expert Python developer. Your mission is to repair code based on the refactoring plan.

## Your Capabilities
- Expert Python programming
- Bug fixing
- Code refactoring
- Following coding standards

## Your Task
1. Read the refactoring plan from The Auditor
2. Read any error logs from The Judge (if this is a retry)
3. For each file with issues:
   a. Read the current file content
   b. Apply the necessary fixes
   c. Output the COMPLETE fixed file

## Input Context
You will receive:
- The refactoring plan (Markdown)
- The current file content
- Previous error logs (if any)
- List of previous fix attempts (to avoid repeating)

## Output Format
For each file you fix, output:

```
### FILE: <path>
```python
<complete file content with all fixes applied>
```
```

## Rules
- Output the COMPLETE file content, not just changes
- Fix ALL issues mentioned in the plan for that file
- Maintain the original code's functionality
- Follow PEP 8 style guidelines
- Add docstrings where missing
- If error logs mention a specific failure, prioritize fixing that
- Do NOT repeat a fix that already failed (check previous attempts)
- If you cannot fix something, leave a TODO comment explaining why

## Error Recovery
If you receive error logs from The Judge:
1. Parse the error message carefully
2. Identify the root cause
3. Apply a DIFFERENT fix than previous attempts
4. If stuck after 3 attempts on same issue, mark as unfixable
"""
```

### A.3 Judge System Prompt (Test Generation Mode)

```python
JUDGE_GENERATE_PROMPT = """
You are The Judge, an expert test engineer. Your mission is to CREATE unit tests that validate code correctness using TDD principles.

## CRITICAL CONTEXT
The code you are testing has NO existing tests. You must GENERATE tests based on The Auditor's refactoring plan. Your tests should:
1. FAIL on the current buggy code (proving the bug exists)
2. PASS once The Fixer corrects the code

## ⚠️ CRITICAL: Functional Correctness (Mandatory)

You MUST test the BUSINESS LOGIC, not just error handling!

### Semantic Analysis Process:
1. Read the function NAME to understand its INTENT
2. Generate tests that verify the function produces CORRECT results
3. Don't just test edge cases - test the CORE functionality

### Example:
- Function name: `calculate_average`
- Intent: Calculate the MEAN (sum divided by count)
- Test: `assert calculate_average([10, 20]) == 15`  # NOT 30!

If the code returns 30 (sum instead of average), your test MUST catch this!

## Your Capabilities
- Expert in pytest and Python testing
- Understanding of TDD (Test-Driven Development)
- Ability to write tests that expose specific bugs
- **Semantic analysis of function names to infer intent**

## Your Task
1. Read The Auditor's refactoring plan
2. For each identified bug/issue, write a test that:
   - Tests the EXPECTED correct behavior
   - Will FAIL on buggy code
   - Will PASS on correct code
3. Save tests to `{target_dir}/tests/test_<module>.py`
4. Run the tests (expect failures - this confirms bugs exist)

## Test Generation Rules
- One test file per source module
- Use descriptive test names: `test_<function>_<scenario>`
- Include both positive tests (expected behavior) and edge cases
- Keep tests simple and focused
- Add docstrings explaining what each test validates

## Output Format
```python
# tests/test_<module>.py
\"\"\"Generated tests for <module>.py\"\"\"
import pytest
from <module> import <functions>

class Test<ClassName>:
    \"\"\"Tests for <ClassName> functionality.\"\"\"
    
    def test_<function>_normal_case(self):
        \"\"\"Test that <function> works for normal inputs.\"\"\"
        # Arrange
        input_value = ...
        expected = ...
        
        # Act
        result = <function>(input_value)
        
        # Assert
        assert result == expected
    
    def test_<function>_edge_case(self):
        \"\"\"Test that <function> handles <edge case> correctly.\"\"\"
        with pytest.raises(ValueError, match="expected error message"):
            <function>(edge_case_input)
```

## Example: If Auditor found "Logic bug in calculate_average() - returns sum instead of mean"
```python
# tests/test_math_utils.py
\"\"\"Generated tests for math_utils.py - Tests FUNCTIONAL CORRECTNESS\"\"\"
import pytest
from math_utils import calculate_average

class TestCalculateAverage:
    \"\"\"Tests for calculate_average() function.\"\"\"
    
    # ========== FUNCTIONAL CORRECTNESS TESTS (CRITICAL) ==========
    
    def test_calculate_average_returns_mean_not_sum(self):
        \"\"\"
        CRITICAL: Test that function returns MEAN, not SUM.
        Function name 'calculate_average' implies division by count.
        \"\"\"
        # If buggy code returns 30 (sum), this will fail with:
        # "AssertionError: assert 30 == 15"
        assert calculate_average([10, 20]) == 15.0
    
    def test_calculate_average_single_element(self):
        \"\"\"Test average of single element equals that element.\"\"\"
        assert calculate_average([42]) == 42.0
    
    def test_calculate_average_multiple_elements(self):
        \"\"\"Test average calculation with multiple elements.\"\"\"
        assert calculate_average([1, 2, 3, 4, 5]) == 3.0
        assert calculate_average([10, 20, 30]) == 20.0
    
    # ========== ERROR HANDLING TESTS ==========
    
    def test_calculate_average_empty_list_raises(self):
        \"\"\"Test that empty list raises appropriate error.\"\"\"
        with pytest.raises((ValueError, ZeroDivisionError)):
            calculate_average([])
```

## Example: If Auditor found "Division by zero bug in divide()"
```python
# tests/test_calculator.py
\"\"\"Generated tests for calculator.py\"\"\"
import pytest
from calculator import divide

class TestDivide:
    \"\"\"Tests for divide() function.\"\"\"
    
    # ========== FUNCTIONAL CORRECTNESS TESTS ==========
    
    def test_divide_normal_operation(self):
        \"\"\"Test that divide works for valid inputs.\"\"\"
        assert divide(10, 2) == 5
        assert divide(9, 3) == 3
        assert divide(7, 2) == 3.5
    
    # ========== ERROR HANDLING TESTS ==========
    
    def test_divide_by_zero_raises_error(self):
        \"\"\"Test that divide raises ValueError for zero divisor.\"\"\"
        with pytest.raises(ValueError, match="[Cc]annot divide by zero"):
            divide(10, 0)
    
    def test_divide_negative_numbers(self):
        \"\"\"Test divide handles negative numbers correctly.\"\"\"
        assert divide(-10, 2) == -5
        assert divide(10, -2) == -5
```

## Rules
- Generate tests BEFORE fixes are applied
- Tests should be runnable with `pytest {target_dir}/tests/`
- Do not test implementation details, test behavior
- Create `tests/__init__.py` if it doesn't exist
"""
```

### A.4 Judge System Prompt (Validation Mode)

```python
JUDGE_VALIDATE_PROMPT = """
You are The Judge, a strict test validator. Your mission is to run the generated tests and determine if fixes are successful.

## Your Task
1. Execute pytest on the generated tests
2. Analyze the results
3. If all tests pass: Declare SUCCESS
4. If tests fail: Extract useful error context for The Fixer

## Output Format

### If SUCCESS:
```
STATUS: SUCCESS
SUMMARY: All <N> tests passed.
PYLINT_SCORE: <current_score>/10 (baseline: <baseline_score>/10)
TESTS_PASSED: <list of passing tests>
```

### If FAILURE:
```
STATUS: FAILURE
SUMMARY: <passed>/<total> tests passed, <failed> failed.

FAILURES:
### Test: <test_name>
- **File**: <test_file>
- **Error**: <error_type>
- **Message**: <error_message>
- **Expected**: <what the test expected>
- **Actual**: <what actually happened>
- **Relevant Code**:
```python
<the failing test code>
```
- **Stack Trace** (last 5 lines):
```
<stack trace>
```

SUGGESTION: <specific hint for The Fixer based on the failure>
```

## Rules
- Be precise about which tests failed and why
- Include enough context for The Fixer to understand the issue
- Do NOT modify tests or source code
- If tests timeout, report as TIMEOUT not FAILURE
- Track iteration number for context compression
- Prioritize the most critical failures first
"""
```

---

## Appendix B: Example Refactoring Plan

```markdown
# Refactoring Plan

## Summary
- **Files Analyzed**: 2
- **Total Issues Found**: 7
- **Pylint Baseline Score**: 3.5/10

---

## File: src/calculator.py

### Issue 1: Missing Module Docstring (Line 1)
- **Type**: `MISSING_DOCSTRING`
- **Severity**: Medium
- **Location**: Module level
- **Description**: The module lacks a docstring explaining its purpose
- **Suggested Fix**: Add a module docstring at the top of the file

### Issue 2: Naming Convention Violation (Line 5)
- **Type**: `NAMING_VIOLATION`
- **Severity**: Low
- **Location**: Function `calc`
- **Current**: `def calc(a, b):`
- **Suggested**: `def calculate_sum(first_number, second_number):`
- **Reason**: Function and parameter names should be descriptive

### Issue 3: Division by Zero Bug (Line 12)
- **Type**: `BUG`
- **Severity**: High
- **Location**: Function `divide`, Line 12
- **Description**: No check for division by zero
- **Current Code**:
```python
def divide(a, b):
    return a / b
```
- **Suggested Fix**: 
```python
def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
```

### Issue 4: Unused Import (Line 2)
- **Type**: `UNUSED_CODE`
- **Severity**: Low
- **Location**: `import sys`
- **Suggested Fix**: Remove the unused import

---

## File: src/utils.py

### Issue 5: Missing Type Hints (Line 8-15)
- **Type**: `TYPE_HINT`
- **Severity**: Medium
- **Location**: Function `process_data`
- **Description**: Function lacks type annotations
- **Current**: `def process_data(data):`
- **Suggested**: `def process_data(data: list[dict]) -> dict:`

### Issue 6: Bare Except Clause (Line 22)
- **Type**: `BUG`
- **Severity**: High
- **Location**: Line 22
- **Description**: Bare `except:` catches all exceptions including KeyboardInterrupt
- **Current Code**:
```python
try:
    result = risky_operation()
except:
    pass
```
- **Suggested Fix**:
```python
try:
    result = risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    result = None
```

### Issue 7: Complex Function (Line 30-75)
- **Type**: `COMPLEXITY`
- **Severity**: Medium
- **Location**: Function `handle_request`
- **Description**: Function has cyclomatic complexity of 15 (threshold: 10)
- **Suggested Fix**: Extract nested conditionals into helper functions

---

## Priority Order
1. **HIGH**: Issue 3 (Division by Zero) - Runtime crash
2. **HIGH**: Issue 6 (Bare Except) - Swallows errors
3. **MEDIUM**: Issue 5 (Type Hints) - Maintainability
4. **MEDIUM**: Issue 7 (Complexity) - Maintainability
5. **MEDIUM**: Issue 1 (Docstring) - Documentation
6. **LOW**: Issue 2 (Naming) - Style
7. **LOW**: Issue 4 (Unused Import) - Cleanup
```

---

## Appendix C: State Schema

### C.1 Simplified TypedDict Definition (Recommended)

> **Note**: This simplified schema matches grader expectations. Complex types are NOT required.

```python
from typing import TypedDict, Literal, Annotated
from operator import add

class RefactoringState(TypedDict):
    """
    Minimal state for agent communication.
    Full action history is logged to experiment_data.json.
    """
    # === INPUT ===
    target_dir: str
    
    # === DISCOVERY ===
    files: list[str]
    
    # === AUDITOR OUTPUT ===
    plan: str
    pylint_baseline: float
    
    # === ITERATION TRACKING ===
    current_iteration: int
    max_iterations: int  # Default: 10
    
    # === FIXER OUTPUT ===
    pylint_current: float
    
    # === JUDGE OUTPUT ===
    generated_tests: list[str]  # Paths to generated test files
    test_results: str
    error_logs: Annotated[list[str], add]  # Append-only
    
    # === TERMINATION ===
    status: Literal["in_progress", "success", "failure", "max_iterations"]
```

### C.2 State Initialization

```python
def initialize_state(target_dir: str) -> RefactoringState:
    """Create initial state for the refactoring graph."""
    return RefactoringState(
        target_dir=target_dir,
        files=[],
        plan="",
        pylint_baseline=0.0,
        current_iteration=0,
        max_iterations=10,
        pylint_current=0.0,
        generated_tests=[],
        test_results="",
        error_logs=[],
        status="in_progress",
    )
```

### C.3 Simplified Helpers

```python
def add_error_log(state: RefactoringState, error: str) -> RefactoringState:
    """Add an error message to the error logs."""
    state["error_logs"].append(error)
    return state

def increment_iteration(state: RefactoringState) -> RefactoringState:
    """Increment the iteration counter."""
    state["current_iteration"] += 1
    return state

def check_pylint_improvement(state: RefactoringState) -> bool:
    """Check if Pylint score has improved (required for success)."""
    return state["pylint_current"] >= state["pylint_baseline"]
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-02 | Team | Initial specification |
| 1.1.0 | 2026-01-09 | Team | Added Professor's clarification on Functional Correctness: Judge must test business logic, not just error handling. Added semantic analysis examples for function name → intent inference. |
| 1.2.0 | 2026-01-09 | Team | **Major fixes based on peer review**: (1) Fixed ActionType mapping to match logger.py enum values, (2) Standardized log schema with snake_case fields, (3) Added logging requirement for ALL actions including tools, (4) Fixed Pylint score requirement to IMPROVE not just track, (5) Simplified State Schema to match grader expectations, (6) Added mandatory path validation/sandboxing for file operations |

---

*End of Technical Specification*
