"""
Quick sanity test for whichever LLM provider is configured in .env.
Run: python scripts/test_llm.py
"""

import sys
from pathlib import Path

# Make "app" package importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm import chat_completion, load_config


def main() -> int:
    try:
        cfg = load_config()
    except Exception as e:
        print(f'[FAIL] config: {e}')
        return 1

    print(f'[ok] Provider: {cfg.provider}')
    print(f'[ok] Model:    {cfg.model}')
    print(f'[ok] Base URL: {cfg.base_url}')
    print(f'[ok] Key len:  {len(cfg.api_key)}')

    print('\n[send] Testing a small chat call...')
    try:
        resp = chat_completion(
            messages=[
                {'role': 'system',
                 'content': '你是"长"（Chang），一个说人话的 AI 理财助手。别用金融术语。'},
                {'role': 'user',
                 'content': '你好，我有 5000 块，是理财小白，怎么开始？两三句话就行。'},
            ],
            temperature=0.7,
            max_tokens=300,
        )
    except Exception as e:
        print(f'\n[FAIL] {type(e).__name__}: {e}')
        return 1

    msg = resp.choices[0].message.content or ''
    print(f'\n[reply]\n{msg}\n')
    usage = getattr(resp, 'usage', None)
    if usage:
        print(f'[usage] prompt={usage.prompt_tokens}, '
              f'completion={usage.completion_tokens}, '
              f'total={usage.total_tokens}')

    print('\n[PASS] LLM is working. Ready to wire up the agent.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
