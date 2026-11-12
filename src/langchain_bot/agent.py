import asyncio

from langchain.agents import create_agent
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from .rag_tool import search_policies
from dotenv import load_dotenv
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
import os
from pathlib import Path
import json
from fastmcp.client.transports import StdioTransport
from langchain.mcp import MCPAdapter
from .middleware import get_hitl_middleware, get_logging_middleware
from .sql_tools import get_sql_tools
from .action_tools import get_action_tools
from .context import SessionContext

load_dotenv()
_agent = None
_checkpointer = None
THREADS_PATH = Path(__file__).resolve().parents[2] / "threads.json"


GMAIL_MCP_CONFIG = {
    "mcpServers": {
        "gmail": {
            "command": "npx",
            "args": ["-y", "@gongrzhe/server-gmail-autoauth-mcp"],
        },
    }
}

def _sync_mcp_tool(tool):
    """MCPAdapter tools are async-only. agent.invoke needs a sync func."""
    if getattr(tool, "func", None) is not None:
        return tool

    tool_name = tool.name

    async def _invoke_mcp_tool(kwargs):
        async with MCPAdapter(GMAIL_MCP_CONFIG) as adapter:
            tools = await adapter.list_tools()
            matching_tool = next(
                candidate for candidate in tools if candidate.name == tool_name
            )
            return await matching_tool.ainvoke(kwargs)

    def _call(**kwargs):
        return asyncio.run(_invoke_mcp_tool(kwargs))

    return StructuredTool(
        name=tool.name,
        description=tool.description,
        args_schema=tool.args_schema,
        func=_call,
        response_format="content",
    )

def load_threads(user_email):
    if not THREADS_PATH.exists():
        return []
    with THREADS_PATH.open("r") as f:
        all_threads = json.load(f)
    return all_threads.get(user_email, [])

def save_threads(user_email, threads):
    if THREADS_PATH.exists():
        with THREADS_PATH.open("r") as f:
            all_threads = json.load(f)
    else:
        all_threads = {}
    all_threads[user_email] = threads
    with THREADS_PATH.open("w") as f:
        json.dump(all_threads, f, indent=4)


def add_thread(user_email, conversation_id):
    threads = load_threads(user_email)
    if conversation_id not in threads:
        threads.append(conversation_id)
        save_threads(user_email, threads)

def get_thread_config(user_email, conversation_id):
    return{
        "configurable" : {
            "thread_id" : f"{user_email}_{conversation_id}"
        },
        "recursion_limit" : 20
    }
def get_checkpointer():
    global _checkpointer
    if _checkpointer is None:
        db_path = os.getenv("CHECKPOINTS_DB_PATH", "checkpoints.sqlite")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        _checkpointer = SqliteSaver(conn)
        _checkpointer.setup()
    return _checkpointer
async def load_gmail_tools():
    async with MCPAdapter(GMAIL_MCP_CONFIG) as adapter:
        return await adapter.list_tools()
def create_support_agent():
    llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    gmail_tools = [
        _sync_mcp_tool(tool)
        for tool in asyncio.run(load_gmail_tools())
    ]
    action_tools = get_action_tools()
    tools = [search_policies] + get_sql_tools() + gmail_tools + action_tools
    system_prompt="""
            You are a helpful e-commerce support assistant that can answer questions about company policies and FAQs.
            You can use the 'search_policies' tool to look up relevant policy documents and provide answers for the following: 
            returns, shipping, refunds, cancellation policy; 
            You can use the SQL tools for orders, returns, payments, and spending.
            Always join orders to users and filter by the logged-in user's email.
            Never return another user's data.
            Use at most 3 SQL attempts for one request.
            Use send_email only for email requests. Its `to` list must contain only
            the logged-in customer's email.
            For a cancellation or return request, first verify the order with SQL.
            Then use send_email to send a one-line "request received" message and
            use SQL to insert the corresponding email_logs row. Then call exactly
            one action tool. The action tool requires human approval before it runs.
            Do not call more than one tool in a turn.
            After an approved action, send the result email and record it in
            email_logs. Do not call delete_email, batch_delete_emails, or label tools.
            Answer from tool results; use no tool for simple greetings.
        """
    middleware = [get_hitl_middleware()] + get_logging_middleware()
    return create_agent(
    llm,
    tools,
    context_schema=SessionContext,
    system_prompt=system_prompt,
    middleware=middleware,
    checkpointer=get_checkpointer(),
    )

def get_agent():
    global _agent
    if _agent is None:
        _agent = create_support_agent()
    return _agent


def resume_with_decision(decision, config, context):
    return get_agent().invoke(
        Command(resume={"decisions": [{"type": decision}]}),
        config,
        context=context,
    )
