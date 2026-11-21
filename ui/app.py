import pandas as pd
import plotly.graph_objects as go
import psycopg
import streamlit as st

from ticket_assistant.assistant import PAYLOAD_KEYS, Assistant

JIRA = "https://issues.apache.org/jira/browse/"
HINT = (
    "Try: How many Kafka issues are unresolved? / Chart issues per project / "
    "List the 10 oldest unresolved Kafka bugs / Why do consumer group rebalances take so long?"
)

st.set_page_config(page_title="Jira Ticket Assistant", layout="wide")


@st.cache_resource(show_spinner="Loading models and data...")
def load_assistant():
    return Assistant()


def render(message, index):
    payload = message.get("payload") or {}
    with st.chat_message(message["role"]):
        table = payload.get("table")
        if table:
            st.markdown(message["content"].split("\n\n")[0])
            st.dataframe(
                pd.DataFrame(table["rows"], columns=table["columns"]),
                hide_index=True,
                key=f"table-{index}",
            )
        else:
            st.markdown(message["content"])
        if payload.get("figure"):
            st.plotly_chart(go.Figure(payload["figure"]), key=f"figure-{index}")
        if payload.get("note"):
            st.caption(payload["note"])
        if payload.get("sources"):
            with st.expander("Sources"):
                for s in payload["sources"]:
                    st.markdown(f"- [{s['key']}]({JIRA}{s['key']}): {s['title']} (score {s['score']})")
        if payload.get("plan"):
            with st.expander(f"How this was answered ({message.get('agent')})"):
                st.json(payload["plan"])


assistant = load_assistant()
history = assistant.history
st.session_state.setdefault("session_id", None)
st.session_state.setdefault("messages", [])

with st.sidebar:
    st.title("Jira Ticket Assistant")
    user_id = st.text_input("User", value="demo")
    if history:
        try:
            if st.button("New chat"):
                st.session_state.session_id = history.new_session(user_id)
                st.session_state.messages = []
            for s in history.sessions(user_id):
                if st.button(s["title"] or "New chat", key=s["id"]):
                    st.session_state.session_id = s["id"]
                    st.session_state.messages = history.messages(s["id"], limit=100)
        except psycopg.Error:
            st.warning("History is unavailable right now.")

st.title("Ask about Kafka, Cassandra and Hadoop tickets")
if not st.session_state.messages:
    st.caption(HINT)

for i, message in enumerate(st.session_state.messages):
    render(message, i)

question = st.chat_input("Ask a question")
if question:
    created = False
    if history and not st.session_state.session_id:
        try:
            st.session_state.session_id = history.new_session(user_id)
            created = True
        except psycopg.Error:
            st.warning("History is unavailable right now.")
    st.session_state.messages.append({"role": "user", "content": question})
    render(st.session_state.messages[-1], len(st.session_state.messages) - 1)
    with st.spinner("Thinking..."):
        out = assistant.ask(question, st.session_state.session_id)
    payload = {k: out[k] for k in PAYLOAD_KEYS if k in out}
    st.session_state.messages.append(
        {"role": "assistant", "content": out["answer"], "agent": out["agent"], "payload": payload}
    )
    if created:
        st.rerun()
    render(st.session_state.messages[-1], len(st.session_state.messages) - 1)