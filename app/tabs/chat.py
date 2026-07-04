"""
Tab 1: 聊聊 (Chat)  -- main agent conversation.

Wired to Zhipu GLM-4-Flash via app.llm.
Reply structure enforced by system prompt: 【结论】/【依据】/【适合谁】/【问你】.
CTA button 「开跑」turns a proposal into a paper-trading run (transitions Wallet).
"""

from __future__ import annotations
import time
from typing import Optional

from nicegui import ui

from app import state as S
from app.llm import chat_completion


# ================================================================
# System prompt: 4-part reply + no jargon + 阿钱's voice
# ================================================================

SYSTEM_PROMPT = """你是「阿钱」（A-Qian），一个说人话的 AI 理财助手。
你的用户是理财小白 —— 上过班、有点存款、但看到 K 线图就头晕，
听到"夏普比率"就想关掉 App。

【身份规则】
- 你是用户的朋友，不是客服
- 用「你」不用「您」
- 说话像微信聊天，不是像财经新闻主播
- 遇到用户问的东西你也不确定，直接说"这个我也不好判断"，不要瞎编

【说话规则】
1. 不用金融术语（如"夏普比率"、"再平衡"、"波动率"）。
   如果用户之前已经问过某个术语，且这个术语已经在他的词汇本里，才可以用。
2. 不说百分比，用具体钱数。
   例："回撤 8%" ❌  改成 "最多可能亏 400 块" ✅
3. 每个投资建议都必须给「顺利情况」和「最坏情况」两个具体钱数。
4. 一次回复不超过 6 段，每段不超过 2 句话。

【回复结构 —— 严格四段】
只要用户在问 "我该买啥 / 该不该跟 / 这个东西值得投吗" 这类"求判断"的问题，
你的回复必须按下面四段结构：

【结论】用一句话直接说结论（推荐什么 or 不推荐）
【依据】2-3 句话说为啥（结合数据 / 常识）
【适合谁】说这类做法一般适合什么人（对方能自己判断符不符合）
【问你】反问用户，收集画像信息（存了几年？急着用吗？之前投过啥？）

如果用户只是闲聊 / 问概念 / 求解释，就正常回答，不用四段结构。

【擅长的事】
- 帮小白理解基础金融概念（用大白话 + 生活比喻）
- 根据用户的钱和风险偏好，给组合建议（大盘 ETF / 债券 / 黄金 / 加密 少量搭配）
- 分析用户看到的市场现象、新闻对钱包的影响

【回避】
- 不做择时预测（"下周会不会涨"）
- 不推荐个股（茅台、宁德时代、Tesla 之类）
- 不给保证收益（"稳赚不赔"）
- 不代替用户做决定，你只给"建议 + 依据"，用户自己按【开跑】才算数
"""


# ================================================================
# Guiding bubbles (full human sentences, not command-line-y)
# ================================================================

BUBBLES = [
    ('💰 5000 块起步',
     '我有 5000 块，之前只放过余额宝，现在想开始理财，'
     '从哪个产品先开始？依据是什么？'),
    ('🔥 黄金涨了要跟吗',
     '最近黄金涨得很凶，5% 的仓位换成黄金值得吗？'
     '这种"跟涨"的操作一般适合什么样的人？'),
    ('🎯 泡泡玛特值得投',
     '我看到泡泡玛特最近特别火，它值得投吗？'
     '你结合我的情况帮我分析一下。'),
    ('🎓 什么是夏普比率',
     '我总看到别人说"夏普比率"，这到底是啥？说人话。'),
]


# ================================================================
# Render
# ================================================================

def render() -> None:
    st = S.get()

    ui.label('有点啥想聊的？').classes('text-lg font-semibold').style('color:#2d4a3e;')
    ui.label('别急，说人话就行。').classes('text-xs text-gray-500 mb-2')

    # ---- Guiding bubbles (2x2) ----
    with ui.grid(columns=2).classes('w-full gap-2 mb-3'):
        for label, question in BUBBLES:
            ui.button(label, on_click=lambda q=question: _ask(q))\
                .props('flat').classes('bg-white text-xs').style(
                    'border:1px solid #e5e5e5; border-radius:12px;'
                    'padding:8px 6px; text-transform:none;'
                    'white-space:normal; height:auto; min-height:44px;'
                )

    # ---- Chat log ----
    chat_area = ui.column().classes('w-full gap-2')
    _render_chat_log(chat_area)

    # ---- Input at the bottom of Chat tab ----
    with ui.row().classes('w-full items-end gap-2 mt-2'):
        input_box = ui.input(placeholder='说说你想聊什么…')\
            .props('outlined dense').classes('flex-grow')
        send_btn = ui.button(icon='send')\
            .props('round dense').classes('aq-btn-primary')

        async def _send():
            msg = input_box.value.strip() if input_box.value else ''
            if not msg:
                return
            input_box.value = ''
            _ask(msg, chat_area=chat_area)

        send_btn.on_click(_send)
        input_box.on('keydown.enter', _send)


# ================================================================
# Chat rendering + LLM call
# ================================================================

def _render_chat_log(container) -> None:
    st = S.get()
    container.clear()
    if not st.chat:
        with container:
            with ui.card().classes('w-full').style(
                'background:#f6faf6; border:1px dashed #cfe3d0;'
            ):
                ui.label('点上面的气泡开始聊，或者在下面输入框直接问阿钱。')\
                    .classes('text-sm text-gray-600')
        return
    with container:
        for m in st.chat:
            _render_message(m)


