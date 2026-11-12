import time
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    wrap_model_call,
    wrap_tool_call,
)
def _ts():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

@wrap_model_call 
def model_logging_middleware(request, handler):
    messages = request.messages
    message_count = len(messages)
    last_message = messages[-1].content if messages else None

    print(f"[{_ts()}] Model call with {message_count} messages")
    print(f"[{_ts()}] Last message: {last_message}")

    try:
        response = handler(request)
        response_preview = (
            response.content
            if hasattr(response, "content")
            else str(response)
        )
        print(f"[{_ts()}] Model response: {response_preview}")
        tool_calls = response.tool_calls if hasattr(response, "tool_calls") else []
        if tool_calls:
            print(f"[{_ts()}] Tool calls made: {tool_calls}")
        return response
    except Exception as e:
        print(f"[{_ts()}] Model call failed with error: {e}")
        raise

@wrap_tool_call
def tool_logging_middleware(request, handler):
    tool_call = request.tool_call
    print(f"[{_ts()}] Tool call: {tool_call}")

    try:
        response = handler(request)
        print(f"[{_ts()}] Tool completed successfully")
        return response

    except Exception as error:
        print(f"[{_ts()}] Tool error: {error}")
        raise


def get_logging_middleware():
    return [model_logging_middleware, tool_logging_middleware]


def get_hitl_middleware():
    return HumanInTheLoopMiddleware(
        interrupt_on={
            "cancel_order_action": {
                "allowed_decisions": ["approve", "reject"],
            },
            "create_return_action": {
                "allowed_decisions": ["approve", "reject"],
            },
        },
    )