import asyncio
import streamlit as st
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mistralai import ChatMistralAI
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

# --- Backend call to MCP ---
async def run_multi_query(user_input, model_name="mistral-medium-latest"):
    mistral_key = os.getenv("MISTRAL_API_KEY")
    mcp_server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/mcp")
    # aws_s3_mcp_url = os.getenv("AWS_S3_MCP_URL", "http://127.0.0.1:8010/mcp")

    model = ChatMistralAI(model=model_name, api_key=mistral_key)

    # Multi-server MCP client
    client = MultiServerMCPClient(
        {
            "kubernetes": {
                "transport": "streamable_http",
                "url": mcp_server_url,
            },
            # "aws_s3": {
            #     "transport": "streamable_http",
            #     "url": aws_s3_mcp_url,
            # }
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

    # Build LangGraph pipeline
    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "call_model")
    builder.add_conditional_edges("call_model", should_continue)
    builder.add_edge("tools", "call_model")
    graph = builder.compile()

    # Updated system prompt to include both K8s and S3
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

    # Run with full context
    result = await graph.ainvoke({"messages": conversation_history})
    last_msg = result["messages"][-1].content
    return last_msg if isinstance(last_msg, str) else str(last_msg)

# --- Streamlit UI ---
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

    # Sidebar with session management
    with st.sidebar:
        st.title("☸️ Kubernetes Chat")
        
        # Model selection at the top
        MODEL_OPTIONS = {
            "Mistral Large": "mistral-large-latest",
            "Mistral Medium": "mistral-medium-latest",
            "Mistral Small": "mistral-small",
        }
        selected_model = st.selectbox("Select Model", options=list(MODEL_OPTIONS.keys()), index=1)
        st.session_state.selected_model = MODEL_OPTIONS[selected_model]
        
        st.divider()
        
        # NEW SESSION BUTTON
        if st.button("➕ New Session", use_container_width=True):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.session_state.sessions_page = 0  # Reset to first page
            st.rerun()

        # Search box
        search_query = st.text_input("🔍 Search chats", placeholder="Type to search...")
        
        # Load sessions with preview
        sessions_data = list_sessions_with_preview(limit=50)
        
        # Filter sessions based on search query
        if search_query:
            filtered_sessions = [
                s for s in sessions_data 
                if search_query.lower() in s["preview"].lower() or search_query.lower() in s["session_id"].lower()
            ]
        else:
            filtered_sessions = sessions_data
        
        # Increase sessions per page for list view
        sessions_per_page = 20
        total_sessions = len(filtered_sessions)
        start_idx = st.session_state.sessions_page * sessions_per_page
        end_idx = min(start_idx + sessions_per_page, total_sessions)
        paginated_sessions = filtered_sessions[start_idx:end_idx]

        if not filtered_sessions:
            st.info("No sessions found")
        else:
            # Display sessions as a clean list using radio buttons for selection
            session_options = []
            for session in paginated_sessions:
                preview = session["preview"][:45] + "..." if len(session["preview"]) > 45 else session["preview"]
                if not preview.strip():
                    preview = "(empty session)"
                session_options.append((session["session_id"], preview))

            # Map session_id → preview
            radio_labels = {sid: preview for sid, preview in session_options}

            # Use session_id as the value in st.radio (stable unique key)
            selected_session_id = st.radio(
                "Select session:",
                options=list(radio_labels.keys()),  # stable keys
                format_func=lambda sid: radio_labels[sid],  # show preview as label
                index=None if st.session_state.session_id not in radio_labels else list(radio_labels.keys()).index(st.session_state.session_id),
                label_visibility="collapsed",
                key="session_selector"
            )

            # Update session if changed
            if selected_session_id and selected_session_id != st.session_state.session_id:
                st.session_state.session_id = selected_session_id
                st.session_state.messages = load_messages(selected_session_id)
                st.rerun()
        # Pagination controls
        if total_sessions > sessions_per_page:
            st.divider()
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.session_state.sessions_page > 0:
                    if st.button("⬅️ Prev", use_container_width=True):
                        st.session_state.sessions_page -= 1
                        st.rerun()
            with col2:
                total_pages = max(1, (total_sessions + sessions_per_page - 1) // sessions_per_page)
                st.markdown(
                    f"<div style='text-align: center; padding: 4px; font-size: 12px;'>Page {st.session_state.sessions_page+1} / {total_pages}</div>",
                    unsafe_allow_html=True
                )
            with col3:
                if end_idx < total_sessions:
                    if st.button("➡️", use_container_width=True):
                        st.session_state.sessions_page += 1
                        st.rerun()
        
        st.divider()
        
        # Display current session info
        st.info(f"Current Session: `{st.session_state.session_id[:8]}...`")

    # Main chat area
    st.title("Kubernetes MCP Chat")
    
    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("Ask something about Kubernetes...")
    if user_input:
        # Add user message to UI immediately
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Save user message to DB
        save_message(st.session_state.session_id, "user", user_input)
        
        # Get assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                answer = asyncio.run(run_multi_query(user_input, st.session_state.selected_model))
                st.markdown(answer)
        
        # Save assistant message to DB
        save_message(st.session_state.session_id, "assistant", answer)
        
        # Reload messages to keep session state in sync
        st.session_state.messages = load_messages(st.session_state.session_id)
        
        # Rerun to update the UI and sidebar
        st.rerun()

if __name__ == "__main__":
    main()
