from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import streamlit as st

import src.langchain_bot.agent as agent
from src.langchain_bot.auth import authenticate_user
from src.langchain_bot.context import SessionContext


DB_PATH = Path(__file__).resolve().parent / "ecommerce.db"


def _now():
    return datetime.now(timezone.utc).isoformat()


def init_session():
    st.session_state.setdefault("admin_user", None)
    st.session_state.setdefault("admin_result", None)


def load_pending_actions(status, email):
    query = """
        SELECT id, thread_id, user_email, action_type, order_id,
               product_name, reason, status, created_at, updated_at
        FROM pending_actions
        WHERE status = ?
    """
    parameters = [status]
    if email:
        query += " AND lower(user_email) = lower(?)"
        parameters.append(email.strip())
    query += " ORDER BY created_at DESC"

    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(query, parameters).fetchall()


def update_action_status(action_id, status):
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            UPDATE pending_actions
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, _now(), action_id),
        )


def conversation_id_from_thread(thread_id, user_email):
    prefix = f"{user_email}_"
    if thread_id.startswith(prefix):
        return thread_id[len(prefix):]
    return thread_id


def result_text(result):
    messages = result.get("messages", []) if isinstance(result, dict) else []
    for message in reversed(messages):
        if getattr(message, "type", None) == "ai" and message.content:
            return message.content
    return "The request completed, but no assistant summary was returned."


def resume_action(row, decision):
    conversation_id = conversation_id_from_thread(
        row["thread_id"],
        row["user_email"],
    )
    config = {
        "configurable": {"thread_id": row["thread_id"]},
        "recursion_limit": 20,
    }
    context = SessionContext(
        user_email=row["user_email"],
        conversation_id=conversation_id,
        role="customer",
    )
    result = agent.resume_with_decision(decision, config, context)
    update_action_status(
        row["id"],
        "APPROVED" if decision == "approve" else "REJECTED",
    )
    return result_text(result)


def render_login():
    with st.form("admin_login_form"):
        email = st.text_input("Admin email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        user = authenticate_user(email, password, "admin")
        if user:
            st.session_state.admin_user = user
            st.rerun()
        else:
            st.error("Invalid admin credentials.")


def main():
    st.set_page_config(page_title="Support Admin", page_icon="🛠")
    init_session()
    st.title("Support Admin")

    if st.session_state.admin_user is None:
        render_login()
        return

    user = st.session_state.admin_user
    st.caption(f"Signed in as {user['email']}")

    status = st.selectbox(
        "Status",
        ["PENDING", "APPROVED", "REJECTED"],
    )
    email = st.text_input("Customer email (optional)")

    if st.session_state.admin_result:
        st.success(st.session_state.admin_result)
        st.session_state.admin_result = None

    rows = load_pending_actions(status, email)
    st.subheader(f"{status.title()} actions ({len(rows)})")

    if not rows:
        st.info("No matching pending actions.")
        return

    for row in rows:
        with st.container(border=True):
            st.write(f"**User:** {row['user_email']}")
            st.write(f"**Order:** #{row['order_id']}")
            st.write(f"**Action:** {row['action_type']}")
            st.write(f"**Thread:** `{row['thread_id']}`")
            if row["product_name"]:
                st.write(f"**Product:** {row['product_name']}")
            if row["reason"]:
                st.write(f"**Reason:** {row['reason']}")

            if status == "PENDING":
                approve, reject = st.columns(2)
                if approve.button("Approve", key=f"approve_{row['id']}"):
                    try:
                        st.session_state.admin_result = resume_action(row, "approve")
                    except Exception as error:
                        st.error(f"Approval failed: {error}")
                    else:
                        st.rerun()
                if reject.button("Reject", key=f"reject_{row['id']}"):
                    try:
                        st.session_state.admin_result = resume_action(row, "reject")
                    except Exception as error:
                        st.error(f"Rejection failed: {error}")
                    else:
                        st.rerun()


if __name__ == "__main__":
    main()
