"""
UN SDG AI Analytics Platform — LangChain SQL Agent
Allows plain-English policy questions to be answered via SQLite.

Usage (in notebooks/05_ai_agent_demo.ipynb):
    from src.sql_agent import build_agent, ask

    agent = build_agent()
    ask(agent, "Which Sub-Saharan African countries improved most in SDG 3 since 2015?")

Built on LangGraph's create_react_agent (langgraph.prebuilt), not the legacy
langchain_community create_sql_agent/AgentExecutor. The legacy path constructs
its prompt in a way that can end the conversation on an assistant-role message
("prefill") — a pattern current Claude models (Opus 4.8+, Sonnet 5, Fable 5)
reject outright with a 400. create_react_agent uses native tool-calling
messages throughout, which doesn't hit this.
"""

import os
import json
import datetime
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed', 'sdg_analytics.db')
LOG_PATH = os.path.join(os.path.dirname(__file__), '..', 'logs', 'agent_queries.jsonl')
MODEL_NAME = "claude-sonnet-5"

SYSTEM_PROMPT_TEMPLATE = (
    "You are an expert in UN Sustainable Development Goals data. "
    "The database contains SDG indicator values for 193 countries from 2000-2025, "
    "SDG Index scores from 2000-2026 (Sustainable Development Report), "
    "and World Bank enrichment data (income group, GDP per capita). "
    "\n\nThe exact schema is already given below - do NOT call sql_db_list_tables or "
    "sql_db_schema, they are redundant with this and just waste a turn. Only fall back "
    "to them if you need a table not covered here.\n\n"
    "{schema}\n\n"
    "Never guess table or column names or the exact spelling of category values like "
    "region names - read them from the schema/sample rows above. "
    "If you need to match country names, fetch them all in a single query - e.g. "
    "SELECT country_code, country_name, region FROM countries - and find the match(es) "
    "yourself from the returned list. Never issue multiple guess-and-check queries "
    "(e.g. repeated LIKE '%...%' searches) to hunt for how a name is spelled - that wastes "
    "a full round trip per guess. "
    "Verify a query with the query-checker tool before running it. "
    "Always join country names for readable output. "
    "Note data gaps honestly - many countries have incomplete indicator coverage. "
    "Provide concise, policy-relevant answers."
)


def build_agent(db_path: str = DB_PATH, verbose: bool = True):
    """
    Build a LangGraph ReAct agent backed by the SDG SQLite database.

    The agent can:
    1. Inspect the schema (table names, columns, sample rows)
    2. Write a SQL query for the user's question
    3. Execute the query against the SQLite database
    4. Observe the result and decide if it's sufficient
    5. Refine and re-query if needed
    6. Return a natural-language answer

    This is the "agent" pattern - multi-step reasoning, not one-shot text-to-SQL.
    """
    db = SQLDatabase.from_uri(
        f"sqlite:///{db_path}",
        include_tables=[
            'countries', 'sdg_goals', 'sdg_indicators',
            'sdg_values', 'sdg_index_scores'
        ],
        sample_rows_in_table_info=1    # a taste of real data values, without tripling schema tokens
    )

    llm = ChatAnthropic(
        model=MODEL_NAME, #"claude-opus-4-8",
        # no `temperature` - this model tier rejects it (400): fixed temperature is
        # replaced by adaptive thinking, on by default, nothing to configure here.
        # The real driver of cost in this agent isn't schema/result size - it's that
        # EVERY tool-calling turn pays for a thinking pass, and each turn resends prior
        # turns' thinking-replay data along with the growing history, so cost compounds
        # with turn count. "low" (tried first) cut cost per turn but produced more
        # empty-result query retries - not worth it once entity_resolver.py already
        # removes the name-guessing turns. "medium" as a middle ground between that
        # and the full default ("high" for Sonnet 5) - revisit based on logged
        # llm_calls / retry counts once there's more than one run to compare.
        reasoning_effort="medium",
        max_tokens=2048
    )

    tools = SQLDatabaseToolkit(db=db, llm=llm).get_tools()

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(schema=db.get_table_info())
    agent = create_react_agent(llm, tools, prompt=system_prompt)
    agent.verbose = verbose    # read back by ask()/ask_and_log() to print the reasoning trail
    return agent


