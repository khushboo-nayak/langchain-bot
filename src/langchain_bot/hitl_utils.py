from datetime import datetime, timezone
from pathlib import Path
import sqlite3


DB_PATH = Path(__file__).resolve().parents[2] / "ecommerce.db"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _interrupt_values(result):
    if isinstance(result, dict):
        return result.get("__interrupt__", ())
    return getattr(result, "interrupts", ())


def _action_request(interrupt):
    value = getattr(interrupt, "value", interrupt)
    if not isinstance(value, dict):
        return None

    requests = value.get("action_requests", [])
    if not requests:
        return None

    request = requests[0]
    if hasattr(request, "name"):
        return request.name, request.args
    return request.get("name"), request.get("args", request.get("arguments", {}))


def has_pending_action_for_thread(thread_id):
    with sqlite3.connect(DB_PATH) as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM pending_actions
            WHERE thread_id = ? AND status = 'PENDING'
            LIMIT 1
            """,
            (thread_id,),
        ).fetchone()
    return row is not None


def handle_interrupt(result, thread_id, user_email):
    """Persist a HITL action request and return the markdown shown in chat."""
    for interrupt in _interrupt_values(result):
        request = _action_request(interrupt)
        if request is None:
            continue

        tool_name, arguments = request
        action_types = {
            "cancel_order_action": "CANCEL_ORDER",
            "create_return_action": "CREATE_RETURN",
        }
        action_type = action_types.get(tool_name)
        if action_type is None:
            continue

        order_id = arguments.get("order_id")
        product_name = arguments.get("product_name")
        reason = arguments.get("reason")

        with sqlite3.connect(DB_PATH) as connection:
            existing = connection.execute(
                """
                SELECT 1
                FROM pending_actions
                WHERE thread_id = ?
                  AND action_type = ?
                  AND order_id = ?
                  AND status = 'PENDING'
                LIMIT 1
                """,
                (thread_id, action_type, order_id),
            ).fetchone()

            if existing is None:
                connection.execute(
                    """
                    INSERT INTO pending_actions
                        (
                            thread_id,
                            user_email,
                            action_type,
                            order_id,
                            product_name,
                            reason,
                            status,
                            created_at,
                            updated_at
                        )
                    VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
                    """,
                    (
                        thread_id,
                        user_email,
                        action_type,
                        order_id,
                        product_name,
                        reason,
                        _now(),
                        _now(),
                    ),
                )

        label = "cancellation" if action_type == "CANCEL_ORDER" else "return"
        details = f"order #{order_id}"
        if product_name:
            details += f" ({product_name})"
        return (
            f"### Approval required\n\n"
            f"Please approve or reject this {label} request for {details}."
        )

    return ""