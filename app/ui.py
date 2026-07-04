"""
Chang - Streamlit UI (mobile-first, 4 tabs)

Tab 1 (Chat)   - main agent conversation
Tab 2 (Feed)   - AI-translated news/events
Tab 3 (Wallet) - portfolio + backtest results (two layers)
Tab 4 (Me)     - profile + vocabulary book

Run:
  streamlit run app/ui.py
"""

import os
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Allow "python -m app.ui" and "streamlit run app/ui.py" both to import siblings
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.backtest import BacktestConfig, run_backtest, stress_test
from app.llm import chat_completion, load_config as load_llm_config


# ================================================================
# Chang's system prompt — small-talk friendly, no jargon
# ================================================================

CHANG_SYSTEM_PROMPT = """你是「长」（Chang），一个说人话的 AI 理财助手，专门帮理财小白。

【说话规则】必须严格遵守：
1. 不用金融术语（如"夏普比率"、"再平衡"、"波动率"）。如果用户先问了某个术语，你先解释，之后可以用。
2. 不说百分比，用具体钱数。例："回撤 8%" ❌  改成 "最多可能亏 400 块" ✅
3. 每个建议都必须给「顺利情况」和「最坏情况」两个具体钱数。
4. 说话像朋友，不像客服。用"你" 而不是"您"。
5. 一次回复不超过 4 段，每段不超过 2 句话。
6. 有推荐方案时，用清晰列表列出（几个标的、各占多少钱），别绕。

【擅长的事】
- 帮小白理解基础金融概念
- 根据用户的钱和风险偏好，给出组合建议（大盘 / 债券 / 黄金 等 ETF 搭配）
- 分析用户看到的市场现象、新闻对钱包的影响

【回避】
- 不做择时预测（"下周会不会涨"）
- 不推荐个股（茅台、宁德时代这些）
- 不给保证收益（"稳赚不赔"）
"""


# ================================================================
# Page config -- mobile-first
# ================================================================

st.set_page_config(
    page_title='长 · Chang',
    page_icon='🌱',
    layout='centered',
    initial_sidebar_state='collapsed',
)

# Custom CSS: mobile-friendly, warm palette (avoid finance-app cold blue)
st.markdown("""
<style>
    /* Tighten mobile layout so first screen shows nav + first CTAs */
    .main .block-container {
        max-width: 480px;
        padding-top: 0.5rem;
        padding-bottom: 5rem;
        padding-left: 0.75rem;
        padding-right: 0.75rem;
    }
    h1, h2, h3 { color: #2d4a3e; margin-top: 0.4rem; margin-bottom: 0.4rem; }
    h1 { font-size: 1.4rem; }
    h2 { font-size: 1.15rem; }
    h3 { font-size: 1.02rem; }

    /* Tabs: narrower, denser */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        justify-content: space-around;
        border-bottom: 1px solid #eaeaea;
        margin-top: 0.2rem;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 6px 8px;
        font-size: 14px;
    }
    div[data-testid="stMetricValue"] { font-size: 22px; }
    div[data-testid="stMetricLabel"] { font-size: 12px; }

    /* Compact hero */
    .chang-hero {
        background: linear-gradient(135deg, #f0f9f0 0%, #e8f5e8 100%);
        border-radius: 12px;
        padding: 10px 14px;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .chang-hero-title {
        font-size: 20px;
        font-weight: 700;
        color: #1a3a2e;
        line-height: 1.1;
    }
    .chang-hero-sub {
        font-size: 12px;
        color: #5a6b62;
        margin-top: 2px;
    }

    /* Tip strip */
    .chang-tip {
        background: #fff9e6;
        border-left: 4px solid #ffc107;
        padding: 8px 12px;
        border-radius: 6px;
        margin: 8px 0;
        font-size: 13px;
    }

    /* Buttons — tighter on mobile */
    .stButton > button {
        padding: 0.35rem 0.5rem;
        font-size: 13px;
        min-height: 2.1rem;
        white-space: nowrap;
    }
    /* Chat bubbles a bit smaller */
    [data-testid="stChatMessage"] { padding: 0.4rem 0.6rem; }
</style>
""", unsafe_allow_html=True)


# ================================================================
# Session state defaults
# ================================================================

def _init_state():
    ss = st.session_state
    if 'user_profile' not in ss:
        ss.user_profile = {
            'capital': 5000.0,
            'risk_level': 'balanced',  # conservative / balanced / growth
            'goal': '还没想好',
            'horizon_years': 3,
        }
    if 'chat_history' not in ss:
        ss.chat_history = []
    if 'vocab' not in ss:
        ss.vocab = []  # list of {'term': ..., 'plain': ...}
    if 'portfolio' not in ss:
        # Default portfolio (built for demo before agent kicks in)
        ss.portfolio = {
            'tickers': ['SPY', 'GLD', 'AGG'],
            'weights': [0.40, 0.30, 0.30],
            'start_date': '2020-01-01',
            'created_at': None,
        }
    if 'last_backtest' not in ss:
        ss.last_backtest = None

