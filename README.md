# 阿钱 · A-Qian — 让钱，稳稳地长起来

> **产品**: 说人话的 AI 理财 Agent，移动端 first
> **参赛**: FLOW AI 投资交易 Agent 24h Hackathon · 2026-07-04 北京
> **双轨**: Builder Track (产品) + Trader Track (策略)

## 一句话介绍

一个说人话的 AI 理财朋友。你告诉阿钱"我有 5000 块，是小白"，
阿钱用大白话解释每个选项、算清楚风险，然后给一份配置方案 ——
不甩术语、不丢 K 线图，还能一键跟着跑。

**名字叙事**: 「阿钱」= 你的理财小伙伴。
就像"阿明""阿珍"一样，有性格、有陪伴感，但不掉价。
从 5000 到 500 万，阿钱都在。

## 核心闭环

```
看到现象 → 阿钱翻译 → 分析建议 → 【开跑】→ 每天真更新
```

每次交互背后都在跑**真回测**（akshare 真实数据 + 极端情景压测），
每一份"开跑"下去的方案都进入 **Paper Engine 每天真的算 PnL**。

## 双轨映射

| 赛道 | 得分来源 |
|---|---|
| **Builder** | 移动端 4 Tab 底部导航 · 全程小白语言 · 每次决策可回滚 |
| **Trader** | 真数据 · Sharpe/MaxDD/波动率 · 再平衡/止损/波动率控制 · 3 段极端情景压测 · Paper Engine 双引擎 (股票+加密) |

## 技术栈

- **LLM**: 智谱 GLM-4-Flash（意图理解 + 结果解释；策略/回测/风控/执行走 deterministic Python）
- **数据**: akshare (股票) + Binance testnet (加密)
- **回测**: 纯 pandas/numpy (Option B: 再平衡 + 止损 + 波动率目标 + 权重上下限)
- **执行**: 自研 Paper Engine (股票, SQLite) + Binance testnet (加密, 7×24 波动)
- **UI**: NiceGUI (原生移动端底部 Tab)
- **存储**: SQLite (关掉重开状态还在)

## 快速开始

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 配置 API
cp .env.example .env
# 编辑 .env, 填 ZHIPU_API_KEY

# 3. 跑
python -m app.main
# 浏览器打开 http://localhost:8080
# 手机同 WiFi 打开 http://<你电脑IP>:8080
```

## 项目结构

```
0704flowAI/
├── app/
│   ├── backtest.py     # 回测引擎 (Option B)
│   ├── llm.py          # LLM 抽象层 (zhipu / ark 切换)
│   ├── state.py        # 中央 UserState + SQLite 持久化
│   ├── memory.py       # 长记忆 (对话摘要 + 用户画像)
│   ├── paper.py        # Paper Trading Engine (股票+加密)
│   ├── strategy.py     # 策略 DSL + 内置策略库
│   ├── main.py         # NiceGUI 主入口 (底部 4 Tab)
│   └── tabs/
│       ├── chat.py     # 💬 聊聊 (含【开跑】CTA)
│       ├── feed.py     # 👀 看看 (组合关联新闻)
│       ├── wallet.py   # 💰 钱袋子 (双态: 未开跑/运行中)
│       └── profile.py  # 🌱 我 (画像 + 词汇本)
├── data/               # 数据缓存
├── devlog.md           # 开发者日志 (每步动作)
├── .env.example        # 环境变量模板
└── requirements.txt
```

## 开发进度

详见 [`devlog.md`](./devlog.md)