def _print_trace(messages):
    """Print each tool call and tool result as the agent made them - the reasoning trail."""
    for msg in messages:
        kind = msg.__class__.__name__
        if kind == "AIMessage":
            if getattr(msg, "tool_calls", None):
                for tc in msg.tool_calls:
                    print(f"\n[agent] calling `{tc['name']}` with: {tc['args']}")
            elif msg.content:
                print(f"\n[agent] {msg.content}")
        elif kind == "ToolMessage":
            content = str(msg.content)
            preview = content if len(content) < 500 else content[:500] + " ...(truncated)"
            print(f"[result] {preview}")


def _answer_text(content) -> str:
    """
    Normalize an AIMessage's .content to plain text. On models with thinking
    on by default (e.g. Sonnet 5), .content is a list of blocks - a
    "thinking" block plus a "text" block - instead of a plain string. Join
    just the text block(s) and drop the thinking block (its content is
    empty anyway under the default "omitted" display setting, and its
    "signature" field is opaque replay metadata, not useful in logs).
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content)


def _extract_sql_attempts(messages):
    """Pair each sql_db_query tool call with its result, in call order."""
    pending = {}
    attempts = []
    for msg in messages:
        if msg.__class__.__name__ == "AIMessage" and getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                if tc["name"] == "sql_db_query":
                    pending[tc["id"]] = tc["args"].get("query", json.dumps(tc["args"]))
        elif msg.__class__.__name__ == "ToolMessage":
            call_id = getattr(msg, "tool_call_id", None)
            if call_id in pending:
                attempts.append({"query": pending[call_id], "result": str(msg.content)})
    return attempts


def _sum_usage(messages):
    """
    Sum token usage across every LLM call in this agent run, not just the
    final one - each tool-calling round trip is a separate call to the
    model, and each resends the growing conversation history, so the real
    cost of a run is the sum across all of them.
    """
    input_tokens = output_tokens = 0
    llm_calls = 0
    for msg in messages:
        usage = getattr(msg, "usage_metadata", None)
        if usage:
            input_tokens += usage.get("input_tokens", 0)
            output_tokens += usage.get("output_tokens", 0)
            llm_calls += 1
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "llm_calls": llm_calls,
    }


def ask(agent, question: str) -> str:
    """Run a natural-language question through the agent and return the answer."""
    result = agent.invoke({"messages": [("user", question)]})
    messages = result["messages"]
    if getattr(agent, "verbose", True):
        _print_trace(messages)
    return _answer_text(messages[-1].content)


def ask_and_log(agent, question: str, log_path: str = LOG_PATH) -> dict:
    """
    Same as ask(), but also records the full trail to a JSON-lines log:
    the NL question, every SQL query the agent tried (it may retry), each
    query's raw result, the final NL answer, and token usage summed across
    every LLM call in the run. One JSON object per line in `log_path`,
    appended (never overwritten) so the file is a running audit trail
    across a whole session.

    Returns a dict: {"answer", "input_tokens", "output_tokens",
    "total_tokens", "llm_calls"} - not just the answer string, since token
    usage is the point of this function versus plain ask().
    """
    result = agent.invoke({"messages": [("user", question)]})
    messages = result["messages"]
    if getattr(agent, "verbose", True):
        _print_trace(messages)

    sql_attempts = _extract_sql_attempts(messages)
    answer = _answer_text(messages[-1].content)
    usage = _sum_usage(messages)

    record = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "question": question,
        "sql_attempts": sql_attempts,
        "final_sql": sql_attempts[-1]["query"] if sql_attempts else None,
        "sql_result": sql_attempts[-1]["result"] if sql_attempts else None,
        "answer": answer,
        **usage,
    }

    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {"answer": answer, **usage}
