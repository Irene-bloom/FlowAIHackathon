# FlowAI · 开发者日志

> **项目**: FlowAI - 小白友好的 AI 理财 Agent
> **赛事**: FLOW AI 投资交易 Agent 24h Hackathon
> **时间**: 2026-07-04 ~ 2026-07-05
> **仓库**: https://github.com/Irene-bloom/FlowAIHackathon
> **赛道**: Builder + Trader 双轨

---

## 日志规范

每条 Entry 记录格式：

```
## Entry #N · YYYY-MM-DD HH:MM · 标题
- 动作:  做了什么
- 原因:  为什么这么做
- 结果:  产出/影响/后续动作
```

---

## Entry #0 · 2026-07-04 · 项目立项与设计定稿

### 一、产品定义

**面向人群**: 想理财但看不懂的真小白（不敢开始、术语看不懂、怕被割、焦虑但拖延）。

**核心洞察**: 小白不主动规划理财，全是"被触发"才打开 App。所以按"心理时刻"设计功能，不按"功能模块"。

**四个心理时刻**:
| 时刻 | 内心 OS | 对应 Tab |
|---|---|---|
| ① 冲动时刻 | "同事说买黄金赚了 20%…" | ① 聊聊 (Chat) |
| ② 焦虑时刻 | "工资躺余额宝三年了…" | ② 看看 (Feed) |
| ③ 怀疑时刻 | "上次配的方案现在亏了…" | ③ 钱袋子 (Wallet) |
| ④ 迷茫时刻 | "'夏普比率'是啥来着…" | ④ 我 (Profile) |

**核心闭环**: 看到现象 → AI 翻译 → 分析建议 → 行动确认 → 结果验证。

### 二、双轨评分策略

**创始人原话锚点**:
> "会聊天的金融助手不算。会总结研报的工具不算。包装得很漂亮的 Demo 更不算。
> 目标理解 → 任务拆解 → 数据调用 → 策略生成 → 风险判断 → 执行反馈，闭环。"

**Builder Track 加分点**:
- 4 Tab 完整闭环
- 全程小白语言（3 条硬规则见下）
- 每个建议都可以"回滚"

**Trader Track 加分点** (藏在展开层, 表层小白看不到):
- 真数据 (yfinance)
- 真回测 (年化 / Sharpe / MaxDD / 波动率)
- 3 段极端情景压测 (2008 金融危机 / 2020 疫情 / 2022 加息)
- 策略层规则 (再平衡 / 止损 / 波动率目标)

### 三、四个 Tab 设计

**Tab ① 聊聊 (Chat)** - 主交互入口，复用完整闭环
- 3 个引导气泡：新手入门 / 现象分析 / 组合体检
- Agent 回复自带"[🔍 我是怎么算的]"折叠层 (Trader 分)
- 每次建议有 [👍 / 👎 / 🤔] 三键，全部可回滚

**Tab ② 看看 (Feed)** - AI 现象翻译器
- 每天 3 条与用户组合关联的"人话新闻"
- 每条包含：白话翻译 + 与你的钱包关联度 + 建议动作
- 点击深入触发 Chat

**Tab ③ 钱袋子 (Wallet)** - 结果验证
- 表层：具体钱数 + 😊/😐/😰 三档预期
- 展开层：完整回测指标 (Sharpe/MaxDD/极端情景对比)
- Paper trading 实时曲线

**Tab ④ 我 (Profile)** - 个性化 + 成长
- 风险偏好、目标、词汇本 (AI 教过的术语自动收藏)
- **词汇本机制**：小白学过的词，AI 后续对话可以使用 → 动态词汇边界

### 四、关键设计决策

**决策 1: 显示层采用【方案 B】分层展示**
- 表层 = 小白语言 (钱数 / emoji / 白话)
- 展开层 = 专业指标 (Sharpe / MaxDD / 极端情景)
- 一次输入，两种输出——同时讨好双轨评委

