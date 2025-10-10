import asyncio
import streamlit as st
from langchain_mcp_adapters.client import MultiServerMCPClient
# from langchain_mistralai import ChatMistralAI
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
import os
import uuid
from dotenv import load_dotenv

# DB helper
from chat_history import init_db, save_message, load_messages, list_sessions_with_preview

# Load .env file
load_dotenv()
init_db()  # Ensure DB exists

# -----------------------------
# Helper to run async inside Streamlit
# -----------------------------
def run_async_in_streamlit(coro):
    """
    Safely run an async coroutine inside Streamlit.
    Works whether an event loop is already running or not.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, safe to use asyncio.run
        return asyncio.run(coro)
    else:
        # Loop exists, run coroutine in it
        return loop.run_until_complete(coro)

# -----------------------------
# Backend call to MCP
# -----------------------------
async def run_multi_query(user_input, model_name="deepseek-chat"):
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")

    mcp_server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/mcp")
    aws_s3_mcp_url = os.getenv("AWS_S3_MCP_URL", "http://127.0.0.1:8010/mcp")

    model = ChatOpenAI(
        model=model_name,
        api_key=deepseek_key,
        base_url="https://api.deepseek.com",
    )

    client = MultiServerMCPClient(
        {
            "kubernetes": {
                "transport": "streamable_http",
                "url": mcp_server_url,
            },
            "aws_s3": {
                "transport": "streamable_http",
                "url": aws_s3_mcp_url,
            }
        }
    )

    tools = await client.get_tools()
    model_with_tools = model.bind_tools(tools)
    tool_node = ToolNode(tools)

    def should_continue(state: MessagesState):
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools"
        return END

    async def call_model(state: MessagesState):
        messages = state["messages"]
        response = await model_with_tools.ainvoke(messages)
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "call_model")
    builder.add_conditional_edges("call_model", should_continue)
    builder.add_edge("tools", "call_model")
    graph = builder.compile()

    # Build conversation history
    conversation_history = [
        {
            "role": "system",
            "content": (
                "You are an assistant capable of managing both Kubernetes and AWS S3. "
                "Answer concisely and directly based on the user request. "
                "Use Kubernetes tools for cluster-related queries and AWS S3 tools for bucket/object queries. "
                "Do not give generic suggestions unless explicitly asked."
            ),
        }
    ] + [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
    ]
    conversation_history.append({"role": "user", "content": user_input})

    result = await graph.ainvoke({"messages": conversation_history})
    last_msg = result["messages"][-1].content
    return last_msg if isinstance(last_msg, str) else str(last_msg)

# -----------------------------
# Streamlit UI
# -----------------------------
def main():
    st.set_page_config(
        page_title="Kubernetes Chat", 
        page_icon="☸️", 
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "sessions_page" not in st.session_state:
        st.session_state.sessions_page = 0

    # Sidebar
    with st.sidebar:
        st.title("☸️ Kubernetes Chat")

        MODEL_OPTIONS = {
            "Deepseek Chat": "deepseek-chat",
            "Deepseek Reasoner": "deepseek-reasoner",
        }
        selected_model = st.selectbox("Select Model", options=list(MODEL_OPTIONS.keys()), index=0)
        st.session_state.selected_model = MODEL_OPTIONS[selected_model]

        st.divider()

        # New Session
        if st.button("➕ New Session", use_container_width=True):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.session_state.sessions_page = 0
            st.rerun()

        # Search sessions
        search_query = st.text_input("🔍 Search chats", placeholder="Type to search...")
        sessions_data = list_sessions_with_preview(limit=50)

        if search_query:
            filtered_sessions = [
                s for s in sessions_data 
                if search_query.lower() in s["preview"].lower() or search_query.lower() in s["session_id"].lower()
            ]
        else:
            filtered_sessions = sessions_data

        # Pagination
        sessions_per_page = 20
        total_sessions = len(filtered_sessions)
        start_idx = st.session_state.sessions_page * sessions_per_page
        end_idx = min(start_idx + sessions_per_page, total_sessions)
        paginated_sessions = filtered_sessions[start_idx:end_idx]

        if not filtered_sessions:
            st.info("No sessions found")
        else:
            session_options = []
            for session in paginated_sessions:
                preview = session["preview"][:45] + "..." if len(session["preview"]) > 45 else session["preview"]
                if not preview.strip():
                    preview = "(empty session)"
                session_options.append((session["session_id"], preview))

            radio_labels = {sid: preview for sid, preview in session_options}
            selected_session_id = st.radio(
                "Select session:",
                options=list(radio_labels.keys()),
                format_func=lambda sid: radio_labels[sid],
                index=None if st.session_state.session_id not in radio_labels else list(radio_labels.keys()).index(st.session_state.session_id),
                label_visibility="collapsed",
                key="session_selector"
            )

            if selected_session_id and selected_session_id != st.session_state.session_id:
                st.session_state.session_id = selected_session_id
                st.session_state.messages = load_messages(selected_session_id)
                st.rerun()

        # Pagination controls
        if total_sessions > sessions_per_page:
            st.divider()
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.session_state.sessions_page > 0 and st.button("⬅️ Prev", use_container_width=True):
                    st.session_state.sessions_page -= 1
                    st.rerun()
            with col2:
                total_pages = max(1, (total_sessions + sessions_per_page - 1) // sessions_per_page)
                st.markdown(
                    f"<div style='text-align: center; padding: 4px; font-size: 12px;'>Page {st.session_state.sessions_page+1} / {total_pages}</div>",
                    unsafe_allow_html=True
                )
            with col3:
                if end_idx < total_sessions and st.button("➡️", use_container_width=True):
                    st.session_state.sessions_page += 1
                    st.rerun()

        st.divider()
        st.info(f"Current Session: `{st.session_state.session_id[:8]}...`")

    # Main chat area
    st.title("Kubernetes MCP Chat")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Ask something about Kubernetes...")
    if user_input:
        async def handle_user_input():
            # Add user message to UI
            with st.chat_message("user"):
                st.markdown(user_input)

            save_message(st.session_state.session_id, "user", user_input)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    answer = await run_multi_query(user_input, st.session_state.selected_model)
                    st.markdown(answer)

            save_message(st.session_state.session_id, "assistant", answer)
            st.session_state.messages = load_messages(st.session_state.session_id)
            st.rerun()

        # Run async safely inside Streamlit
        run_async_in_streamlit(handle_user_input())

if __name__ == "__main__":
    main()