def _render_message(m: S.ChatMessage) -> None:
    is_user = m.role == 'user'
    avatar = '🙋' if is_user else '🌱'
    bg = '#e8f5e8' if is_user else 'white'
    align = 'flex-end' if is_user else 'flex-start'
    with ui.row().classes('w-full').style(f'justify-content:{align};'):
        with ui.card().classes('shadow-sm').style(
            f'max-width:88%; background:{bg}; border-radius:14px; padding:10px 12px;'
        ):
            with ui.row().classes('items-start gap-2'):
                ui.html(f'<div style="font-size:18px;">{avatar}</div>')
                # Preserve line breaks
                text_html = _escape(m.text).replace('\n', '<br>')
                ui.html(f'<div style="font-size:14px; line-height:1.5;">{text_html}</div>')

            # If this assistant message has a "proposal" payload, render 开跑 CTA
            if not is_user and m.kind == 'proposal':
                _render_proposal_card(m.data)


def _render_proposal_card(proposal: dict) -> None:
    """Render the 开跑 CTA at the bottom of an AI proposal message."""
    tickers = proposal.get('tickers', [])
    weights = proposal.get('weights', [])
    label = proposal.get('label', '推荐方案')

    with ui.column().classes('w-full mt-2 gap-1').style(
        'padding:8px; background:#f6faf6; border-radius:10px;'
    ):
        ui.label(f'📋 {label}').classes('text-xs font-semibold')
        for t, w in zip(tickers, weights):
            ui.label(f'· {S.plain_name(t)} — {w*100:.0f}%').classes('text-xs')

        with ui.row().classes('w-full gap-2 mt-1'):
            ui.button('🚀 开跑（跟着这个方案）',
                      on_click=lambda p=proposal: _kick_off_paper_run(p))\
                .classes('aq-btn-primary flex-grow').props('unelevated')


def _escape(s: str) -> str:
    return (s.replace('&', '&amp;')
             .replace('<', '&lt;')
             .replace('>', '&gt;'))


# ================================================================
# Sending a message + LLM call
# ================================================================

def _ask(question: str, chat_area=None) -> None:
    """Public entry: append user msg, call LLM, append assistant msg, save."""
    st = S.get()
    st.chat.append(S.ChatMessage(role='user', text=question, ts=time.time()))
    S.commit()

    # Kick off LLM call
    ui.timer(0.1, lambda: _do_llm_call(chat_area), once=True)

    # Re-render immediately with the user message + "thinking" placeholder
    if chat_area is not None:
        _render_chat_log(chat_area)


def _do_llm_call(chat_area) -> None:
    st = S.get()

    # Build API messages: system + context + short history
    p = st.profile
    ctx = (
        f'\n\n[用户背景] 本金 {p.capital:.0f} 元；'
        f'风险偏好 {S.RISK_LABELS.get(p.risk_level, p.risk_level)}；'
        f'期限 {p.horizon_years} 年；目标：{p.goal or "还没说"}。'
    )
    if st.chat_summary:
        ctx += f'\n[往期对话摘要] {st.chat_summary}'
    if st.vocab:
        ctx += (
            '\n[用户已经学过的术语，你可以直接用]：'
            + '、'.join(st.vocab.keys())
        )
    if st.paper:
        ctx += (
            f'\n[用户当前已开跑方案] {st.paper.label}: '
            f'{list(zip(st.paper.tickers, st.paper.weights))}, '
            f'当前 PnL {st.paper.current_pnl_pct*100:+.1f}%'
        )

    api_msgs = [{'role': 'system', 'content': SYSTEM_PROMPT + ctx}]
    # Send last 10 turns to keep costs down
    for m in st.chat[-10:]:
        api_msgs.append({
            'role': 'user' if m.role == 'user' else 'assistant',
            'content': m.text,
        })

    try:
        resp = chat_completion(messages=api_msgs, temperature=0.7, max_tokens=800)
        reply_text = resp.choices[0].message.content or '（我没想好，你换个方式问问？）'
    except Exception as e:
        reply_text = (
            f'⚠️ 阿钱这边接不上大脑了：`{type(e).__name__}: {e}`\n\n'
            '检查一下 `.env` 里的 API Key。'
        )

    st.chat.append(S.ChatMessage(role='assistant', text=reply_text, ts=time.time()))
    S.commit()

    if chat_area is not None:
        _render_chat_log(chat_area)


# ================================================================
# 开跑 (kick off paper-trading run)
# ================================================================

def _kick_off_paper_run(proposal: dict) -> None:
    """User accepted an AI proposal -> transition Wallet from 未开跑 to 运行中."""
    # This will be implemented in app/paper.py; stub for now
    from app.paper import start_run
    st = S.get()
    run = start_run(
        tickers=proposal.get('tickers', []),
        weights=proposal.get('weights', []),
        kind=proposal.get('kind', 'mixed'),
        label=proposal.get('label', '推荐方案'),
        initial_capital=st.profile.capital,
    )
    st.paper = run
    S.commit()
    ui.notify('✅ 开跑！去【钱袋子】看看你的钱怎么长。', type='positive')
