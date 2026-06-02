import os
from langchain_anthropic import ChatAnthropic

MODEL = "claude-haiku-4-5-20251001"


def get_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model=MODEL,
        api_key=os.environ["ANTHROPIC_API_KEY"],
        temperature=0.3,
    )
