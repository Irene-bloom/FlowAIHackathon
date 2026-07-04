"""
Tab 4: 我 (Profile) -- writes to the shared UserState so Wallet/Chat use it.
Also shows the vocab book that Chat auto-populates.
"""

from __future__ import annotations
from nicegui import ui

from app import state as S


def render() -> None:
    st = S.get()
    prof = st.profile

    ui.label('你的画像').classes('text-lg font-semibold').style('color:#2d4a3e;')
    ui.label('阿钱靠这些来给你人话建议。').classes('text-xs text-gray-500 mb-2')

    with ui.card().classes('w-full aq-card gap-2'):
        # Capital
        ui.label('💰 你现在有多少钱可以理财？(元)').classes('text-xs')
        cap = ui.number(value=prof.capital, min=100, max=100_000_000, step=1000, format='%.0f')\
            .props('outlined dense').classes('w-full')

        # Risk
        ui.label('🎯 你想要哪种感觉？').classes('text-xs mt-2')
        risk = ui.select(
            options=S.RISK_LABELS,
            value=prof.risk_level,
        ).props('outlined dense').classes('w-full')

        # Horizon
        ui.label('⏰ 这笔钱多久后要用？（年）').classes('text-xs mt-2')
        hz = ui.slider(min=1, max=10, value=prof.horizon_years, step=1).props('label-always')

        # Goal
        ui.label('🌟 想拿来干啥？').classes('text-xs mt-2')
        goal = ui.input(
            value=prof.goal,
            placeholder='比如：3 年后买房 / 存教育金 / 就想理财'
        ).props('outlined dense').classes('w-full')

    def _save():
        st = S.get()
        st.profile.capital = float(cap.value or 5000)
        st.profile.risk_level = risk.value or 'balanced'
        st.profile.horizon_years = int(hz.value or 3)
        st.profile.goal = goal.value or ''
        S.commit()
        ui.notify('存好啦。阿钱下轮回答会用你新填的这些。', type='positive')

    ui.button('保存', on_click=_save, icon='save').classes('aq-btn-primary w-full').props('unelevated')

    # ---- Vocab book ----
    ui.html('<div style="height:16px;"></div>')
    ui.label('📖 我的词汇本').classes('text-md font-semibold').style('color:#2d4a3e;')
    ui.label('阿钱给你解释过的术语都在这里。').classes('text-xs text-gray-500 mb-2')

    if not st.vocab:
        with ui.card().classes('w-full aq-card').style('background:#f6faf6;'):
            ui.label('还是空的。跟阿钱聊天时问过的名词会自动收进来。')\
                .classes('text-xs text-gray-600')
    else:
        for term, plain in st.vocab.items():
            with ui.expansion(term).classes('w-full').style('background:white;'):
                ui.label(plain).classes('text-xs')

    # ---- Debug / reset ----
    ui.html('<div style="height:16px;"></div>')
    with ui.expansion('⚙️ 设置').classes('w-full').style('background:transparent;'):
        ui.button('🧹 重置所有数据（Demo 用）', on_click=_reset)\
            .props('flat').classes('text-xs text-red-500')


def _reset():
    S.reset()
    ui.notify('已重置。刷新一下页面。', type='info')