**决策 2: 小白语言 3 条硬规则**
1. 不出现百分比 → 换算成具体钱数 ("回撤 8%" ❌ / "最多可能亏 400 块" ✅)
2. 不出现术语 → 除非用户词汇本里有 ("再平衡" ❌ / "调整比例" ✅)
3. 每个建议都必给"最好情况"和"最坏情况"两个数

**决策 3: 回测引擎选【Option B 中等版】**
- 支持: 买入持有 + 定期再平衡 + 阈值再平衡 + 止损 + 波动率目标 + 权重上下限
- 拒绝: 因子模型 / 择时信号 (24h 内做不完，且不是 idea 核心)
- 代码目标: 200 行内，模块清晰

**决策 4: 信息源采用 3 阶段策略**
- Stage 1 (前 14h): 硬编码 20 条预制新闻，跑通闭环
- Stage 2 (14-18h): 接 RSS (财联社 / Investing) + fallback 到 Mock
- Stage 3 (可选): 生产环境话术，Demo 现场切换展示
- **不做实时爬虫** (24h 内翻车代价太大)

**决策 5: 移动端用 Streamlit 而非原生 App**
- 用 `layout="centered"` + 手机浏览器扫码打开
- 原生 App 24h 内做不完，且没必要
- 评委实际测试时也是用手机浏览器

### 五、24 小时时间预算

| 时段 | 任务 | 输出 |
|---|---|---|
| 0-1h | 环境 / git / devlog / API 打通 | 项目可跑 |
| **1-3h** | **回测引擎 (核心)** | 输入 tickers+权重, 输出全指标 |
| 3-4h | 策略层: 再平衡 + 止损 | 引擎升级 |
| 4-5h | 极端情景模块 | 3 段压测 |
| 5-6h | Agent 主循环 + Tool Calling | Agent 能调回测 |
| 6-9h | Tab ① 聊聊闭环 | 对话触发回测 |
| 9-13h | Tab ③ 钱袋子 + 展开层 | 双层展示 |
| 13-16h | Tab ② 看看 + Mock 新闻 | 现象触发对话 |
| 16-19h | Tab ④ 我 + 词汇本 + Paper Trading | 4 Tab 完整 |
| 19-21h | 端到端联调 + 错误兜底 | 断网也不崩 |
| 21-23h | Demo 剧本 + 3 profile 缓存 | 现场秒开 |
| 23-24h | Buffer / 睡觉 | 别猝死 |

### 六、技术选型

| 层 | 选择 | 理由 |
|---|---|---|
| LLM | 火山方舟 (Doubao 1.5 pro) | 用户有 key, 中文强 |
| Agent 框架 | 手写 Tool Calling loop | 24h 内不用 LangChain, 排错更快 |
| 数据 | yfinance + akshare (fallback) | 免费, 无 key, 代码几行 |
| 回测 | 纯 pandas + numpy | 200 行足够, 无依赖风险 |
| UI | Streamlit | 4h 上线的方案 |
| 存储 | SQLite (in-memory OK) | Demo 不需要多用户 |
| 部署 | 本地 + ngrok / 现场跑 | 别折腾 Docker |

### 七、风险清单

| 风险 | 概率 | 缓解方案 |
|---|---|---|
| yfinance 在国内被墙 | 高 | 备用 akshare / stooq |
| 火山方舟 tool-calling 格式差异 | 中 | 先跑通 1 个 tool 再往下做 |
| 前视偏差 (look-ahead bias) | 中 | 硬约束: 决策只用 t-1 之前数据 |
| 现场评委输入极端 (100 块) | 中 | 意图解析加规则, 变成加分项 |
| Streamlit 多轮状态冲突 | 中 | 用 `st.session_state`, 别用 stream |
| Demo 时网络抖动 | 高 | 所有 API 调用 try/except + 缓存兜底 |
| 做太多花哨功能, 闭环没跑通 | **最高** | 每 4h 自检: 从对话到 PnL 能不能动 |

### 八、安全声明

- ⚠️ 用户初次分享了火山引擎登录密码 + AK/SK
- 已提醒用户: 比赛后立刻改密码 + 禁用 AK/SK
- `.env` 已加入 `.gitignore`, 密钥不会推到公开仓库
- 本 devlog 与所有代码文件均不包含真实密钥

