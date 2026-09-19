# Football Alpha v0.4 — 简单数学公式与全部因子

**状态：代码已实现 market-anchored residual pricing；因子系数未拟合，不得把本文件当成已验证的盈利模型。** 500 场旧版 Poisson 1X2 回测：383 笔、P&L -$7,810、ROI -20.39%；这是旧版 baseline，不是 v0.4 的收益。历史没有 PIT 阵容/xG/战术快照的因子不能用赛后信息补填。

## 1. Market prior / 市场基准

同一个互斥市场（如主胜/平/客胜）有赔率 `O_1,O_X,O_2`：

`q_i = 1/O_i`

`p_market,i = q_i / (q_1 + q_X + q_2)`

二元市场：`p_market,yes = (1/O_yes) / (1/O_yes + 1/O_no)`。

**不同盘口不可混合 de-vig。** Kalshi/Polymarket 可执行 ask 用于入场成本，不等于 sportsbook fair prior；记录平台、盘口定义、时间戳、费用和流动性。

## 2. Football residual / 市场没反映的足球信息

所有特征 `z_j = (x_j - training_mean_j) / training_std_j`；均值/标准差只在过去训练集拟合，输入按 PIT 冻结，`z_j` 截断至 [-2,2]。

`R = Σ_j clip(w_j × z_j, -cap_j, cap_j)`

`p_raw = sigmoid(logit(p_market) + R)`

`logit(p) = ln[p/(1-p)]`；`sigmoid(x) = 1/(1+exp(-x))`。

`p_calibrated = sigmoid(a + b × logit(p_raw))`，a/b 必须只用过去训练期拟合，再在未来 holdout 测试。当前 w/a/b **没有完成训练**，不会假装得出 production fair。

### 因子（z 是相对市场预期/同级对手的标准化差值，不是原始比分）

| Factor | 简单量化 / z | 单项 log-odds 上限（研究用，不是训练权重） |
|---|---|---:|
| Attack xG | 近期 xG for / 90，按对手防守强度调整 | .12 |
| Defense xGA | 对手 xGA / 90；防守越差越利于我方进球 | .12 |
| Shot volume | shots / 90、box shots | .06 |
| xG per shot | xG / shots；区分低射门量和高机会质量 | .06 |
| Finishing regression | goals − xG 的回归，避免把运气当稳定实力 | .035 |
| Opponent-adjusted form | 指数衰减近况减对手基准；half-life 候选 30/60/90/120 天 | .05 |
| Home / away | 主客场强度差；不能双算市场已知主场优势 | .05 |
| Coach tactical matchup | 教练体系对位：低位/高压/边路/中路/定位球 | .07 |
| Pressing/build-up | PPDA、逼抢成功、后场失误风险 | .05 |
| Transition | 反击 xG、失误后 xGA、速度对位 | .06 |
| Set piece | 定位球 xG for/against | .04 |
| Game-state asymmetry | 强队先得分后的总进球尾部；弱队领先后的节奏变化 | .05 |
| Lineup | 首发分钟/球员贡献相对常规 XI；记录发布时间 | .09 |
| Injuries/suspensions | 缺阵的边际 xG/xGA 贡献，不是简单人数 | .08 |
| Squad depth | 替补阵容相对对手的实力 | .06 |
| Tier gap | 联赛层级差/跨联赛强度映射，杯赛尤重要 | .07 |
| Rotation × depth | rotation penalty × (1−depth resilience)；曼城替补对低级别球队不能机械降级 | .06 |
| Rest/fatigue | 休息天数、密集赛程、出场负荷 | .04 |
| Travel | 旅途距离/跨时区/客场恢复 | .025 |
| Motivation | 争冠/保级/杯赛目标，仅可核实信息 | .035 |
| Weather | 风、雨、温度对射门/节奏影响 | .02 |
| Human disagreement | 用户赛前明确记录的战术直觉，与模型不同才作为待检验特征 | .025 |
| Market sentiment | 可验证情绪/新闻冲击，防止把价格跌当价值 | .035 |
| Market movement | 开盘→T-24H→T-1H→close 的 PIT 变化；只用决策前数据 | .035 |

