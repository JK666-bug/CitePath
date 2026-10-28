import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import AzureChatOpenAI

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DEFAULT_DEPLOYMENT = "gpt-4.1-mini"
DEFAULT_API_VERSION = "2025-04-01-preview"


def chat_model() -> AzureChatOpenAI:
    key = os.environ.get("HKU_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Set HKU_API_KEY in backend/.env")
    deployment = os.environ.get("HKU_DEPLOYMENT", DEFAULT_DEPLOYMENT).strip()
    api_version = os.environ.get("HKU_API_VERSION", DEFAULT_API_VERSION).strip()
    return AzureChatOpenAI(
        base_url=f"https://api.hku.hk/openai/student/deployments/{deployment}",
        api_version=api_version,
        api_key=key,
        model=deployment,
        temperature=0,
        timeout=60,
        max_retries=1,
        default_headers={
            "api-key": key,
            "Ocp-Apim-Subscription-Key": key,
        },
    )


def ping() -> str:
    reply = chat_model().invoke([HumanMessage(content="Hello!")])
    return str(reply.content)
