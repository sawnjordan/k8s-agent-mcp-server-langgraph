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
from chat_history import init_db, save_message, load_messages, list_sessions

# Load .env file
load_dotenv()
init_db()  # Ensure DB exists


# --- Backend call to MCP ---
async def run_k8s_query(user_input, model_name="mistral-medium-latest"):
    mistral_key = os.getenv("MISTRAL_API_KEY")
    mcp_server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/mcp")

    model = ChatMistralAI(model=model_name, api_key=mistral_key)

    client = MultiServerMCPClient(
        {
            "kubernetes": {
                "transport": "streamable_http",
                "url": mcp_server_url,
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

    # Build LangGraph pipeline
    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "call_model")
    builder.add_conditional_edges("call_model", should_continue)
    builder.add_edge("tools", "call_model")
    graph = builder.compile()

    result = await graph.ainvoke({"messages": [{"role": "user", "content": user_input}]})
    last_msg = result["messages"][-1].content
    return last_msg if isinstance(last_msg, str) else str(last_msg)


# --- Streamlit UI ---
def main():
    st.set_page_config(page_title="Kubernetes Chat", page_icon="☸️", layout="wide")
    st.title("☸️ Kubernetes MCP Chat")

    # Model selection
    MODEL_OPTIONS = {
        "Mistral Large": "mistral-large-latest",
        "Mistral Medium": "mistral-medium-latest",
        "Mistral Small": "mistral-small",
    }
    selected_model = st.selectbox("Select Model", options=list(MODEL_OPTIONS.keys()), index=1)
    st.session_state.selected_model = MODEL_OPTIONS[selected_model]

    # --- Session Management ---
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    sessions = list_sessions()
    selected_session = st.sidebar.selectbox("Previous Sessions", options=["New Session"] + sessions)

    if selected_session == "New Session":
        session_id = st.session_state.session_id
    else:
        session_id = selected_session

    # Load chat messages
    messages = load_messages(session_id)

    # Chat input
    user_input = st.chat_input("Ask something about Kubernetes...")
    if user_input:
        # Save user message
        save_message(session_id, "user", user_input)
        with st.spinner("Thinking..."):
            answer = asyncio.run(run_k8s_query(user_input, st.session_state.selected_model))
            # Save assistant message
            save_message(session_id, "assistant", answer)
        messages = load_messages(session_id)

    # Display chat history
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Clear chat button
    if st.button("Clear Chat"):
        st.session_state.session_id = str(uuid.uuid4())  # start fresh session


if __name__ == "__main__":
    main()
