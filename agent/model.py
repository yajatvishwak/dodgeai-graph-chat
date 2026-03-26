
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def build_openrouter_model() -> ChatOpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENROUTER_API_KEY environment variable.")

    model_name = os.environ.get("OPENROUTER_MODEL", "google/gemini-3.1-flash-lite-preview")
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    temperature = float(os.environ.get("OPENROUTER_TEMPERATURE", "0"))

    return ChatOpenAI(
        model=model_name,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
    )