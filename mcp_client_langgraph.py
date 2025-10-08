import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
# from langchain_mistralai import ChatMistralAI
from langchain_openai import ChatOpenAI   
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def run_k8s_query(user_input: str):
    # mistral_key = os.getenv("MISTRAL_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")

    # Initialize Mistral model
    # model = ChatMistralAI(model="mistral-medium-latest", api_key=mistral_key)
    model = ChatOpenAI(
        # model="deepseek-chat",
        model="deepseek-reasoner",
        api_key=deepseek_key,
        base_url="https://api.deepseek.com",
    )

    # Connect to your Kubernetes MCP server
    client = MultiServerMCPClient(
        {
            "kubernetes": {
                "transport": "streamable_http",
                "url": "http://127.0.0.1:8000/mcp",
            }
        }
    )

    tools = await client.get_tools()
    model_with_tools = model.bind_tools(tools)
    tool_node = ToolNode(tools)

    # LangGraph pipeline
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

    result = await graph.ainvoke({"messages": [{"role": "user", "content": user_input}]})
    last_msg = result["messages"][-1].content

    # Fallback if command is not supported
    if "Mistral" in str(last_msg) and "tool" in str(last_msg).lower():
        return "I don’t have a tool for that Kubernetes command. Please try another action."

    # Detect empty results like 'no pods found'
    if last_msg.strip() in ["", "(No pods found or empty response received.)"]:
        return "No resources found in the default namespace."

    return last_msg if isinstance(last_msg, str) else str(last_msg)


async def main():
    print("🚀 Kubernetes MCP Client (interactive)")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("k8s> ").strip()
        if user_input.lower() in ["exit", "quit"]:
            break
        if not user_input:
            continue

        try:
            answer = await run_k8s_query(user_input)
            print(f"\n{answer}\n")
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
