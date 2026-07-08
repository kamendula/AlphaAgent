<div align="center">

# 🔭 AlphaAgent

**资产无关(股 + 币)的多 Agent 选股/尽调框架 —— 带一个诚实的回测,和一个泄漏可控的 Agent 层。**

*可插拔池子源 → 便宜的量化过滤 → 多 Agent 尽调 → 纯规则进场时机。*

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-pre--alpha-orange.svg)]()

[English](README.md) · [贡献指南](CONTRIBUTING.md)

</div>

> 🚧 **Pre-alpha。** API 可能变动。文中内容不构成投资建议,见[免责声明](#-免责声明)。

---

## 为什么又造一个 trading-agent?

GitHub 上 LLM 交易 bot 一大把,但大多有同样两个盲区:**没法诚实回测**,以及 Agent **会偷看未来**(模型本就知道后来发生了什么;联网还会搜到基准日之后的新闻)。AlphaAgent 就是冲着解决这两点设计的。

**四件事,没有任何同类项目全做到:**

| | 含义 |
|---|---|
| 🧱 **机械/Agent 层分离** | 证明 edge 的回测只跑确定性规则,LLM 被 *bypass* —— Agent 幻觉污染不了你的收益曲线。 |
| 🔌 **协作可插拔** | `panel`(并行专家 + 裁判)、`debate`(多空辩论)、`vote`(投票),从配置切换多 Agent 拓扑,不用重写编排。 |
| 🪙 **资产无关** | 股和币走同一套符号路由 + Provider 注册表。加一个市场 = 丢一个 loader 文件。 |
| 🛡️ **PIT-Guard** | 点-in-time 中间件,拦截每次 Agent 工具调用,强制 `数据时间戳 ≤ 基准日`,并压制模型自身的参数记忆泄漏(匿名化 + 证据绑定 + 泄漏探针)。 |

---

## 怎么跑的

两道独立闸门 —— **AI 管定性判断,规则管进场时机** —— 绝不混在一起:

```
① 选股链:  可插拔池子源 → 量化过滤(便宜/可回测) → 多 Agent 协作(调工具) → Verdict
② 进场链:  Verdict 通过者 → 纯规则/技术信号 → buy / wait / pass + 触发价
横切底座:  DataProvider 注册表 · LLM 抽象 · PIT-Guard 中间件 · 可替换编排 adapter
回测:      只跑机械层(过滤+进场+离场,Agent bypass),复用 OSS 框架
```

*(架构图见 [英文 README](README.md) 的 mermaid 图。)*

---

## 快速上手

```bash
git clone https://github.com/kamendula/AlphaAgent.git && cd AlphaAgent
make demo        # 用内置离线快照跑通全链 —— 零 key、零网络、零安装
```

要实时数据 + 真模型?指定配置(在 `.env` 填 `FMP_API_KEY` / `OPENROUTER_API_KEY`):

```bash
python -m alphaagent screen --config configs/real.toml
python -m alphaagent backtest --symbol NVDA --config configs/demo.toml
```

> 多 Agent 面板**已在 demo 中可跑**(离线确定性 mock LLM,无需 key);把 `llm = "mock"` 换成 `"openrouter"`/`"openai"` 即用真模型。
> 配置用 TOML(Python 3.11+ 标准库直接解析,demo 无需 YAML 库)。

---

## 运行样例

一次真实运行(`configs/real.toml`:FMP 行情+财报+新闻,HY 模型走 OpenRouter,PIT-Guard 全开)。机械过滤先排序,只有头部候选进多 Agent 面板;进场时机是纯规则:

```text
 #  SYMBOL   TYPE    SCORE  FACTORS
 1  AAPL     equity  0.644  trend=0.82 momentum=0.91 not_overbought=0.20
 2  GOOGL    equity  0.594  trend=0.47 momentum=0.82 not_overbought=0.50
 ...

Agent 面板裁决
AAPL  -> BUY   (0.31)
  · fundamental 谨慎  净利率26.6%、营收+16.6%,但 EPS 未加速、PE 30.8 偏贵
  · technical   看多  站上50日线、动量+20.5%、RSI 61.8 不超买
  · sentiment   中性  科技大盘情绪偏正,无个股催化
  · risk        中性  ATR 2.8%、回撤-12.7%、未拥挤 —— clean
GOOGL -> AVOID (0.28)
  · fundamental 中性  营收+21.8%、净利率56.9%、PE 13.9 便宜,但 EPS 减速
  · technical   谨慎  跌破50日线;动量矛盾
  · risk        谨慎  回撤16.2% + 波动偏高

进场信号(纯规则,无 Agent)
  AAPL   WAIT  高于 EMA 4.6% —— 等回踩
  GOOGL  PASS  跌破 50 日线

🛡️  PIT-Guard:泄漏探针 0.00(clean);工具被 as-of 界住、证据绑定
```

离线 `make demo` 会即时产出同样结构(mock LLM + 内置快照),零配置即可复现。

---

## 护城河:PIT-Guard 🛡️

泄漏分两类,分别处置:

**① 工具/数据泄漏 —— 100% 可控。** 中间件卡在工具边界,保证 Agent 只看到时间戳 ≤ 基准日的数据:价格截断、新闻按日期过滤、财报用当时申报的 point-in-time 快照。

**② 参数记忆泄漏 —— 模型已知未来,删不掉,只能压制:**
- **匿名化**:抹掉代码/公司名,让它判断"这支具备这些特征的匿名标的",而不是"我认识的那个后来暴涨的 NVDA"。
- **证据绑定**:每条结论必须挂受控工具返回的 `evidence_ref`,凭空回忆判无效。
- **截止日后评估 + 泄漏探针**:历史评 Agent 只用训练截止日之后的日期,并量化残余污染。

关键:**头条回测里根本没有 Agent**,所以参数泄漏碰不到它。

---

## 扩展它(一个文件 + 一行)

每个扩展点都是注册表插件:`DataProvider` / `PoolSource` / `QuantFilter` / `Analyst` 角色 / `CollaborationPolicy` / `EntryRule`,都用 `@register` 一行注册。参考 [`examples/`](examples/) 和 [贡献指南](CONTRIBUTING.md)。

---

## 🗺️ 路线图

- [x] **M0** 核心注册表 + 数据模型 + yfinance provider + `make demo`
- [x] **M1** 选股链:池子 + 过滤 + `panel`/`vote`/`llm_judge` 协作 + 4 个 Analyst + 厂商无关 LLM(离线 mock)+ FMP 数据源
- [x] **M2** 进场规则(`breakout`/`pullback`)+ 回测 adapter(`simple` 纯标准库 + 可选 `backtesting.py`)+ 机械层报告 + `alphaagent backtest`
- [x] **M3** PIT-Guard:边界(`GuardedRouter`)+ 匿名化 + 证据绑定 + 泄漏探针
- [x] **M4** `debate` 策略 · 可选 MCP 薄外挂(`python -m alphaagent.mcp`)· prompt 外置(`agents/prompts/*.md`)· 每个扩展点的参考 example

---

## ⚠️ 免责声明

AlphaAgent 是**研究与教育**框架,**不下真实订单**,**不构成投资建议**。市场有风险,决策自负。

## 许可

MIT —— 见 [LICENSE](LICENSE)。