**注意**：市场价格差不是 football factor。市场 prior 和 market movement 可能相关，训练时需正则化与 ablation 防止双算。每个因子先检验增量 holdout log loss、Brier、CLV 和 net ROI；未测得增益的权重保持 0。市场先验与 Poisson goal model 的独立估值可以保留作 disagreement diagnostic，但不能直接用最大 disagreement 自动买入。

## 3. Goal distribution / 总进球、让球和比分

`λ_home = λ_home,base × exp(Σ_k β_hk z_k)`

`λ_away = λ_away,base × exp(Σ_k β_ak z_k)`

`P(H=h,A=a) = Pois(h;λ_home) × Pois(a;λ_away)`（初版独立 Poisson；高相关/红牌/比赛状态可升级 Dixon–Coles、bivariate Poisson、state-transition）。

`P(Over 2.5) = 1 − Σ_(h+a≤2) P(h,a)`

`P(Home win) = Σ_(h>a) P(h,a)`

`P(BTTS) = 1 − P(H=0) − P(A=0) + P(H=0,A=0)`

不能因为双方近期进球少就直接推 Under：要分开估计创造机会不足、finishing variance、transition vulnerability、压迫失误与比分不对称（3–0 也可能打穿 Under）。

## 4. Trading / 价格、风险与 Paper

`break_even = 1 / executable_decimal_odds`

`p_lower = max(0, p_calibrated − model_uncertainty_pp)`

`EV_net = p_lower × executable_decimal_odds − 1 − fee_per_stake − slippage_per_stake`

`fair_odds = 1 / p_calibrated`

只有**独立 PIT 数据 + 已训练/校准 residual + 同市场实时可执行报价 + EV_net ≥ 5% + 敞口/流动性/相关性限制**，才自动生成 paper signal；无需 watch-only 人工等待，但不得把未定价的研究观点当成交。A ≤0.75u，B ≤0.5u，C ≤0.25u，单场合计 ≤1u。B 两腿组合须计算联合概率，不能在相关时简单相乘。

`paper_PnL(win) = stake × (odds−1) − fees`

`paper_PnL(loss) = −stake − fees`

`NAV = initial_capital + Σ settled_paper_PnL`（未结算仓位另计敞口）。

2026-09-19 三笔旧研究模拟按用户指令纳入 paper NAV，标记 `legacy research simulation`；它们**不是**独立验证的 executable fills。500 场历史回测不计入当前 live paper NAV，避免双算。

## 5. 验证路线 / 防止再出现“高 EV 反而亏”

1. 先用 market de-vig baseline 做 log loss / Brier / calibration。
2. 训练 residual 模型：带 L2 的 logistic / multinomial logistic，按联赛和盘口做 hierarchical shrinkage；训练集拟合所有标准化参数。
3. chronological walk-forward，冻结每场 kickoff 前最后可用的 PIT 特征；holdout 300–500 场以上。
4. 对每项因子做 ablation：`Δlog_loss_j = loss(without j) − loss(with j)`；同时观察净 ROI/CLV，不能只看单个胜场。
5. 对赔率分桶（<2、2–3、3–5、≥5）、主客/让球/大小球、联赛、EV bucket 分层；检查 estimated EV 是否随 realized ROI 单调上升。
6. 记录每笔模型版本、数据时间、盘口、赔率、fee/slippage、赛前用户直觉及是否改变决策；绝不使用赛后阵容/结果补训练旧预测。

**实施边界**：`src/residual_pricing.py` 已可计算 de-vig、residual log-odds、factor contribution 和 conservative EV；`src/data_engine.py` 只有校准权重存在时才允许此版本产生 paper-entry candidate。下一阶段需要真实 PIT xG、阵容、战术、盘口数据和 residual 训练集；不能凭今天三场赢球倒推出因子系数。
