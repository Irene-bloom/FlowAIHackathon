"""
Tab 3: 钱袋子 (Wallet) -- dual state.

State A: 未开跑 -> show a compact prompt telling the user to go to Chat.
State B: 运行中 -> show current NAV, PnL, allocation, and an expandable
                   "🔍 展开看专业指标" panel (Sharpe/MaxDD/stress) for judges.
"""

from __future__ import annotations
import time

from nicegui import ui
import plotly.graph_objects as go

from app import state as S
from app.paper import refresh_run


def render() -> None:
    st = S.get()

    if st.paper is None:
        _render_pre_kickoff(st)
    else:
        _render_running(st)


# ================================================================
# State A: 未开跑
# ================================================================

def _render_pre_kickoff(st: S.UserState) -> None:
    with ui.card().classes('w-full aq-card'):
        ui.label('还没开跑').classes('text-lg font-semibold').style('color:#2d4a3e;')
        ui.label('你还没有正在跟着跑的方案。').classes('text-sm text-gray-700 mt-1')
        ui.html('<hr style="border:0; border-top:1px solid #eee; margin:10px 0;">')
        ui.label('先去【聊聊】告诉阿钱你的情况：').classes('text-xs text-gray-600')
        ui.label('· 你有多少钱').classes('text-xs text-gray-600')
        ui.label('· 想稳还是想搏').classes('text-xs text-gray-600')
        ui.label('· 大概什么时候用').classes('text-xs text-gray-600')
        ui.html('<div style="height:8px;"></div>')
        ui.label('阿钱会给你 2-3 个方案，选一个按【开跑】，'
                 '这里就会开始每天真更新。').classes('text-xs text-gray-600 mt-1')


# ================================================================
# State B: 运行中
# ================================================================

def _render_running(st: S.UserState) -> None:
    paper = st.paper

    # Try to refresh NAV against latest prices (best-effort)
    try:
        refresh_run(paper)
        S.commit()
    except Exception as e:
        ui.notify(f'刷新报价失败: {e}', type='warning')

    pnl = paper.current_nav - paper.initial_capital
    pnl_pct = paper.current_pnl_pct
    running_days = int((time.time() - (paper.started_at or time.time())) / 86400) if paper.started_at else 0

    # ---- Status strip ----
    with ui.card().classes('w-full aq-card').style(
        'background: linear-gradient(135deg, #f0f9f0 0%, #e8f5e8 100%);'
    ):
        with ui.row().classes('items-center gap-2 w-full'):
            dot_color = '#4a9d5c' if not paper.stopped_out else '#e57373'
            ui.html(
                f'<div style="width:10px; height:10px; border-radius:50%;'
                f'background:{dot_color};"></div>'
            )
            status = '运行中' if not paper.stopped_out else '已止损'
            ui.label(f'🟢 {status} · 第 {running_days} 天').classes('text-xs').style(
                'color:#2d4a3e; font-weight:600;'
            )
        ui.label(paper.label).classes('text-xs text-gray-500 mt-1')

    # ---- Big number: current NAV ----
    with ui.card().classes('w-full aq-card'):
        ui.label('你的钱').classes('text-sm text-gray-500')
        ui.label(S.money(paper.current_nav)).classes('text-3xl font-bold').style(
            'color:#2d4a3e;'
        )
        pnl_color = '#4a9d5c' if pnl >= 0 else '#e57373'
        ui.html(
            f'<div style="color:{pnl_color}; font-size:14px; margin-top:2px;">'
            f'{"↑" if pnl >= 0 else "↓"} '
            f'{"+" if pnl >= 0 else ""}{S.money(pnl)} '
            f'({pnl_pct*100:+.2f}%)</div>'
        )

    # ---- NAV chart ----
    if paper.nav_history and len(paper.nav_history) >= 2:
        _render_nav_chart(paper)

    # ---- Composition ----
    with ui.card().classes('w-full aq-card'):
        ui.label('你的钱都放在哪').classes('text-sm font-semibold')
        for t, w in zip(paper.tickers, paper.weights):
            amt = paper.current_nav * w
            with ui.row().classes('items-center w-full gap-2 mt-1'):
                ui.label(f'{S.plain_name(t)}').classes('text-xs flex-grow')
                ui.label(f'{S.money(amt)}').classes('text-xs').style('color:#4a9d5c;')
                ui.label(f'{w*100:.0f}%').classes('text-xs w-8 text-right text-gray-500')
            ui.linear_progress(w, show_value=False).props('rounded').classes('w-full').style(
                '--q-primary: #4a9d5c;'
            )

    # ---- Actions ----
    with ui.card().classes('w-full aq-card').style('background:transparent; box-shadow:none;'):
        with ui.row().classes('gap-2 w-full'):
            ui.button('⚙️ 换方案',
                      on_click=_switch_plan)\
                .props('outline').classes('flex-grow text-xs')
            ui.button('⏸ 暂停跟单',
                      on_click=_stop_run)\
                .props('outline').classes('flex-grow text-xs')

    # ---- Expandable: 专业指标 for judges ----
    with ui.expansion('🔍 展开看专业指标', icon='analytics').classes('w-full').style(
        'background:white; border-radius:14px; margin-top:12px;'
    ):
        _render_pro_panel(paper)


