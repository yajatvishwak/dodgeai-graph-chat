from langchain.agents import create_agent
from subagent.cypher_subagent import get_cypher_middleware
from model import build_openrouter_model

from langfuse.langchain import CallbackHandler

langfuse_callback = CallbackHandler()

agent = create_agent(
    model=build_openrouter_model(),
    middleware=[get_cypher_middleware()],
)

result = agent.invoke({
    "messages": [{"role": "user", "content": "What is the total net amount of all sales orders?"}]
}, config={"callbacks": [langfuse_callback]})
print(result["messages"][-1].content)