from typing import Any, List
from langchain_openai import ChatOpenAI

class LLMHarness:
    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.7):
        self.llm = ChatOpenAI(model=model, temperature=temperature)

    async def run(self, messages: List[Any]) -> str:
        resp = await self.llm.ainvoke(messages)
        return resp.content  # type: ignore