---

## Entry #1 · 2026-07-04 · 环境搭建

- **动作**: 检查环境 → 装 Python 3.11.9 → 验证 pip → 初始化 git → 关联 GitHub 远程
- **原因**: 系统自带 Python 3.8.1 太老, yfinance / streamlit 新版本都不支持, 硬用会有玄学 bug
- **过程**:
  1. 用户下载 Python 3.11.9 安装包
  2. 安装时勾选 "Add python.exe to PATH" + "Use admin privileges"
  3. 启用 "Disable path length limit" (解除 260 字符路径限制)
  4. 重启 VS Code 后验证: `python --version` → 3.11.9 ✅, `pip --version` → 24.0 ✅
  5. `git init -b main` + `git remote add origin https://github.com/Irene-bloom/FlowAIHackathon.git`
- **结果**:
  - Python 3.11.9 + pip 24.0 就绪
  - Git 已初始化到 main 分支, 远程指向 Irene-bloom/FlowAIHackathon
  - 遇到 VS Code 提示 "无法解析 /usr/bin/python3" → 无影响, 用户可在 Python 扩展里选新解释器消除

---

## Entry #2 · 2026-07-04 · 项目骨架

- **动作**: 创建 `.gitignore` / `.env.example` / `requirements.txt` / `README.md` / `app/__init__.py` / `data/.gitkeep`
- **原因**: 先把结构立起来, 后续代码有地方放
- **产出**:
  ```
  0704flowAI/
  ├── .gitignore          # 排除 .env 和缓存
  ├── .env.example        # 环境变量模板 (安全)
  ├── requirements.txt    # 依赖清单
  ├── README.md           # 项目介绍
  ├── devlog.md           # 本文件
  ├── app/
  │   └── __init__.py
  └── data/
      └── .gitkeep
  ```
- **待办**: 建 `app/backtest.py` (Option B 回测引擎), 装依赖, 跑首次回测

---

## Entry #3 · 2026-07-04 · 装依赖 + 产品命名

- **动作**:
  1. `pip install -r requirements.txt` 装完全部依赖
  2. 产品命名讨论: 从"小钱 / Piggy / Chang / 阿钱"多个候选中选定
- **原因**:
  - 依赖: 后续所有代码都要跑起来
  - 命名: "小钱"卡死用户天花板 (小白长大后觉得幼稚); "Piggy" 在理财赛道已被 Piggyvest 等占据; 需要一个"能陪用户长大"的名字
- **产出**:
  - ✅ 装好: yfinance 1.5.1 / pandas 3.0.3 / numpy 2.4.6 / scipy 1.17.1 / openai 2.44.0 / streamlit 1.58.0 / plotly 6.8.0 / feedparser / pydantic
  - ⚠️ 小坑: `requirements.txt` 里有中文注释导致 Windows pip 用 GBK 解码失败, 已改成纯 ASCII 注释
  - ✅ 产品名定为「**长 (Chang)**」
    - 一个字, 力量足, 好记
    - 无天花板: 5000 块要"长", 500 万也要"长"
    - 和 Tab ③【钱袋子】的"看钱怎么长大"叙事完美咬合
    - 图标意象: 🌱 → 🌳
    - 副标语: "让钱，长起来"
- **待办**: 写回测引擎 (`app/backtest.py`, Option B)

---

## Entry #5 · 2026-07-04 · 首次回测跑通 (踩坑记录)

- **动作**: 跑 `python app/backtest.py` 首次完整回测
- **踩坑过程**:
  1. ❌ yfinance 直接被限流 (`YFRateLimitError: Too Many Requests`) — Entry #0 风险清单已预警
  2. ❌ 加了 Stooq fallback, 但 Stooq 现在上了 JS 反爬 (返回 JS challenge 页面)
  3. ✅ 换用 akshare (国内量化圈主力数据源, 无 key, 无 rate limit), 一次跑通
