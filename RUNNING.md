# Running the SDG SQL Agent

One-time setup, then how to ask it a question. See [AGENT.md](AGENT.md) for how it works.

## Setup (one time)

1. Open PowerShell in the project directory:
   ```powershell
   cd "C:\Users\kate\OneDrive\Portfolio\1-Projects\DS-08-UN-SDG-Platform"
   ```
2. Install the required packages:
   ```powershell
   pip install langchain langchain-community langchain-anthropic anthropic
   ```
3. Set your Anthropic API key for this shell session:
   ```powershell
   $env:ANTHROPIC_API_KEY = "sk-ant-..."
   ```
   This only lasts for the current PowerShell window — repeat it each time you open a new one.
4. Make sure the database exists at `data/processed/sdg_analytics.db`. If not, build it first by running [`notebooks/02_database_build.ipynb`](notebooks/02_database_build.ipynb).

## Asking a question

From the project directory, with the API key set:

```powershell
python src/run_agent.py "Which Sub-Saharan African countries improved most in SDG 3 since 2015?"
```

Or run it with no question to get an interactive prompt (`>`) and ask several in a row — type `quit` to exit.

Every question is logged to `logs/agent_queries.jsonl`, including the SQL it ran and the token cost.