def _render_nav_chart(paper: S.PaperRun) -> None:
    xs = [h['ts'] for h in paper.nav_history]
    ys = [h['nav'] for h in paper.nav_history]
    import pandas as pd
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pd.to_datetime(xs, unit='s'),
        y=ys,
        mode='lines',
        line=dict(color='#4a9d5c', width=2.5),
        fill='tozeroy',
        fillcolor='rgba(74, 157, 92, 0.12)',
        name='你的钱',
    ))
    fig.add_hline(y=paper.initial_capital, line_dash='dash', line_color='#999',
                  annotation_text='本金', annotation_position='right')
    fig.update_layout(
        height=200,
        margin=dict(l=0, r=10, t=10, b=0),
        showlegend=False,
        xaxis=dict(showgrid=False, tickformat='%m/%d'),
        yaxis=dict(showgrid=True, gridcolor='#f0f0f0'),
        plot_bgcolor='white',
    )
    ui.plotly(fig).classes('w-full')


def _render_pro_panel(paper: S.PaperRun) -> None:
    """The section judges care about: Sharpe/MaxDD/stress."""
    if len(paper.nav_history) < 2:
        ui.label('数据太少，还没法算稳定指标（至少要 2 天）').classes(
            'text-xs text-gray-500'
        )
    else:
        # Compute quick stats over the paper run's NAV history
        import numpy as np
        import pandas as pd
        s = pd.Series([h['nav'] for h in paper.nav_history])
        r = s.pct_change().dropna()
        if len(r) > 1:
            ann = (1 + r.mean()) ** 252 - 1
            vol = r.std() * (252 ** 0.5)
            sh = ann / vol if vol > 1e-9 else 0.0
            cummax = s.cummax()
            dd = (s / cummax - 1).min()
            with ui.column().classes('gap-1'):
                ui.label(f'• 年化收益（估算）: {ann*100:+.2f}%').classes('text-xs')
                ui.label(f'• 波动率:           {vol*100:.2f}%').classes('text-xs')
                ui.label(f'• Sharpe:            {sh:.2f}').classes('text-xs')
                ui.label(f'• 已发生最大回撤:   {dd*100:+.2f}%').classes('text-xs')

    ui.html('<hr style="border:0; border-top:1px solid #eee; margin:10px 0;">')
    ui.label('极端情景压力测试').classes('text-xs font-semibold')
    ui.label('拿同样的组合放到 2008 / 2020 / 2022 三段最惨的时期跑一遍').classes(
        'text-xs text-gray-500 mb-2'
    )

    stress_state = {'running': False}

    async def _run_stress():
        if stress_state['running']:
            return
        stress_state['running'] = True
        ui.notify('压测跑起来了，估计要 20-40 秒...', type='info')
        try:
            from app.backtest import BacktestConfig, stress_test
            # Only stock tickers can pass through akshare stress_test
            stock_only = [(t, w) for t, w in zip(paper.tickers, paper.weights)
                          if not S.is_crypto(t)]
            if not stock_only:
                ui.notify('你的组合都是加密，压测目前只支持股票部分。', type='warning')
                return
            # Renormalize weights
            total = sum(w for _, w in stock_only)
            tickers = [t for t, _ in stock_only]
            weights = [w / total for _, w in stock_only]
            cfg = BacktestConfig(
                tickers=tickers, weights=weights,
                start_date='2015-01-01',
                initial_capital=paper.initial_capital,
                rebalance_freq='M',
                rebalance_threshold=0.05,
                stop_loss_drawdown=0.20,
            )
            results = stress_test(cfg)
            for name, res in results.items():
                if 'error' in res:
                    ui.notify(f'{name}: {res["error"]}', type='negative')
                else:
                    ui.label(
                        f'• {name}: 总收益 {res["total_return"]*100:+.2f}% · '
                        f'MaxDD {res["max_drawdown"]*100:.2f}% · '
                        f'Sharpe {res["sharpe"]:.2f}'
                    ).classes('text-xs')
        finally:
            stress_state['running'] = False

    ui.button('▶ 跑压测', on_click=_run_stress)\
        .props('flat').classes('text-xs').style('color:#4a9d5c;')


# ================================================================
# Actions
# ================================================================

def _switch_plan() -> None:
    ui.notify('去【聊聊】跟阿钱说"我想换方案"，它会给你新的选项。', type='info')


def _stop_run() -> None:
    st = S.get()
    st.paper = None
    S.commit()
    ui.notify('已暂停。想重新开跑就再去【聊聊】。', type='info')
