from langchain.tools import tool, ToolRuntime
from .context import SessionContext
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).resolve().parents[2] / "ecommerce.db"

def _now():
    return datetime.now(timezone.utc).isoformat()

def _find_owned_order(connection, order_id, user_email):
    return connection.execute(
        """
        SELECT orders.id, orders.user_id, orders.status
        FROM orders
        JOIN users ON users.id = orders.user_id
        WHERE orders.id = ?
          AND users.email = ?
        """,
        (order_id, user_email),
    ).fetchone()

@tool
def cancel_order_action(order_id: int, runtime: ToolRuntime[SessionContext],) -> str:
    '''
    after approval — verify user owns order, status PLACED only; UPDATE orders CANCELLED, payments REFUNDED; 
    INSERT ticket with thread_id; return confirmation text.
    '''
    context = runtime.context
    now= _now()

    with sqlite3.connect(DB_PATH) as connection:
        order = _find_owned_order(
            connection,
            order_id,
            context.user_email,
        )
        if not order:
            return f"Order {order_id} not found for user {context.user_email}."
        order_id, user_id, status = order
        if status != "PLACED":
            return (
                f"Order #{order_id} cannot be cancelled because its "
                f"status is {status}. Only PLACED orders can be cancelled."
            )
        connection.execute(
            """
            UPDATE orders
            SET status = 'CANCELLED'
            WHERE id=?
            """,
            (order_id,),
        )
        connection.execute(
            """
            UPDATE payments
            SET status = 'REFUNDED'
            WHERE order_id=?
            """,
            (order_id,),
        )
        connection.execute(
            """
            INSERT INTO tickets
                (
                    user_id,
                    subject,
                    status,
                    thread_id,
                    user_email,
                    created_at,
                    updated_at
                )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                f"Order #{order_id} cancellation",
                "OPEN",
                context.conversation_id,
                context.user_email,
                now,
                now,
            ),
        )
    return f"Order {order_id} has been cancelled and a refund has been initiated."
@tool
def create_return_action(
    order_id: int,
    product_name: str,
    reason: str,
    runtime: ToolRuntime[SessionContext],
) -> str:
    '''
     after approval — SHIPPED/DELIVERED only; reject PLACED with message to cancel instead; 
     INSERT return, ticket, refund payment; return confirmation.
    '''
    context = runtime.context
    now = _now()

    with sqlite3.connect(DB_PATH) as connection:
        order = _find_owned_order(
            connection,
            order_id,
            context.user_email,
        )

        if order is None:
            return f"Order #{order_id} was not found for your account."

        order_id, user_id, status = order

        if status == "PLACED":
            return (
                f"Order #{order_id} is still PLACED. "
                "Please request cancellation instead of a return."
            )

        if status not in {"SHIPPED", "DELIVERED"}:
            return (
                f"Order #{order_id} cannot be returned because its "
                f"status is {status}."
            )

        item = connection.execute(
            """
            SELECT order_items.id
            FROM order_items
            JOIN products
                ON products.id = order_items.product_id
            WHERE order_items.order_id = ?
              AND lower(products.name) = lower(?)
            LIMIT 1
            """,
            (order_id, product_name),
        ).fetchone()

        if item is None:
            return (
                f"{product_name} was not found in order "
                f"#{order_id}."
            )

        order_item_id = item[0]

        cursor = connection.execute(
            """
            INSERT INTO returns
                (
                    order_id,
                    order_item_id,
                    user_id,
                    reason,
                    status,
                    requested_at
                )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                order_item_id,
                user_id,
                reason,
                "PENDING",
                now,
            ),
        )

        return_id = cursor.lastrowid

        connection.execute(
            """
            UPDATE payments
            SET status = 'REFUNDED'
            WHERE order_id = ?
            """,
            (order_id,),
        )

        connection.execute(
            """
            INSERT INTO tickets
                (
                    user_id,
                    return_id,
                    subject,
                    status,
                    thread_id,
                    user_email,
                    created_at,
                    updated_at
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                return_id,
                f"Return request for order #{order_id}",
                "OPEN",
                context.conversation_id,
                context.user_email,
                now,
                now,
            ),
        )

    return (
        f"Return request created for {product_name} "
        f"in order #{order_id}. The payment was marked as refunded."
    )


def get_action_tools():
    return [cancel_order_action, create_return_action]