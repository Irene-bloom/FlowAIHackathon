"""
Chang - LLM abstraction layer

Wraps any OpenAI-compatible chat API behind a single get_client() /
chat_completion() interface. Provider is selected via LLM_PROVIDER env var:

  LLM_PROVIDER=zhipu  -> uses ZHIPU_API_KEY + ZHIPU_MODEL + ZHIPU_BASE_URL
  LLM_PROVIDER=ark    -> uses ARK_API_KEY + ARK_ENDPOINT_ID + ARK_BASE_URL

Both providers speak OpenAI-compatible protocol, so switching is a config change.
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

# Load .env from project root
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')


# ================================================================
# Config
# ================================================================

@dataclass
class LLMConfig:
    provider: str      # "zhipu" or "ark"
    api_key: str
    model: str         # for ark this is the endpoint_id
    base_url: str


def load_config() -> LLMConfig:
    provider = os.getenv('LLM_PROVIDER', 'zhipu').strip().lower()

    if provider == 'zhipu':
        key = os.getenv('ZHIPU_API_KEY', '').strip()
        model = os.getenv('ZHIPU_MODEL', 'glm-4-flash').strip()
        base_url = os.getenv('ZHIPU_BASE_URL',
                             'https://open.bigmodel.cn/api/paas/v4').strip()
    elif provider == 'ark':
        key = os.getenv('ARK_API_KEY', '').strip()
        model = os.getenv('ARK_ENDPOINT_ID', '').strip()
        base_url = os.getenv('ARK_BASE_URL',
                             'https://ark.cn-beijing.volces.com/api/v3').strip()
    else:
        raise ValueError(f'Unknown LLM_PROVIDER: {provider!r} (want "zhipu" or "ark")')

    if not key or key.startswith('PASTE') or key.startswith('your_'):
        raise ValueError(f'{provider.upper()} API key is missing or still a placeholder in .env')
    if not model:
        raise ValueError(f'{provider.upper()} model/endpoint is empty in .env')

    return LLMConfig(provider=provider, api_key=key, model=model, base_url=base_url)


# ================================================================
# Client (memoized)
# ================================================================

_client: Optional[OpenAI] = None
_config: Optional[LLMConfig] = None


def get_client() -> tuple[OpenAI, LLMConfig]:
    """Return a lazily-constructed OpenAI-compatible client + its config."""
    global _client, _config
    if _client is None or _config is None:
        _config = load_config()
        _client = OpenAI(api_key=_config.api_key, base_url=_config.base_url)
    return _client, _config


def reset_client() -> None:
    """Force reload on next get_client() (useful after .env changes)."""
    global _client, _config
    _client = None
    _config = None


# ================================================================
# High-level chat helper
# ================================================================

def chat_completion(
    messages: list[dict],
    *,
    temperature: float = 0.7,
    max_tokens: int = 1000,
    tools: Optional[list] = None,
    stream: bool = False,
):
    """
    Thin wrapper over the underlying chat.completions.create.
    Returns whatever the SDK returns (response object or stream iterator).
    """
    client, cfg = get_client()
    kwargs = dict(
        model=cfg.model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if tools:
        kwargs['tools'] = tools
    if stream:
        kwargs['stream'] = True
    return client.chat.completions.create(**kwargs)


def quick_reply(user_msg: str, system_msg: Optional[str] = None,
                temperature: float = 0.7, max_tokens: int = 500) -> str:
    """Convenience one-shot chat call for quick tests."""
    messages = []
    if system_msg:
        messages.append({'role': 'system', 'content': system_msg})
    messages.append({'role': 'user', 'content': user_msg})
    resp = chat_completion(messages, temperature=temperature, max_tokens=max_tokens)
    return resp.choices[0].message.content or ''
