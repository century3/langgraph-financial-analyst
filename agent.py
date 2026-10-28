from pathlib import Path

from langgraph.graph import MessagesState, StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate,SystemMessagePromptTemplate,HumanMessagePromptTemplate,MessagesPlaceholder
from typing_extensions import Literal
from IPython.display import Image, display
from llm import DeepSeekR1,DeepSeekV3
from tools.financial_report import get_financial_report
from tools.stock_price import analyze_stocks
from prompt import plan_prompt

# Nodes
tools = [get_financial_report,analyze_stocks]
tools_by_name = {tool.name: tool for tool in tools}
deepseek_v3 = DeepSeekV3()
deepseek_r1 = DeepSeekR1()
llm_with_tools = deepseek_v3.bind_tools(tools)

class State(MessagesState):
    plan: str
    
def plan_node(state):
    # 创建消息列表
    prompt = plan_prompt

    # 调用 LLM
    response = deepseek_r1.invoke([SystemMessage(content=prompt),state["messages"][0]])
    
    state["plan"] = response.content
    print(state["plan"])
    return state

def llm_call(state):
    """LLM decides whether to call a tool or not"""
    messages = [
        SystemMessage(
            content=f"""
你是一个思路清晰，有条理的金融分析师，必须严格按照以下金融分析计划执行：
    
当前金融分析计划：
{state["plan"]}

如果你认为计划已经执行到最后一步了，请在内容的末尾加上\nFinal Answer字样

示例：
分析报告xxxxxxxx
Final Answer
            """
        )
    ] + state["messages"]
    
    print("------messages[-1]-------")
    print(state["messages"][-1])
    print("------------------")

    # 调用 LLM
    response = llm_with_tools.invoke(messages)

    # 将响应添加到消息列表中
    state["messages"].append(response)

    return state


def tool_node(state):
    """Performs the tool call"""
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        # 将观察结果转换为字符串格式
        if isinstance(observation, list):
            # 如果是列表，将其转换为字符串表示
            observation = str(observation)
        #result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
        state["messages"].append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return state


# Conditional edge function to route to the tool node or end based upon whether the LLM made a tool call
def should_continue(state) -> Literal["environment", "END"]:
    """Decide if we should continue the loop or stop based upon whether the LLM made a tool call"""
    messages = state["messages"]
    last_message = messages[-1]
    # If the LLM makes a tool call, then perform an action
    if "Final Answer" in last_message.content:
        return "END"
    # Otherwise, we stop (reply to the user)
    return "environment"


# Build workflow
agent_builder = StateGraph(State)

# Add nodes
agent_builder.add_node("plan_node", plan_node)
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("environment", tool_node)

# Add edges to connect nodes
agent_builder.add_edge(START, "plan_node")
agent_builder.add_edge("plan_node", "llm_call")
agent_builder.add_conditional_edges(
    "llm_call",
    should_continue,
    {
        # Name returned by should_continue : Name of next node to visit
        "environment": "environment",
        "END": END,
    },
)
agent_builder.add_edge("environment", "llm_call")

# Compile the agent
agent = agent_builder.compile()

# 保存代理工作流程图为 mermaid 文件
graph_mmd = agent.get_graph(xray=True).draw_mermaid()
mmd_path = Path(__file__).resolve().parent / "agent_graph.mmd"
mmd_path.write_text(graph_mmd, encoding="utf-8")
print(f"已保存流程图: {mmd_path}")

if __name__ == "__main__":
    messages = [HumanMessage(content="对比一下 '000612', '688126', '601788', '513100' 这四只股票的股价表现和财务情况，哪家更值得投资")]
    ret = agent.invoke({"plan": "", "messages": messages})
    print(ret["messages"][-1].content)