- **fallback 链最终形态**: `yfinance -> akshare` (Stooq 弃用)
- **首次回测结果** (40% SPY / 30% GLD / 30% AGG, 2015 至今):
  ```
  Final value:      $32,417.96  (from $10,000)
  Total return:     +224.18%
  Annual return:    +11.39%
  Annual vol:       10.27%
  Sharpe:           1.11
  Sortino:          1.39
  Max drawdown:     -19.15%     (2020-02-21 -> 2020-03-20, 74 days to recover)
  Win rate:         55.59%
  Rebalance trades: 140
  ```
- **压力测试**:
  | 情景 | Total Return | Max DD | Sharpe |
  | --- | --- | --- | --- |
  | 2008 crisis | -13.56% | -36.05% | -0.24 |
  | 2020 COVID  | +4.24%  | -19.15% | 0.55  |
  | 2022 hike   | -11.84% | -18.30% | -0.82 |
- **关键学习**: 24h 内不要依赖境外数据 API 的稳定性, akshare 是国内团队做的免费轮子, Hackathon 首选
- **待办**: git 首次 commit + push 到远程

---

## Entry #6 · 2026-07-04 · v2 大改：品牌 / UI / 开跑闭环

### 用户反馈（v1 复盘）

用户在 v1 上线后拉了三个致命问题：

1. **"太长了，不是移动端"** —— Streamlit 硬拉着做手机 App 会踩一堆坑（顶部 Tab、盒子居中冒充手机、F12 手机视图跑歪）。
2. **"4 个 Tab 之间没关联"** —— 每个 Tab 是孤岛：Wallet 硬编码 1 万，用户在 Profile 填 5000 也不联动；Feed 说"跟你相关"却没关联组合；点【问 AI】按钮什么都不做。
3. **"策略只是数字，没跑起来"** —— 用户看不到"跑"的过程，Wallet 是静态摆样子，没有"用户按下开跑 → 系统真的开始跑"这个动作。

创始人红线复述（用户抓得比我准）：
- 会聊天的 ≠ Agent
- 只会总结研报的 ≠ Agent
- 漂亮 Demo ≠ Agent
- **要闭环**：想法 → 策略 → 执行 → 风控 → 反馈

### 调研结论（研究了 Wealthfront / Betterment / RockFlow / TradingAgents 等）

**关键洞察 1**：真正的策略型 App 都是**两层架构**——
- LLM 层只做「意图理解 + 结果解释」
- 策略/回测/执行/风控**全部是 deterministic Python 代码**

LLM 直接算持仓比例、直接下单 = 现场跑测必炸。

**关键洞察 2**：Hackathon 是**周末**，美股 / A 股 / 港股全部闭市。
如果只做股票 Paper trading，评委来展位时 NAV 曲线是**死的一条线**（tick 冻结）。
**解法**：股票为主 + 加密仓辅（Binance Testnet 7×24 波动），现场曲线在跳。

**关键洞察 3**：Streamlit 天生做单页数据看板，**不是移动 App 框架**。
NiceGUI（Quasar 底层）原生支持底部 Tab + 移动端渲染，Python 单文件写。

### v2 决策（用户确认 AAB）

| 项 | v1 | v2 |
|---|---|---|
| **品牌** | 长 (Chang) | **阿钱 (A-Qian)** — 拟人朋友感更强 |
| **UI 框架** | Streamlit（顶部 Tab、桌面味重） | **NiceGUI**（底部 Tab、真移动端） |
| **执行层** | 无（只有回测） | **自研 Paper Engine（股票）+ Binance Testnet（加密）** |
| **状态管理** | 各 Tab 各自 session_state（不联动） | **中央 UserState + SQLite 持久化**（关掉重开状态还在） |
| **AI 回复** | 一段人话 | **四段式**：结论 / 依据 / 画像 / 反问 |
| **长记忆** | 无 | 本地 JSON 存对话摘要 + 提取的偏好 |

### v2 5 分钟 Demo 剧本

