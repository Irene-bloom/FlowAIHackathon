"""
Tab 2: 看看 (Feed) -- 3 news items filtered by user's portfolio.

For v2 we start with a curated seed list (weekend-Demo-safe), then filter/rank
by the user's actual holdings and generate a "关联你的钱包" explanation for each
via LLM. "问阿钱" jumps back to Chat with the news as context.
"""

from __future__ import annotations
from nicegui import ui

from app import state as S


# Seed news pool (mock; the point is realistic, not real-time)
# Each item: emoji / title / body / related_tickers / plain_hint
SEED_NEWS = [
    {
        'id': 'fed_hold',
        'emoji': '🔴',
        'title': '美联储又不降息了',
        'body': '本次议息会议维持利率不变，市场解读为"还要更久才降"。',
        'related': ['AGG', 'TLT', 'IEF'],
        'hint': '你债券基金里的钱这周可能不涨',
    },
    {
        'id': 'gold_ath',
        'emoji': '🟢',
        'title': '黄金再创新高',
        'body': '国际金价突破前高，避险资金流入。',
        'related': ['GLD'],
        'hint': '如果 3 个月前听阿钱加了一点黄金，今天多赚了',
    },
    {
        'id': 'spy_up2',
        'emoji': '🟡',
        'title': '标普 500 又涨 2%',
        'body': '美股大盘再冲高，AI 概念继续拉动。',
        'related': ['SPY', 'QQQ'],
        'hint': '你美股大盘那部分今天涨了',
    },
    {
        'id': 'btc_swing',
        'emoji': '🟠',
        'title': 'BTC 周末大幅波动',
        'body': '比特币过去 24 小时内波动超 5%，加密市场情绪偏投机。',
        'related': ['BTCUSDT', 'ETHUSDT'],
        'hint': '你加密仓这周会颠簸',
    },
    {
        'id': 'cn_cpi',
        'emoji': '⚪',
        'title': '国内 CPI 数据出炉',
        'body': '通胀低于预期，市场预期货币政策仍宽松。',
        'related': ['GLD'],
        'hint': '钱本身"更值钱"了，短期利好持币观望',
    },
]


def render() -> None:
    st = S.get()

    ui.label('今天有几条跟你有关').classes('text-lg font-semibold').style('color:#2d4a3e;')
    ui.label('别的都可以不看，这几条会影响你的钱包。').classes('text-xs text-gray-500 mb-2')

    # Determine which tickers the user actually holds
    held = set()
    if st.paper:
        held.update(t.upper() for t in st.paper.tickers)
    if st.planned.tickers:
        held.update(t.upper() for t in st.planned.tickers)

    # Rank news: items whose related tickers overlap with user's holdings come first
    def _score(item):
        overlap = len(set(item['related']) & held)
        return -overlap  # more overlap = higher (i.e. smaller value)
    ranked = sorted(SEED_NEWS, key=_score)[:3]

    for item in ranked:
        _render_news_card(item, held)


def _render_news_card(item: dict, held: set) -> None:
    is_related = bool(set(item['related']) & held)
    with ui.card().classes('w-full aq-card').style(
        'border:1px solid #eaeaea;' if not is_related
        else 'border:1px solid #cfe3d0; background:#f6faf6;'
    ):
        with ui.row().classes('items-start gap-2 w-full'):
            ui.html(f'<div style="font-size:22px;">{item["emoji"]}</div>')
            with ui.column().classes('flex-grow gap-1'):
                ui.label(item['title']).classes('text-sm font-bold')
                ui.label(item['body']).classes('text-xs text-gray-700')

        # Plain-language relation
        relation_text = _relation_line(item, held)
        ui.html(f'<div class="aq-tip">💡 {relation_text}</div>')

        # Ask-阿钱 button
        with ui.row().classes('w-full justify-end'):
            ui.button('问阿钱怎么办',
                      on_click=lambda it=item: _ask_aqian_about(it),
                      icon='chat')\
                .props('flat dense').classes('text-xs').style('color:#4a9d5c;')


def _relation_line(item: dict, held: set) -> str:
    hit = list(set(item['related']) & held)
    if not hit:
        return item['hint'] + '（不过你现在还没这方面的持仓）'
    names = '、'.join(S.plain_name(t) for t in hit)
    return f'{item["hint"]}（你持有的 {names}）'


def _ask_aqian_about(item: dict) -> None:
    """Push a user message summarizing the news into Chat, then switch tabs."""
    st = S.get()
    question = (
        f'我看到一条新闻：「{item["title"]}」——{item["body"]}\n'
        f'结合我现在的情况，这条对我意味着什么？我要不要动手？'
    )
    st.chat.append(S.ChatMessage(role='user', text=question))
    S.commit()

    # Trigger LLM in Chat context. We import lazily to avoid circular refs.
    from app.tabs import chat as chat_tab
    ui.notify('已把这条新闻发给阿钱，去【聊聊】看回复。', type='info')
    # Kick the LLM call now (chat_area is None because we're in Feed)
    ui.timer(0.05, lambda: chat_tab._do_llm_call(None), once=True)
