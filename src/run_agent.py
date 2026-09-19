"""
UN SDG AI Analytics Platform — interactive CLI for the LangChain SQL agent.

Run from PowerShell (from the project root):
    python src/run_agent.py                              # interactive loop
    python src/run_agent.py "Which countries are ..."     # single question, then exit

Requires:
    pip install langchain langchain-community langchain-anthropic anthropic
    $env:ANTHROPIC_API_KEY = "sk-ant-..."
    data/processed/sdg_analytics.db already built (notebooks/02_database_build.ipynb)

Every question is logged to logs/agent_queries.jsonl (question, SQL attempts,
SQL results, final answer) via sql_agent.ask_and_log.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    try:
        from sql_agent import build_agent, ask_and_log, DB_PATH, LOG_PATH
        from entity_resolver import load_entities, resolve_entities
    except ImportError as e:
        print("Missing dependency:", e)
        print("Run: pip install langchain langchain-community langchain-anthropic anthropic")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set in this shell.")
        print('Run: $env:ANTHROPIC_API_KEY = "sk-ant-..."')
        sys.exit(1)

    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        print("Build it first: run notebooks/02_database_build.ipynb")
        sys.exit(1)

    print(f"Connecting to {DB_PATH} ...")
    agent = build_agent(verbose=False)   # reasoning trace goes to the log file, not the terminal
    entities = load_entities(DB_PATH)
    print(f"Ready. Every question is logged to {LOG_PATH}\n")

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        question = resolve_entities(question, entities)
        result = ask_and_log(agent, question)
        print("\nAnswer:", result["answer"])
        _print_tokens(result)
        return

    print("Type a question, or 'quit' to exit.\n")
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if question.lower() in ("quit", "exit", "q"):
            break
        if not question:
            continue
        try:
            question = resolve_entities(question, entities)
            result = ask_and_log(agent, question)
            print("\nAnswer:", result["answer"])
            _print_tokens(result)
        except Exception as e:
            print(f"\nError: {e}\n")


def _print_tokens(result):
    print(
        f"[tokens] {result['input_tokens']:,} in / {result['output_tokens']:,} out "
        f"= {result['total_tokens']:,} total ({result['llm_calls']} LLM calls this run)\n"
    )


if __name__ == "__main__":
    main()
