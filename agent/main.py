from langchain.agents import create_agent
from subagent.cypher_subagent import get_cypher_middleware
from model import build_openrouter_model
from langchain.agents.middleware import TodoListMiddleware
from langfuse.langchain import CallbackHandler
from system_prompt import system_prompt, todo_middleware_system_prompt
langfuse_callback = CallbackHandler()

agent = create_agent(
    model=build_openrouter_model(),
    middleware=[
        get_cypher_middleware(),
        TodoListMiddleware(system_prompt=todo_middleware_system_prompt),
    ],
    system_prompt=system_prompt
)

result = agent.invoke({
    "messages": [{"role": "user", "content": "Identify sales orders that have broken or incomplete flows (e.g. delivered but not billed, billed without delivery)"}]
}, config={"callbacks": [langfuse_callback]})
print(result["messages"][-1].content)