```
0:00-0:30  冷启动 → 输入"3 万想跑赢通胀"
0:30-1:30  Agent 出方案卡片（组合 + 风控参数）→ 一键"看回测"
1:30-2:30  回测跑通 → Sharpe/回撤/NAV 曲线三张图
2:30-3:30  一键【开跑】→ Paper Engine + Binance Testnet 双引擎启动
3:30-4:30  现场触发极端场景 (BTC 瞬跌 20%) → 风控拦截 → Agent 反思
4:30-5:00  复盘卡片："上次错在哪，下轮我准备..."
```

### 保留 vs 丢弃

**保留（v1 承重墙）**：
- ✅ `app/backtest.py` — 回测引擎（Option B），已跑通 SPY/GLD/AGG
- ✅ `app/llm.py` — LLM 抽象层，智谱 GLM-4-Flash 已验证
- ✅ `.env` / `.gitignore` / 数据缓存

**丢弃（Streamlit 桌面思路）**：
- ❌ `app/ui.py` (Streamlit 版) — 大部分重写；保留在 git 里作为回滚点

**新建**：
- ➕ `app/state.py` — 中央 UserState + SQLite 持久化
- ➕ `app/memory.py` — 长记忆（对话摘要 + 用户偏好提取）
- ➕ `app/paper.py` — Paper Trading Engine（股票 + 加密）
- ➕ `app/strategy.py` — 策略 DSL + 内置策略库
- ➕ `app/main.py` — NiceGUI 主入口（底部 4 Tab）
- ➕ `app/tabs/` — 每个 Tab 一个模块

### 依赖新增

- `nicegui>=3.14.0` — 移动端 UI 框架
- `python-binance>=1.0.37` — Binance testnet 加密仓

### 待办 (按顺序做，每完成一个立刻 commit + push)

1. 项目改名"长" → "阿钱"，README 更新
2. 建 `app/state.py` (UserState + SQLite)
3. 建 `app/main.py` 骨架 (NiceGUI 底部 4 Tab)
4. Chat Tab 接入 LLM + 四段式 prompt + memory
5. Paper Engine + 开跑按钮 + Binance Testnet
6. Wallet Tab 双态 UI (未开跑 / 运行中)
7. Feed Tab 组合过滤 + 【问 AI】跳转
8. Profile Tab 联动共享状态
9. 5 分钟 Demo 剧本 + 3 个 profile 缓存

---

## Entry #7 · 2026-07-04 · 装依赖 + 停 v1

- **动作**:
  1. `pkill streamlit` (v1 已在 git, 可回滚)
  2. `pip install nicegui python-binance`
- **产出**:
  - ✅ NiceGUI 3.14.0
  - ✅ python-binance 1.0.37
  - ✅ FastAPI 0.139.0 (NiceGUI 内嵌)
  - ✅ python-socketio 5.16.3 (NiceGUI 用来做实时刷新)
- **`requirements.txt` 更新**: 新增 nicegui + python-binance, streamlit 保留为 fallback

---

## Entry #4 · 2026-07-04 · 回测引擎 (Option B)

- **动作**: 创建 `app/backtest.py`
- **原因**: 回测引擎是整个项目的承重墙, 后续 Agent 的每次建议都要调用它
- **实现**:
  - `BacktestConfig`: 组合配置 (tickers/weights/日期/再平衡/止损/波动率目标)
  - `load_prices()`: yfinance 拉取, forward-fill 缺失日
  - `run_backtest()`: 主循环, 日频, 处理权重漂移 + 再平衡 + 止损
  - `compute_metrics()`: 年化收益/波动率/Sharpe/Sortino/MaxDD/回本天数/胜率
  - `stress_test()`: 3 段极端情景 (2008 金融危机 / 2020 疫情 / 2022 加息)
  - `BacktestResult.summary()`: JSON 化输出, 给 LLM tool 用
- **关键规则**:
  1. 前视偏差防护: 第 t 天决策只用 t-1 及之前的数据 (portfolio return 用昨日权重 · 今日收益)
  2. 再平衡触发优先级: 止损 > 定期 (月/季) > 阈值偏离
  3. 止损后不再触发定期/阈值再平衡 (锁定在保守组合)
  4. 权重上下限在每次再平衡时应用, 之后重新归一化

---
