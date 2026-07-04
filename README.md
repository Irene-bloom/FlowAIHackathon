# 长 · Chang — 让钱长起来

> **产品**: 说人话的 AI 理财 Agent
> **参赛**: FLOW AI 投资交易 Agent 24h Hackathon · 2026-07-04 北京
> **双轨**: Builder Track (产品) + Trader Track (策略)

## 一句话介绍

一个说人话的 AI 理财助手。你告诉它"我有 5000 块，我是小白"，它用大白话解释每个选项、算清楚风险，然后给一份配置方案——不甩术语、不丢 K 线图。

**名字叙事**: 「长」= 长大、长期、生长。5000 块要长，500 万也要长——从小白到高手，跟着一个 AI 一路长大。

## 核心闭环

```
看到现象 → AI 翻译 → 分析建议 → 行动确认 → 结果验证
```

每一次交互背后都在跑真回测（yfinance 真实数据 + 极端情景压测），
只是小白看到的是"最坏可能亏 400 块"，评委展开可以看到 Sharpe/MaxDD/波动率。

## 双轨映射

| 赛道 | 得分来源 |
|---|---|
| **Builder** | 4 Tab 闭环 · 小白语言 · 每次操作可回滚 |
| **Trader** | 真数据 · 组合回测 · 再平衡/止损/波动率控制 · 3 段极端情景压测 |

## 技术栈

- **LLM**: 火山方舟 (Doubao / DeepSeek)
- **数据**: yfinance + akshare
- **回测**: 纯 pandas/numpy (Option B: 再平衡 + 止损 + 波动率目标 + 权重上下限)
- **UI**: Streamlit (移动端 4 Tab)
- **存储**: SQLite

## 快速开始

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 配置 API
cp .env.example .env
# 编辑 .env 填入 ARK_API_KEY 和 ARK_ENDPOINT_ID

# 3. 跑
streamlit run app/ui.py
```

## 项目结构

```
0704flowAI/
├── app/
│   ├── backtest.py     # 回测引擎 (Option B)
│   ├── data.py         # 数据层
│   ├── agent.py        # Agent 主循环
│   └── ui.py           # Streamlit UI
├── data/               # 数据缓存
├── devlog.md           # 开发者日志 (每步动作)
├── .env.example        # 环境变量模板
└── requirements.txt
```

## 开发进度

详见 [`devlog.md`](./devlog.md)
