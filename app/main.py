"""
阿钱 · Main NiceGUI entry point (mobile-first, native bottom-nav)

Run:  python -m app.main
Then: http://localhost:8080  (or on your phone via LAN IP)

Design principles:
  - All 4 tabs read/write from ONE shared UserState (see app/state.py).
  - Every action persists to SQLite so the app survives restart.
  - Bottom navigation like a native app (💬 聊聊 / 👀 看看 / 💰 钱袋子 / 🌱 我).
  - Chat "开跑" transitions Wallet from "未开跑" to "运行中" state.
"""

from __future__ import annotations
from nicegui import ui, app as nicegui_app

from app import state as S
from app.tabs import chat as tab_chat
from app.tabs import feed as tab_feed
from app.tabs import wallet as tab_wallet
from app.tabs import profile as tab_profile


# ================================================================
# Global styles: mobile-first, warm palette
# ================================================================

CUSTOM_CSS = """
:root {
  --aqian-green: #4a9d5c;
  --aqian-green-soft: #e8f5e8;
  --aqian-green-deep: #2d4a3e;
  --aqian-cream: #fdfaf3;
  --aqian-warn: #ffc107;
  --aqian-text: #1a3a2e;
}
html, body { background: var(--aqian-cream); color: var(--aqian-text); }
body { font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; }

/* Cap main content to phone width, centered on desktop */
.q-page-container { max-width: 480px; margin: 0 auto !important; }
.q-page { background: var(--aqian-cream); }

/* Top header hero */
.aq-hero {
  background: linear-gradient(135deg, #f0f9f0 0%, #e8f5e8 100%);
  padding: 12px 16px;
  display: flex; align-items: center; gap: 10px;
  border-bottom: 1px solid #eaeaea;
}
.aq-hero-title { font-size: 20px; font-weight: 700; color: var(--aqian-green-deep); line-height: 1.15; }
.aq-hero-sub { font-size: 12px; color: #5a6b62; margin-top: 2px; }

/* Bottom nav */
.q-tabs { background: white; border-top: 1px solid #eaeaea; }
.q-tab { min-height: 56px; padding: 4px 0; }
.q-tab__icon { font-size: 22px; }
.q-tab__label { font-size: 11px; margin-top: 2px; }
.q-tab--active { color: var(--aqian-green) !important; }

/* Cards */
.aq-card {
  background: white; border-radius: 14px; padding: 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04); margin-bottom: 12px;
}

/* Primary button */
.aq-btn-primary {
  background: var(--aqian-green) !important;
  color: white !important;
  border-radius: 999px !important;
  padding: 10px 18px !important;
  font-weight: 600;
}

/* Tips */
.aq-tip {
  background: #fff9e6; border-left: 4px solid var(--aqian-warn);
  padding: 8px 12px; border-radius: 6px; font-size: 13px;
  margin: 8px 0;
}
"""


# ================================================================
# Page composition
# ================================================================

@ui.page('/')
def index_page():
    """Single-page app; the 4 tabs share a container we re-render on tab-change."""
    # Load state on first render for THIS session
    S.get()

    ui.add_head_html(
        '<meta name="viewport" content="width=device-width, initial-scale=1, '
        'maximum-scale=1, user-scalable=no">'
    )
    ui.add_head_html(f'<style>{CUSTOM_CSS}</style>')

    # ---------- Header (hero) ----------
    with ui.element('div').classes('aq-hero'):
        ui.html(
            '<div style="font-size:26px;">🌱</div>'
            '<div>'
            '  <div class="aq-hero-title">阿钱 · A-Qian</div>'
            '  <div class="aq-hero-sub">让钱，稳稳地长起来</div>'
            '</div>'
        )

    # ---------- Body: one panel per tab ----------
    # NiceGUI's ui.tab_panels lets us cheaply swap Tab content.
    with ui.tab_panels(value='chat').classes('w-full').style(
        'background: var(--aqian-cream); padding: 12px 12px 80px 12px;'
        'min-height: calc(100vh - 130px);'
    ) as panels:
        with ui.tab_panel('chat'):
            tab_chat.render()
        with ui.tab_panel('feed'):
            tab_feed.render()
        with ui.tab_panel('wallet'):
            tab_wallet.render()
        with ui.tab_panel('me'):
            tab_profile.render()

    # ---------- Bottom nav (fixed) ----------
    with ui.element('div').style(
        'position: fixed; bottom: 0; left: 0; right: 0; z-index: 100;'
        'background: white; max-width: 480px; margin: 0 auto;'
    ):
        with ui.tabs(value='chat').classes('w-full').bind_value_to(panels, 'value') as tabs:
            ui.tab('chat',   label='聊聊',   icon='chat')
            ui.tab('feed',   label='看看',   icon='visibility')
            ui.tab('wallet', label='钱袋子', icon='account_balance_wallet')
            ui.tab('me',     label='我',     icon='eco')


# ================================================================
# Cross-tab navigation helper
# ================================================================

def go_to(tab_name: str) -> None:
    """Programmatic Tab switch, callable from any Tab (e.g. Feed -> Chat)."""
    # NiceGUI stores tab_panels value in Vue state; broadcast via storage
    nicegui_app.storage.user['requested_tab'] = tab_name


# ================================================================
# Entry point
# ================================================================

def main():
    ui.run(
        title='阿钱 · A-Qian',
        favicon='🌱',
        host='0.0.0.0',
        port=8080,
        show=False,          # Don't try to open a browser window on the server
        reload=False,        # Reload disabled for stability during Demo
        storage_secret='aqian-hackathon-2026-demo',
    )


if __name__ == '__main__':
    main()
