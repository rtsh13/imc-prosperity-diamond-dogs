# IMC PROSPERITY 4: COMPLETE COMPETITIVE MASTERPLAN

**Team size:** 2
**Timeline:** Round 1 starts April 14, 2026
**Goal:** Top placement to fast-track IMC SDE applications
**Currency:** XIRECs (formerly SeaShells)

---

## TABLE OF CONTENTS

1. [Optiver Lessons: What We Learned the Hard Way](#1-optiver-lessons)
2. [What Is Prosperity and How It Differs from Optiver](#2-prosperity-vs-optiver)
3. [The Product Blueprint Across All Editions](#3-product-blueprint)
4. [Strategy Archetypes That Win](#4-strategy-archetypes)
5. [Work Split: Phase-Based Pairing](#5-work-split)
6. [Round-by-Round Tactical Guide](#6-round-by-round-guide)
7. [Common Pitfalls That Eliminate Teams](#7-pitfalls)
8. [Manual Trading Preparation](#8-manual-trading)
9. [The Meta-Game](#9-meta-game)

---

## 1. OPTIVER LESSONS: WHAT WE LEARNED THE HARD WAY <a name="1-optiver-lessons"></a>

### What Went Wrong (Ranked by Cost)

**We built infrastructure instead of making money.** 2,500 lines across 12 files of "enterprise-grade" architecture. The teams that won ran ~150 lines of focused, tuned code. We wrote docstrings while they watched PnL.

**The sentiment strategy was net-destructive.** TF-IDF logistic regression trained on 345 rows with 3-class bucketing. Crossed the spread on every trade via IOC orders. The spread cost exceeded the predicted signal magnitude (max ~3.3%, mean ~1.5%). Negative EV by construction.

**`_take_directional_position` was copy-pasted twice** in the same file. The second copy was dead code. Nobody reviewed. A single code review would have caught this and the inverted position-limit check in the arb strategy.

**We ignored the tools Optiver literally handed us.** The `Classifier Introduction.ipynb` walked through BART-large-MNLI zero-shot classification. We built a worse wheel with TF-IDF instead.

**The training data had continuous impact magnitudes we threw away.** Values like `-0.019004` got bucketed into {positive, negative, neutral}. The correct approach was regression, not classification.

**Black-Scholes code sat in the repo unused.** If options instruments existed, we left an entire asset class untouched.

**Team of 6 running waterfall.** Nobody was the "trader" watching PnL. Everyone was an "engineer."

### What Carries Over to Prosperity

| Optiver Asset | Prosperity Application | Modification Needed |
|---|---|---|
| Market maker core logic (mid price, retreat, credit, tick rounding) | Round 1 stable + volatile products | Remove all exchange wrapper code. Pure function: state -> orders |
| Arbitrage intuition (spread monitoring, z-scores) | Round 2 basket arbitrage | Trade the basket instrument directly. No leg risk in Prosperity |
| `common/black_scholes.py` (call/put pricing, delta, vega) | Round 3-4 options products | Add implied vol solver (Newton-Raphson). Replace scipy with pure Python |
| Risk manager's `check_can_trade()` concept | Position budget tracking | Pre-order validation gate, not post-hoc monitor |

### What We Must Unlearn

- **"Ship infrastructure first" instinct.** Prosperity needs one file, one class, ~300-600 lines total by Round 5. No orchestrators, no strategy patterns.
- **"Real-time" thinking.** No `time.sleep()`, no rate limiting, no connections. Pure function: TradingState -> Orders.
- **"Deploy and watch" mentality.** Prosperity is asynchronous. Submit code, wait for results, analyze, re-submit. The backtester is the most important tool.

---

## 2. PROSPERITY VS OPTIVER <a name="2-prosperity-vs-optiver"></a>

| Dimension | Optiver Optibook | IMC Prosperity |
|---|---|---|
| **Format** | 24-hour live hackathon | 5 rounds over 16 days (72h/72h/48h/48h/48h) |
| **Execution** | Real-time exchange, rate limits, connections | Asynchronous. Submit code, engine runs it offline |
| **Language** | Python (with Optibook SDK) | Python only. Single file, single `Trader` class |
| **Interaction** | Direct API calls: `exchange.insert_order()` | Return `list[Order]` from `run()` method. No API |
| **Competition** | Algo vs algo on shared exchange | Algo vs IMC bots. No head-to-head between players |
| **Products** | ~10 instruments (5 stocks + 5 duals) | 10-15 products by Round 5, across categories |
| **Speed** | Matters (25 req/sec limit) | Irrelevant. Fixed timesteps, full state snapshots |
| **Manual component** | None | Separate game-theory/probability challenges per round |
| **State** | Persistent (your bot runs continuously) | Ephemeral. Must serialize state as JSON string between timesteps |
| **Prize** | Hackathon prizes | $50,000 pool. $25K 1st, $10K 2nd, $5K 3rd |

**The key structural difference:** In Optiver, iteration speed was the bottleneck (how fast can you tune parameters while watching live PnL). In Prosperity, research depth is the bottleneck (how well do you understand each product's fair value and the correct strategy, given you can only submit and wait).

---

## 3. THE PRODUCT BLUEPRINT <a name="3-product-blueprint"></a>

Every edition has followed this pattern. Expect Prosperity 4 to do the same.

### Round 1: Market-Making Fundamentals

**Always includes:**
- A stable-price product pegged near 10,000 (PEARLS/AMETHYSTS/RAINFOREST_RESIN)
- A volatile trending product (BANANAS/STARFRUIT/KELP)
- P3 added a third extremely volatile product (SQUID_INK) with sharp spikes

**Strategy:** Hardcode fair value for stable product. EMA-based fair value for volatile products. Market make around fair value with position-aware retreat.

### Round 2: Multi-Product Relationships

**Always includes:**
- Correlated pairs (COCONUTS + PINA_COLADAS, >90% correlation)
- OR cross-exchange arbitrage (ORCHIDS with shipping costs/tariffs)
- OR basket/ETF products (PICNIC_BASKET = weighted sum of components)

**Strategy:** Z-score on spread between related instruments. Trade the basket directly, not the components.

### Round 3: Complexity Escalation

**Has included:**
- Options chains (VOLCANIC_ROCK underlying + 5 call-option vouchers)
- Seasonal patterns (BERRIES with intraday cycles)
- Signal-driven trading (DIVING_GEAR driven by DOLPHIN_SIGHTINGS)

**Strategy:** Black-Scholes pricing + IV mean-reversion for options. Pattern detection for seasonal products.

### Round 4: Cross-Exchange or Advanced Mechanics

**Has included:**
- European call options (COCONUT_COUPON, strike 10,000, 250-day expiry)
- Location arbitrage with tariffs (MAGNIFICENT_MACARONS)

**Strategy:** Same B-S framework for options. Transport cost modeling for location arb.

### Round 5: Bot Identity Reveal

No new products. De-anonymized trader IDs on market trades. Identify profitable bots and copy-trade them.

**Strategy:** Track each bot's buy/sell behavior. Copy-trade bots with positive expected returns (confirmed: "Olivia" in P3 bought at daily lows, sold at daily highs).

### Historical Products Table

| Edition | R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|---|
| P1 (2023) | Pearls, Bananas | +Coconuts, Pina Coladas | +Berries, Diving Gear | +Picnic Basket, Ukulele, Dip, Baguette | Bot IDs |
| P2 (2024) | Amethysts, Starfruit | +Orchids | +Gift Basket, Chocolate, Strawberries, Roses | +Coconut, Coconut Coupon | Bot IDs |
| P3 (2025) | Rainforest Resin, Kelp, Squid Ink | +2 Picnic Baskets, Croissants, Jams, Djembes | +Volcanic Rock, 5 Vouchers | +Magnificent Macarons | Bot IDs |

---

## 4. STRATEGY ARCHETYPES THAT WIN <a name="4-strategy-archetypes"></a>

### 4.1 Market Making on Stable Products (the bedrock)

Every top team builds this first. Place bids below fair value and asks above fair value. Earn the spread on every round-trip.

**Critical insight (Frankfurt Hedgehogs, 2nd globally P3):** Use the "wall mid" (average of the deepest-liquidity bid and ask levels) rather than raw mid-price. This approximates IMC's hidden fair value used for PnL calculation. See CODE_TEMPLATES.md for implementation.

**When to use wall-mid vs other fair value methods:**
- Stable product (pegged ~10,000): hardcode the known value. Don't compute.
- Volatile product with mean-reversion: EMA of mid prices
- Products where your PnL seems wrong despite correct trades: switch to wall-mid
- Baskets: synthetic price from components
- Options: Black-Scholes theoretical value

**Position management (Linear Utility, 2nd globally P2):** Executing zero-EV trades solely to reset position toward zero added ~3% to total PnL by freeing capacity for profitable trades.

### 4.2 ETF/Basket Arbitrage (highest PnL)

Track synthetic basket price from components. Compute z-score on spread. Trade ONLY the basket (not individual components) when spread deviates beyond threshold.

Typical thresholds: entry at +/- 1.5 to 2.0 standard deviations.

**P3 innovation (CMU Physics, 7th globally):** With two baskets sharing components (PICNIC_BASKET1 and PICNIC_BASKET2), trade the difference in premiums between baskets. Achieved 100% position-limit utilization.

### 4.3 Options Pricing via Black-Scholes

1. Each timestep, compute implied volatility (IV) from market mid-price using Newton-Raphson
2. Track IV in traderData. Compute rolling mean IV (window ~50 ticks)
3. If current IV > mean IV + threshold: option expensive, SELL
4. If current IV < mean IV - threshold: option cheap, BUY
5. Delta-hedge by trading the underlying in the opposite direction

**The P3 lesson (CMU Physics):** A simple rolling IV average outperformed their quadratic volatility-smile model by 2.5x on submission day. The smile fit broke on out-of-sample data. **Robust simplicity beats fragile sophistication.**

### 4.4 Cross-Exchange Arbitrage

Products tradable on two exchanges with transport costs and tariffs. Model the total cost of moving inventory, and trade when the price differential exceeds that cost.

**P3 discovery (Frankfurt Hedgehogs):** Volume-imbalance signal. When local best-bid volume exceeds a threshold (e.g., 9), sell orders at best ask are essentially guaranteed to fill.

### 4.5 Bot Copy-Trading (Round 5 only)

When bot IDs are revealed:
1. Track each bot's trades (who buys/sells, at what prices)
2. Compute each bot's average buy price vs. average sell price
3. A bot with avg_sell > avg_buy is consistently profitable
4. Copy-trade: when the profitable bot buys, you buy at the same price

Direct copy-trading outperformed using bot behavior as a regime indicator (Alpha Animals, 9th globally P3).

### 4.6 Historical Data Reuse Detection

In P2, coconut prices matched P1 data with R-squared ~ 0.99. Cross-correlate each new round's price series against all publicly available prior-year data. IMC has progressively closed this exploit but checking costs nothing.

---

## 5. WORK SPLIT: PHASE-BASED PAIRING <a name="5-work-split"></a>

### Context

- Same timezone, co-located (can meet in person)
- Person A (you): stronger Python, HFT/LOB background, more domain knowledge
- Person B (teammate): capable but less Python experience, less domain knowledge
- Communication: MS Teams + shared Git repo

### Model: Phase-Based with Round-by-Round Rotation

NOT pure specialization (our Optiver mistake). NOT rotating every 4-5 hours (too much context-switching overhead, 15-25% time lost on ramp-up). Instead: clear roles per phase within each round, with primary coder rotating across rounds.

### Within Each Round: Three Phases

**Phase 1: Discovery (first 4-6 hours)**

| Person A (you) | Person B |
|---|---|
| Read spec, check position limits, data formats | Run analysis notebook (correlations, distributions) |
| Ensure existing strategies still work on prior products | Check for data reuse against P1/P2/P3 datasets |
| Identify fair value estimation approach | Identify product category (stable/volatile/basket/options) |

After 2-3 hours: sync. Agree on strategy for each new product. Produce a 1-line spec per product: "Product X: use strategy Y with parameters Z."

**Phase 2: Implementation (next 6-10 hours)**

ONE person codes the algo file. The other works on:
- Manual challenge
- Building backtest analysis to validate parameters
- Preparing parameter sweep experiments

Safety submission within 4 hours of Phase 2 start. Then the other person reviews the full code.

**Phase 3: Optimization (final 4-8 hours)**

| Person A | Person B |
|---|---|
| Run parameter sweeps on backtester | Review results, check for overfitting |
| Test edge cases (extreme positions, empty order books) | Verify manual challenge submission |
| Prepare final submission | Cross-check: "does this edge have a reason to exist?" |

Final submission 2+ hours before deadline. Never submit at the last minute.

### Coder Rotation Across Rounds

Given the skill gap: Person A (you) should be primary coder for the harder rounds, Person B for the more straightforward ones.

| Round | Primary Coder | Rationale |
|---|---|---|
| Round 1 | Person A | Foundation code, state serialization framework. Sets the patterns. |
| Round 2 | Person B | Pairs/basket arb is conceptually simple. Good learning round. Person A reviews. |
| Round 3 | Person A | Options/complex products. Needs HFT/quant domain knowledge. |
| Round 4 | Person B | Cross-exchange arb is pattern-matching. Person A reviews for edge cases. |
| Round 5 | Person A | Bot identification is a data/coding task. Needs clean implementation. |

### Non-Negotiable Rules

1. **NEVER submit code only one person has seen.** Even a 20-minute review catches critical bugs. Our Optiver duplicated-function disaster proves this.
2. **One person owns the file at a time.** No simultaneous edits. Git helps, but a single-file codebase makes merge conflicts painful.
3. **Disagreements: defer to the backtest.** If Person A wants z-threshold 1.5 and Person B wants 2.0, test both. The one with higher backtest PnL wins. No debates.
4. **During the 4-day intermission (between R2 and R3):** BOTH people deep-review ALL code together. This is the full-context sync point. Refactor if needed.

---

## 6. ROUND-BY-ROUND TACTICAL GUIDE <a name="6-round-by-round-guide"></a>

**NOTE:** Round 1 start (April 14) is confirmed. Subsequent round dates below are interpolated from P3's schedule. Verify the actual P4 schedule at https://prosperity.imc.com/ once published.

### Round 1 (April 14, 72 hours)

**Expected products:** 1 stable (~10,000), 1-2 volatile

**Hour 0-1:** Both read the spec. Person A checks data format, position limits, order conventions (verify: are sell_orders volumes negative or positive?). Person B loads data, plots price distributions.

**Hour 1-3:** Person B checks for data reuse against prior-year datasets. Person A implements stable market maker using pre-built template.

**Hour 3-4:** First safety submission (just the stable product market maker). Even if it earns 10K XIRECs, you're ahead of 60% of teams.

**Hour 4-8:** Person A adds volatile product strategy (EMA-based fair value). Person B validates EMA window size via backtest parameter sweep.

**Hour 8-10:** Person B reviews full code. Focus on: position limit handling, state serialization, sign conventions.

**Hour 10-12:** Parameter tuning. Submit optimized version.

**Remaining time:** Manual challenge. Further optimization if time permits.

**Minimum viable product:** Market maker that correctly handles the stable product. ~100 lines. Positive PnL on first submission.

### Round 2 (April 17, 72 hours)

**Expected products:** Pairs, baskets, or cross-exchange arb

**Priority:** Identify the relationship between new products. Compute synthetic basket price if applicable. Implement z-score spread trading.

**Critical:** Ensure Round 1 strategies still work. Test full file before submitting.

### Round 3 (April 24, 48 hours)

**Expected products:** Options chain or complex derivatives

**Priority:** If options, deploy pre-built Black-Scholes + IV solver. If seasonal, analyze intraday patterns.

**Warning:** This is where verbose logging crashes Lambda. Strip all unnecessary print statements before submitting.

### Round 4 (April 26, 48 hours)

**Expected products:** Cross-exchange mechanics or additional derivatives

**Priority:** Model transport costs / tariffs if cross-exchange. Apply IV mean-reversion if more options.

### Round 5 (April 28, 48 hours)

**Expected:** Bot identities revealed. No new products.

**Priority:** Deploy bot tracking code. Identify profitable bots within first few simulation hours. Copy-trade.

**Do NOT:** Rip out working strategies to make room for bot trading. Add bot trading ON TOP of everything else.

---

## 7. COMMON PITFALLS THAT ELIMINATE TEAMS <a name="7-pitfalls"></a>

1. **Position limit violations cancel ALL orders for that product.** Not just the excess. Design around limits, don't bolt them on.

2. **Overfitting to backtest data.** Multiple teams report 3-4x drops between backtest and live PnL (e.g., ~35K backtest to ~9K live). If you can't explain WHY an edge exists, discard it.

3. **The hidden fair value.** IMC calculates PnL using a hidden fair value, not mid-price. Wall-mid approximation is the best known proxy for stable products.

4. **Verbose logging causes Lambda crashes** in later rounds with 15 products. Strip print statements.

5. **Spending time on unprofitable products.** Squid Ink (P3) was "pure chaos" per the 7th-place team. If a product's price action is random noise, move on. Optimize proven strategies instead.

6. **Ignoring manual trading.** Separate $5,000 Best Manual Trader prize. And manual PnL counts toward overall ranking.

7. **Discord psychological warfare.** People post inflated backtest screenshots. Ignore. Stick to your own validation.

---

## 8. MANUAL TRADING PREPARATION <a name="8-manual-trading"></a>

Manual challenges are submitted separately from algorithmic code. Formats that have recurred:

- **FX triangular arbitrage:** Given exchange rates between N currencies, find the most profitable conversion cycle. Solvable via Bellman-Ford on negative-log-transformed rates.
- **Nash equilibrium / game theory:** Choose a strategy where payoff depends on other players' choices. Compute expected value under assumed opponent distributions.
- **Reserve price optimization:** Set a price that maximizes expected profit given a distribution of buyer valuations.
- **Probability puzzles / treasure maps:** Expected value calculations.

Pre-code the FX arbitrage solver (see CODE_TEMPLATES.md). Review prior-year manual problems from GitHub repos.

---

## 9. THE META-GAME <a name="9-meta-game"></a>

### What Other Teams Will Do

- ~60% will spend Round 1 figuring out how to submit code. Score near zero.
- ~25% will implement a basic market maker with wrong position handling or raw mid-price. Some money, 3-5x left on table.
- ~10% will implement correct market making with proper position management.
- ~5% will have pre-built templates, local backtesting, and prior-year data for cross-correlation.
- ~1% will also exploit data reuse, use wall-mid, and have options infrastructure ready.

**Your biggest alpha is not better strategies. It's having strategies READY FASTER.** Pre-building templates converts each round from a "build" problem into a "tune" problem.

### For IMC Applications

The competition itself is a filter. Top finishers get fast-tracked into interviews. But even a top-10% finish demonstrates:
- Algorithmic thinking under time pressure
- Understanding of market microstructure (order books, position management, fair value estimation)
- Quantitative reasoning (options pricing, statistical arbitrage)
- Python implementation ability

Both team members should be able to explain every strategy decision in an interview. This is why both people need to review all code (even if only one writes it per round).