_init_state()


# ================================================================
# Helpers
# ================================================================

RISK_LABELS = {
    'conservative': '😴 稳当型 · 少赚不亏',
    'balanced':     '😐 平衡型 · 稳中有进',
    'growth':       '😤 进取型 · 敢博更大',
}

TICKER_PLAIN = {
    'SPY': '美股大盘 (500 只大公司)',
    'QQQ': '美股科技 (纳指 100)',
    'GLD': '黄金',
    'AGG': '美国债券',
    'TLT': '美国长期国债',
    'VNQ': '美国房地产',
    'IEF': '美国中期国债',
}

def plain_name(t: str) -> str:
    return TICKER_PLAIN.get(t.upper(), t)


def money(x: float) -> str:
    """Format money the way a real person would say it."""
    if abs(x) >= 10000:
        return f'{x/10000:.1f} 万'
    return f'{x:,.0f} 元'


@st.cache_data(show_spinner=False, ttl=1800)
def cached_backtest(tickers_tuple, weights_tuple, start_date, capital):
    """Cache backtest results in-process (30 min) for snappy demo."""
    cfg = BacktestConfig(
        tickers=list(tickers_tuple),
        weights=list(weights_tuple),
        start_date=start_date,
        initial_capital=capital,
        rebalance_freq='M',
        rebalance_threshold=0.05,
        stop_loss_drawdown=0.20,
    )
    result = run_backtest(cfg)
    return result.summary(), result.equity_curve.to_dict(), result.metrics


# ================================================================
# Header (product hero)
# ================================================================

