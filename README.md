# LangChain E-commerce Support Bot

A Streamlit e-commerce support assistant built with LangChain, LangGraph, SQLite, Chroma, and Gmail MCP.

The assistant supports:

- Customer login and per-user conversation threads.
- SQL-backed order, payment, return, and spending questions.
- RAG answers from the policy documents in `policies/`.
- Human approval for cancellations and returns.
- Gmail actions through the `@gongrzhe/server-gmail-autoauth-mcp` server.
- SQLite checkpoints for conversation memory.

## Requirements

- Python 3.11 or newer.
- `uv`.
- Node.js and `npx` for the Gmail MCP server.
- An OpenAI API key.
- Gmail OAuth credentials if Gmail tools are enabled.

## Setup

Install the project dependencies:

```bash
uv sync
```

Create a local environment file:

```bash
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env`. Keep `.env` local and never commit it.

The demo database is `ecommerce.db`. To recreate it from the seed schema:

```bash
uv run python src/langchain_bot/db_init.py
```

This resets the local database and its seed data.

## Run the customer app

```bash
uv run streamlit run app.py
```

The terminal prints a local URL. Open it in a browser and log in with a seeded customer account from the local database.

## Run the admin app

Run the admin dashboard on a separate port while the customer app is running:

```bash
uv run streamlit run app_admin.py --server.port 8502
```

The admin app lists pending cancellation and return requests. An administrator can approve or reject each request, which resumes the customer thread and updates the action status in SQLite.

## Gmail MCP setup

The agent starts the Gmail MCP server with:

```text
npx -y @gongrzhe/server-gmail-autoauth-mcp
```

Authenticate it once:

```bash
npx @gongrzhe/server-gmail-autoauth-mcp auth
```

Store Gmail OAuth files under `~/.gmail-mcp/`, not in the project directory. For a local OAuth client, register this exact redirect URI in Google Cloud Console:

```text
http://localhost:3000/oauth2callback
```

The discovered Gmail tool is named `send_email`. Gmail tools are adapted to synchronous wrappers so the application can continue using `agent.invoke()`.

## Architecture

- `app.py`: customer Streamlit UI, login, thread selection, chat requests, and HITL notices.
- `app_admin.py`: admin login, pending-action filters, and approve/reject workflow.
- `src/langchain_bot/agent.py`: the single LangChain agent, tool registration, checkpointer, Gmail adapter, and resume helper.
- `src/langchain_bot/action_tools.py`: approved cancellation and return database actions.
- `src/langchain_bot/hitl_utils.py`: interrupt detection and pending-action persistence.
- `src/langchain_bot/middleware.py`: synchronous model/tool logging and HITL middleware.
- `src/langchain_bot/sql_tools.py`: SQLDatabase toolkit for `ecommerce.db`.
- `src/langchain_bot/rag_tool.py`: policy-document vector search.
- `checkpoints.sqlite`: local LangGraph conversation checkpoints; ignored by Git.

## Security

Never commit API keys, OAuth credentials, Gmail tokens, local databases, checkpoints, or customer data. The repository ignores `.env`, OAuth/token files, SQLite databases, Chroma data, and Gmail token directories. Use `.env.example` as the safe configuration template.

Before publishing, check the tracked file list:

```bash
git status
git ls-files
```

## Validation

Compile the Python modules:

```bash
uv run python -m py_compile app.py app_admin.py src/langchain_bot/*.py
```

Inspect the registered tools:

```bash
uv run python -c "from src.langchain_bot.agent import get_action_tools, get_sql_tools, load_gmail_tools; import asyncio; print([t.name for t in get_action_tools()]); print([t.name for t in get_sql_tools()]); print([t.name for t in asyncio.run(load_gmail_tools())])"
```
