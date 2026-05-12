import os
from langchain_openai import ChatOpenAI

MODEL = "deepseek-ai/deepseek-v3.2"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=MODEL,
        base_url=NVIDIA_BASE_URL,
        api_key=os.environ["NVIDIA_API_KEY"],
        temperature=0.3,
    )