st.markdown("""
<div class="chang-hero">
  <div style="font-size: 28px;">🌱</div>
  <div>
    <div class="chang-hero-title">长 · Chang</div>
    <div class="chang-hero-sub">让钱，慢慢长起来</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ================================================================
# 4 Tabs
# ================================================================

tab1, tab2, tab3, tab4 = st.tabs(['💬 聊聊', '👀 看看', '💰 钱袋子', '🌱 我'])


# ---------------- Tab 1: 聊聊 (Chat) ----------------
with tab1:
    st.markdown('#### 有点啥想聊的？')
    st.caption('别急，说人话就行。')

    # Guiding bubbles — 2x2 grid, short labels
    c1, c2 = st.columns(2)
    with c1:
        b1 = st.button('💰 5000块起步', use_container_width=True, key='b1')
        b3 = st.button('📊 看我的组合', use_container_width=True, key='b3')
    with c2:
        b2 = st.button('🔥 黄金要跟吗', use_container_width=True, key='b2')
        b4 = st.button('🎓 夏普比率', use_container_width=True, key='b4')

    # Map bubbles -> canned questions
    _bubble_map = {
        'b1': ('我有 5000 块，是理财小白，怎么开始？',   b1),
        'b2': ('最近黄金涨得很凶，我该不该跟一点？',       b2),
        'b3': ('帮我看看我现在这个组合怎么样',            b3),
        'b4': ('什么是夏普比率？说人话',                  b4),
    }
    pending_question = None
    for _, (q, triggered) in _bubble_map.items():
        if triggered:
            pending_question = q
            break

    # Free-form input
    user_input = st.chat_input('说说你想聊什么…')
    if user_input:
        pending_question = user_input

    # Send to LLM if there's a new question
    if pending_question:
        st.session_state.chat_history.append(('user', pending_question))

        # Include user's current portfolio context so Chang knows what "我的组合" means
        p = st.session_state.portfolio
        profile = st.session_state.user_profile
        context_line = (
            f"[背景] 用户当前设定：本金 {profile['capital']:.0f} 元，"
            f"风险偏好 {profile['risk_level']}，目标 {profile['goal']}。"
            f"当前示例组合：{list(zip(p['tickers'], p['weights']))}。"
        )

        # Convert internal chat history to OpenAI-style messages
        api_messages = [
            {'role': 'system', 'content': CHANG_SYSTEM_PROMPT + '\n\n' + context_line},
        ]
        for role, msg in st.session_state.chat_history:
            api_messages.append({
                'role': 'user' if role == 'user' else 'assistant',
                'content': msg,
            })

        try:
            with st.spinner('长在想…'):
                resp = chat_completion(
                    messages=api_messages,
                    temperature=0.7,
                    max_tokens=600,
                )
            reply = resp.choices[0].message.content or '（我没想好，你换个方式问问？）'
        except Exception as e:
            reply = f'⚠️ 我这边接不上大脑了：`{type(e).__name__}: {e}`\n\n检查一下 `.env` 里的 API Key 和 provider。'

        st.session_state.chat_history.append(('assistant', reply))
        st.rerun()

    # Chat log
    st.markdown('---')
    if not st.session_state.chat_history:
        st.info('点上面的气泡开始聊，或者在下面输入框直接问我。')
    else:
        for role, msg in st.session_state.chat_history:
            with st.chat_message('user' if role == 'user' else 'assistant',
                                  avatar='🙋' if role == 'user' else '🌱'):
                st.markdown(msg)


# ---------------- Tab 2: 看看 (Feed) ----------------
with tab2:
    st.markdown('### 今天有 3 条跟你有关')
    st.caption('别的都能不看，这 3 条会影响你的钱包。')

    news_items = [
        {
            'emoji': '🔴',
            'title': '美联储又不降息了',
            'plain': '房贷利率还得等等才能降，你债券基金里的钱可能这周不涨',
            'impact': '影响你 30% 的仓位 (AGG 债券)',
            'suggestion': '别慌，等 12/18 下次开会再看',
        },
        {
            'emoji': '🟢',
            'title': '黄金又创新高了',
            'plain': '如果 3 个月前听我的加了 5% 黄金，你今天多了 120 块',
            'impact': '你现在的组合里有 30% 黄金 (GLD)',
            'suggestion': '现在还能上车吗？问问 AI',
        },
        {
            'emoji': '🟡',
            'title': '标普500 涨了 2%',
            'plain': '你持有的美股大盘今天涨了，估计多赚了 40 块',
            'impact': '你 40% 的钱在这里 (SPY)',
            'suggestion': '不用操作，让它自己长',
        },
    ]

    for n in news_items:
        with st.container(border=True):
            st.markdown(f'### {n["emoji"]} {n["title"]}')
            st.markdown(f'**白话说**：{n["plain"]}')
            st.caption(f'💡 {n["impact"]}')
            c1, c2 = st.columns([1, 1])
            with c1:
                st.button(f'问 AI', key=f'ask_{n["title"]}', use_container_width=True)
            with c2:
                st.caption(n['suggestion'])

    st.markdown('---')
    st.caption('新闻源接入是下一步（Stage 2）。当前用的是场景样例。')


# ---------------- Tab 3: 钱袋子 (Wallet) ----------------
with tab3:
    p = st.session_state.portfolio
    profile = st.session_state.user_profile
    capital = profile['capital']

    with st.spinner('算算你的钱能长成啥样…'):
        try:
            summary, equity_dict, metrics = cached_backtest(
                tuple(p['tickers']), tuple(p['weights']),
                p['start_date'], capital,
            )
            error = None
        except Exception as e:
            summary = equity_dict = metrics = None
            error = f'{type(e).__name__}: {e}'

    if error:
        st.error(f'回测跑不通：{error}\n\n可能是数据源被限流，稍后再试。')
    else:
        # ==== Surface layer: for real newbies ====
        final_val = summary['final_value']
        pnl = summary['pnl']

        st.markdown('### 你的钱')

        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                label='现在大概是',
                value=money(final_val),
                delta=f'+{money(pnl)}' if pnl >= 0 else money(pnl),
            )
        with col2:
            ann_ret = summary['annual_return']
            st.metric(
                label='平均每年长',
                value=f'{ann_ret*100:+.1f}%',
                delta=f'约 {money(capital * ann_ret)}/年',
            )

        st.markdown('#### 未来一年可能长这样')
        vol = summary['annual_vol']
        good = capital * (1 + ann_ret + vol)
        avg = capital * (1 + ann_ret)
        bad = capital * (1 + ann_ret - vol)
        max_dd = summary['max_drawdown']
        worst = capital * (1 + max_dd)

        c1, c2, c3 = st.columns(3)
        c1.markdown(f'😊 **顺利**\n\n{money(good)}')
        c2.markdown(f'😐 **平均**\n\n{money(avg)}')
        c3.markdown(f'😰 **最坏**\n\n{money(bad)}')

        st.markdown(
            f'<div class="chang-tip">'
            f'💡 历史上最惨的一次：{money(worst)} '
            f'({summary["max_drawdown_period"]}, 用了 {summary["recovery_days"]} 天回本)'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ==== Equity curve ====
        if equity_dict:
            equity_series = pd.Series(equity_dict).sort_index()
            equity_series.index = pd.to_datetime(equity_series.index)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=equity_series.index,
                y=equity_series.values,
                mode='lines',
                line=dict(color='#4a9d5c', width=2.5),
                fill='tozeroy',
                fillcolor='rgba(74, 157, 92, 0.12)',
                name='你的钱',
            ))
            fig.add_hline(
                y=capital, line_dash='dash', line_color='#999',
                annotation_text='本金', annotation_position='right',
            )
            fig.update_layout(
                height=280,
                margin=dict(l=0, r=10, t=10, b=0),
                showlegend=False,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='#f0f0f0', tickformat=','),
                plot_bgcolor='white',
            )
            st.plotly_chart(fig, use_container_width=True)

        # ==== Composition ====
        st.markdown('#### 你的钱都放在哪')
        for t, w in zip(p['tickers'], p['weights']):
            amt = capital * w
            st.progress(w, text=f'{plain_name(t)} · {money(amt)} · {w*100:.0f}%')

        # ==== Expandable pro layer (for judges) ====
        with st.expander('🔍 展开看专业指标'):
            st.markdown('**回测统计**')
            m = summary
            col_l, col_r = st.columns(2)
            with col_l:
                st.markdown(f"- 年化收益: **{m['annual_return']*100:+.2f}%**")
                st.markdown(f"- 年化波动: **{m['annual_vol']*100:.2f}%**")
                st.markdown(f"- Sharpe: **{m['sharpe']:.2f}**")
                st.markdown(f"- Sortino: **{m['sortino']:.2f}**")
            with col_r:
                st.markdown(f"- 最大回撤: **{m['max_drawdown']*100:.2f}%**")
                st.markdown(f"- 回撤时段: `{m['max_drawdown_period']}`")
                st.markdown(f"- 回本天数: **{m['recovery_days']}**")
                st.markdown(f"- 胜率: **{m['win_rate']*100:.1f}%**")
                st.markdown(f"- 调仓次数: **{m['num_trades']}**")

            st.markdown('---')
            st.markdown('**极端情景压力测试**')
            st.caption('把同样的组合放到历史上 3 个至暗时刻里跑一遍')
            if st.button('▶️ 跑压测 (2008 / 2020 / 2022)', key='stress_btn'):
                with st.spinner('压测中…'):
                    try:
                        cfg = BacktestConfig(
                            tickers=p['tickers'],
                            weights=p['weights'],
                            start_date=p['start_date'],
                            initial_capital=capital,
                            rebalance_freq='M',
                            rebalance_threshold=0.05,
                            stop_loss_drawdown=0.20,
                        )
                        stress = stress_test(cfg)
                        for name, res in stress.items():
                            if 'error' in res:
                                st.error(f'{name}: {res["error"]}')
                            else:
                                st.markdown(
                                    f"**{name}**: "
                                    f"总收益 {res['total_return']*100:+.2f}% · "
                                    f"最大回撤 {res['max_drawdown']*100:.2f}% · "
                                    f"Sharpe {res['sharpe']:.2f}"
                                )
                    except Exception as e:
                        st.error(f'压测失败: {e}')

        st.caption(
            f'📊 基于真实历史数据 (yfinance/akshare) · 回测周期 '
            f'{summary["period"]}'
        )


# ---------------- Tab 4: 我 (Profile) ----------------
with tab4:
    profile = st.session_state.user_profile

    st.markdown('### 你的画像')

    new_capital = st.number_input(
        '💰 你现在有多少钱可以理财？(元)',
        min_value=100.0, max_value=100_000_000.0,
        value=float(profile['capital']),
        step=1000.0,
    )
    new_risk = st.radio(
        '🎯 你想要哪种感觉？',
        options=list(RISK_LABELS.keys()),
        format_func=lambda x: RISK_LABELS[x],
        index=list(RISK_LABELS.keys()).index(profile['risk_level']),
    )
    new_horizon = st.slider(
        '⏰ 这笔钱多久后要用？',
        min_value=1, max_value=10,
        value=int(profile['horizon_years']),
    )
    new_goal = st.text_input(
        '🌟 想拿来干啥？',
        value=profile['goal'],
        placeholder='比如：3 年后买房 / 存教育金 / 就想理财',
    )

    if st.button('保存', use_container_width=True, type='primary'):
        st.session_state.user_profile = {
            'capital': new_capital,
            'risk_level': new_risk,
            'horizon_years': new_horizon,
            'goal': new_goal,
        }
        # Clear backtest cache so wallet reflects new capital
        cached_backtest.clear()
        st.success('存好啦。去【钱袋子】看看新数字。')

    st.markdown('---')

    # Vocabulary book
    st.markdown('### 📖 我的词汇本')
    st.caption('AI 给你解释过的术语，都在这里')
    if not st.session_state.vocab:
        st.info('还是空的。跟 AI 聊天时问过的名词会自动收进来。')
    else:
        for v in st.session_state.vocab:
            with st.expander(v['term']):
                st.markdown(v['plain'])


# ================================================================
# Footer
# ================================================================
st.markdown('---')
st.caption(
    '🌱 长 · Chang v0.1 (dev) · '
    'FLOW AI 24h Hackathon 2026 · '
    '[GitHub](https://github.com/Irene-bloom/FlowAIHackathon)'
)
