import os
from openai import OpenAI

NEBIUS_BASE = "https://api.studio.nebius.com/v1/"

# Defaults — overridden at runtime via session state or env
MODEL_LARGE = "Qwen/Qwen3-235B-A22B-Instruct-2507"
MODEL_SMALL = "Qwen/Qwen3-30B-A3B-Instruct-2507"

# Models shown in the cloud-mode selector
KNOWN_MODELS: list[tuple[str, str]] = [
    ("Qwen3-235B  (Best quality)", "Qwen/Qwen3-235B-A22B-Instruct-2507"),
    ("Qwen3-30B   (Faster / cheaper)", "Qwen/Qwen3-30B-A3B-Instruct-2507"),
    ("DeepSeek-V4-Flash (Fastest)", "deepseek-ai/DeepSeek-V4-Flash-0731"),
    ("DeepSeek-V4-Pro   (Pro)", "deepseek-ai/DeepSeek-V4-Pro"),
    ("Kimi-K3 (Moonshot)", "moonshotai/Kimi-K3"),
]


def get_client() -> OpenAI:
    """Always reads NEBIUS_API_KEY at call time so runtime-set keys are picked up."""
    return OpenAI(
        base_url=NEBIUS_BASE,
        api_key=os.getenv("NEBIUS_API_KEY", ""),
    )


def active_model() -> str:
    """Return the model currently set in the environment (overridable at runtime)."""
    return os.getenv("NEBIUS_MODEL", MODEL_LARGE)
