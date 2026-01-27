"""
LangGraph builder for The Refactoring Swarm.

Constructs and compiles the state graph for orchestrating agents.
"""

from langgraph.graph import StateGraph, END

from src.graph.state import RefactoringState
from src.graph.nodes import (
    auditor_node,
    judge_generate_tests_node,
    fixer_node,
    judge_validate_node,
    should_continue,
)


def build_graph() -> StateGraph:
    """
    Build the refactoring state graph.

    The graph follows a TDD workflow:
    1. Auditor analyzes code and creates refactoring plan
    2. Judge generates tests (that should FAIL on buggy code)
    3. Fixer applies fixes
    4. Judge validates (runs tests)
    5. Loop back to Fixer if tests fail, or END if tests pass

    Graph Structure:
        auditor → judge_generate → fixer → judge_validate
                                     ↑              |
                                     └──────────────┘ (if tests fail)
    """
    # Create the graph with our state schema
    graph = StateGraph(RefactoringState)

    # Add nodes
    graph.add_node("auditor", auditor_node)
    graph.add_node("judge_generate", judge_generate_tests_node)
    graph.add_node("fixer", fixer_node)
    graph.add_node("judge_validate", judge_validate_node)

    # Set entry point
    graph.set_entry_point("auditor")

    # Add edges (TDD Flow)
    graph.add_edge("auditor", "judge_generate")  # Auditor → Judge generates tests
    graph.add_edge("judge_generate", "fixer")  # Judge → Fixer (with failing tests)
    graph.add_edge("fixer", "judge_validate")  # Fixer → Judge validates

    # Conditional edge: Loop or End
    graph.add_conditional_edges(
        "judge_validate",
        should_continue,
        {
            "continue": "fixer",  # Tests failed → back to Fixer
            "end": END,  # Tests passed → done!
        },
    )

    return graph


def compile_graph():
    """
    Compile the graph and return an executable.

    Returns:
        Compiled LangGraph application ready to invoke
    """
    graph = build_graph()
    return graph.compile()
