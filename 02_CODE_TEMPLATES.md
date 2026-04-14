# CODE TEMPLATES: PRE-BUILT STRATEGIES FOR PROSPERITY 4

All code uses **zero external dependencies** beyond what Prosperity guarantees (Python stdlib + likely numpy).
scipy is NOT guaranteed in the sandbox. All math is pure Python.

**IMPORTANT:** Verify the following before using any template in P4:
- Are `order_depth.sell_orders[price]` values negative or positive? (P2/P3: negative)
- What are the exact position limits per product? (Given in each round's spec)
- What is the exact `TradingState` interface? (`pip install prosperity4btx` to inspect)

---

## TABLE OF CONTENTS

1. [Trader Class Skeleton](#1-skeleton)
2. [Pure Python Math Utilities](#2-math)
3. [State Serialization Framework](#3-state)
4. [Position Budget Tracker](#4-position)
5. [Stable Product Market Maker](#5-stable-mm)
6. [Volatile Product Market Maker (EMA)](#6-volatile-mm)
7. [Wall-Mid Calculator](#7-wall-mid)
8. [Z-Score Basket Arbitrage](#8-basket-arb)
9. [Black-Scholes + Implied Vol Solver](#9-options)
10. [Bot Tracker (Round 5)](#10-bot-tracker)
11. [Data Reuse Detection](#11-data-reuse)
12. [FX Arbitrage Solver (Manual Challenge)](#12-fx-arb)
13. [New Round Analysis Notebook](#13-analysis)

---

## 1. Trader Class Skeleton <a name="1-skeleton"></a>

```python
import json
import math
from datamodel import OrderDepth, TradingState, Order

class Trader:
    
    # FILL THESE PER ROUND (from the spec)
    LIMITS = {
        # "PRODUCT_NAME": position_limit,
    }

    def run(self, state: TradingState):
        result = {}
        conversions = 0
        
        # Deserialize persistent state
        data = json.loads(state.traderData) if state.traderData else {}
        
        # Route each product to its strategy
        for product in state.order_depths:
            if product in self.LIMITS:
                # Dispatch to appropriate strategy
                # Add cases per round as products are introduced
                pass
        
        # Example dispatching (uncomment/modify per round):
        # if "STABLE_PRODUCT" in state.order_depths:
        #     result["STABLE_PRODUCT"] = self.strategy_stable("STABLE_PRODUCT", state, data)
        # if "VOLATILE_PRODUCT" in state.order_depths:
        #     result["VOLATILE_PRODUCT"] = self.strategy_ema("VOLATILE_PRODUCT", state, data)
        
        traderData = json.dumps(data)
        return result, conversions, traderData
```

---

## 2. Pure Python Math Utilities <a name="2-math"></a>

**Do NOT use scipy.** These replace `scipy.stats.norm.cdf` and `norm.pdf`.

```python
import math

def norm_cdf(x):
    """
    Cumulative distribution function for standard normal.
    Abramowitz & Stegun approximation. Max error ~1.5e-7.
    """
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911
    sign = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return 0.5 * (1.0 + sign * y)

def norm_pdf(x):
    """Probability density function for standard normal."""
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)
```

---

## 3. State Serialization Framework <a name="3-state"></a>

```python
def init_product_data(data, product, defaults=None):
    """
    Initialize data for a product if not already present.
    Call at the start of each strategy function.
    
    Usage:
        init_product_data(data, "KELP", {"ema": None, "prices": []})
    """
    if product not in data:
        data[product] = defaults or {}

def append_capped(lst, value, max_len=100):
    """Append to a list, keeping only the last max_len elements."""
    lst.append(value)
    if len(lst) > max_len:
        del lst[:-max_len]  # more efficient than slicing for large lists
```

**Design rules for traderData:**
- Store only what you cannot recompute (running averages, not raw histories where possible)
- Use `round(value, 2)` before storing floats
- Cap all lists with `append_capped`
- Key everything by product name so adding Round N products never breaks Round N-1 data
- Test serialization size with 15 products, 200 ticks each, before the competition

---

## 4. Position Budget Tracker <a name="4-position"></a>

**This is the most important utility in the entire codebase.** Getting this wrong means either:
- Violating position limits (all orders cancelled for that product), or
- Under-utilizing your capacity (leaving money on the table)

```python
def compute_orders_with_budget(
    product: str,
    order_depth: OrderDepth, 
    fair_value: float,
    position: int,
    limit: int,
    spread: float = 2.0,     # how many ticks wide to quote
    retreat: float = 0.005,   # price retreat per lot of position
):
    """
    Place orders respecting position limits.
    
    Order of operations:
    1. Take any mispriced resting orders (cross the spread when profitable)
    2. Place passive quotes with remaining capacity
    
    This ordering is critical: eating mispriced orders first captures
    guaranteed profit before committing capacity to passive quotes.
    
    NOTE on sell_orders sign convention:
    In P2/P3, sell_orders volumes were NEGATIVE.
    VERIFY THIS FOR P4 by printing order_depth in your first test submission.
    If P4 sell_orders are positive, remove the negation on the qty line below.
    """
    orders = []
    buy_budget = limit - position     # how much more we can buy
    sell_budget = limit + position    # how much more we can sell
    
    # Theoretical price adjusted for inventory
    theo = fair_value - retreat * position
    
    # --- PHASE 1: Take profitable resting orders ---
    
    # Buy from any ask priced below our theoretical value
    if order_depth.sell_orders:
        for price in sorted(order_depth.sell_orders.keys()):
            if price < theo and buy_budget > 0:
                # sell_orders volumes are NEGATIVE in P2/P3. Verify for P4.
                available = -order_depth.sell_orders[price]  # REMOVE NEGATION IF P4 VOLUMES ARE POSITIVE
                qty = min(available, buy_budget)
                if qty > 0:
                    orders.append(Order(product, price, qty))
                    buy_budget -= qty
    
    # Sell into any bid priced above our theoretical value
    if order_depth.buy_orders:
        for price in sorted(order_depth.buy_orders.keys(), reverse=True):
            if price > theo and sell_budget > 0:
                available = order_depth.buy_orders[price]  # buy_orders are positive
                qty = min(available, sell_budget)
                if qty > 0:
                    orders.append(Order(product, price, -qty))
                    sell_budget -= qty
    
    # --- PHASE 2: Place passive quotes with remaining capacity ---
    
    # Round to tick size. REPLACE 1 WITH ACTUAL TICK SIZE FROM SPEC.
    # Example: if tick_size = 0.1, use math.floor(x / 0.1) * 0.1
    tick = 1  # PLACEHOLDER - set from instrument spec
    bid_price = math.floor((theo - spread) / tick) * tick
    ask_price = math.ceil((theo + spread) / tick) * tick
    
    if buy_budget > 0:
        orders.append(Order(product, bid_price, buy_budget))
    if sell_budget > 0:
        orders.append(Order(product, ask_price, -sell_budget))
    
    return orders
```

---

## 5. Stable Product Market Maker <a name="5-stable-mm"></a>

For products pegged near a known value (e.g., 10,000).

```python
def strategy_stable(self, product, state, data):
    """
    Market make around a known fair value.
    The stable product in every Prosperity edition has been pegged near 10,000.
    """
    FAIR_VALUE = 10000  # ADJUST per round's product
    SPREAD = 2          # ticks wide on each side
    RETREAT = 0.0       # no retreat needed for stable product (price doesn't trend)
    
    position = state.position.get(product, 0)
    limit = self.LIMITS[product]
    order_depth = state.order_depths[product]
    
    return compute_orders_with_budget(
        product, order_depth, FAIR_VALUE, position, limit,
        spread=SPREAD, retreat=RETREAT
    )
```

---

## 6. Volatile Product Market Maker (EMA) <a name="6-volatile-mm"></a>

For products with trending prices (BANANAS, STARFRUIT, KELP).

```python
def strategy_ema(self, product, state, data):
    """
    Estimate fair value using exponential moving average.
    Market make around the EMA with position-based retreat.
    """
    EMA_ALPHA = 0.1     # smoothing factor. Higher = more responsive. TUNE THIS.
    SPREAD = 3           # wider than stable product. TUNE THIS.
    RETREAT = 0.01       # retreat per lot of position. TUNE THIS.
    
    init_product_data(data, product, {"ema": None})
    
    order_depth = state.order_depths[product]
    position = state.position.get(product, 0)
    limit = self.LIMITS[product]
    
    # Compute mid price
    if not order_depth.buy_orders or not order_depth.sell_orders:
        return []
    best_bid = max(order_depth.buy_orders.keys())
    best_ask = min(order_depth.sell_orders.keys())
    mid = (best_bid + best_ask) / 2
    
    # Update EMA
    if data[product]["ema"] is None:
        data[product]["ema"] = mid
    else:
        data[product]["ema"] = EMA_ALPHA * mid + (1 - EMA_ALPHA) * data[product]["ema"]
    
    fair_value = data[product]["ema"]
    
    return compute_orders_with_budget(
        product, order_depth, fair_value, position, limit,
        spread=SPREAD, retreat=RETREAT
    )
```

---

## 7. Wall-Mid Calculator <a name="7-wall-mid"></a>

Approximates IMC's hidden fair value. **Use for stable products only.** For volatile products, EMA is better. For baskets, use synthetic price. For options, use Black-Scholes.

```python
def compute_wall_mid(order_depth):
    """
    Find the price levels with deepest liquidity on each side,
    then average them. Approximates IMC's hidden fair value.
    
    Only reliable for stable-price products where IMC bots place
    large "wall" orders at fair value.
    """
    if not order_depth.buy_orders or not order_depth.sell_orders:
        return None
    
    # Find bid level with most volume
    wall_bid = max(order_depth.buy_orders.keys(),
                   key=lambda p: order_depth.buy_orders[p])
    
    # Find ask level with most volume (works regardless of sign convention)
    wall_ask = max(order_depth.sell_orders.keys(),
                   key=lambda p: abs(order_depth.sell_orders[p]))
    
    return (wall_bid + wall_ask) / 2
```

---

## 8. Z-Score Basket Arbitrage <a name="8-basket-arb"></a>

For products with known basket relationships (e.g., BASKET = 6*A + 3*B + 1*C).

```python
def strategy_basket(self, basket_product, state, data):
    """
    Trade basket vs synthetic price from components.
    
    CONFIGURE PER ROUND:
    - COMPONENTS: dict mapping component product -> weight in basket
    - Z_ENTRY: z-score threshold to enter (typically 1.5-2.0)
    - Z_EXIT: z-score threshold to exit (typically 0.5)
    """
    COMPONENTS = {
        # "CROISSANTS": 6, "JAMS": 3, "DJEMBES": 1,  # EXAMPLE from P3
    }
    Z_ENTRY = 1.5   # TUNE THIS
    Z_EXIT = 0.5
    HISTORY_LEN = 100
    
    init_product_data(data, basket_product, {"spread_history": []})
    
    # Compute synthetic basket price from component mid prices
    synthetic = 0
    for component, weight in COMPONENTS.items():
        if component not in state.order_depths:
            return []
        depth = state.order_depths[component]
        if not depth.buy_orders or not depth.sell_orders:
            return []
        comp_mid = (max(depth.buy_orders.keys()) + min(depth.sell_orders.keys())) / 2
        synthetic += weight * comp_mid
    
    # Get basket mid price
    basket_depth = state.order_depths[basket_product]
    if not basket_depth.buy_orders or not basket_depth.sell_orders:
        return []
    basket_mid = (max(basket_depth.buy_orders.keys()) + min(basket_depth.sell_orders.keys())) / 2
    
    # Compute spread
    spread = basket_mid - synthetic
    append_capped(data[basket_product]["spread_history"], round(spread, 2), HISTORY_LEN)
    
    history = data[basket_product]["spread_history"]
    if len(history) < 30:
        return []  # need enough data for statistics
    
    # Compute z-score
    mean_spread = sum(history) / len(history)
    variance = sum((x - mean_spread) ** 2 for x in history) / len(history)
    std_spread = math.sqrt(variance) if variance > 0 else 1
    z_score = (spread - mean_spread) / std_spread
    
    # Generate orders - trade ONLY the basket, not components
    position = state.position.get(basket_product, 0)
    limit = self.LIMITS.get(basket_product, 50)
    orders = []
    
    if z_score > Z_ENTRY:
        # Basket expensive relative to components -> SELL basket
        sell_budget = limit + position
        if sell_budget > 0:
            best_bid = max(basket_depth.buy_orders.keys())
            qty = min(sell_budget, abs(basket_depth.buy_orders[best_bid]))
            if qty > 0:
                orders.append(Order(basket_product, best_bid, -qty))
    
    elif z_score < -Z_ENTRY:
        # Basket cheap relative to components -> BUY basket
        buy_budget = limit - position
        if buy_budget > 0:
            best_ask = min(basket_depth.sell_orders.keys())
            qty = min(buy_budget, abs(basket_depth.sell_orders[best_ask]))
            if qty > 0:
                orders.append(Order(basket_product, best_ask, qty))
    
    elif abs(z_score) < Z_EXIT and position != 0:
        # Mean reverted -> close position
        if position > 0:
            best_bid = max(basket_depth.buy_orders.keys())
            orders.append(Order(basket_product, best_bid, -position))
        else:
            best_ask = min(basket_depth.sell_orders.keys())
            orders.append(Order(basket_product, best_ask, -position))
    
    return orders
```

---

## 9. Black-Scholes + Implied Vol Solver <a name="9-options"></a>

**Pure Python. No scipy.** Uses `norm_cdf` and `norm_pdf` from Section 2.

```python
def bs_call_price(S, K, T, r, sigma):
    """Black-Scholes European call price."""
    if T <= 0 or sigma <= 0:
        return max(S - K, 0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)

def bs_delta(S, K, T, r, sigma):
    """Delta of a European call."""
    if T <= 0 or sigma <= 0:
        return 1.0 if S > K else 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return norm_cdf(d1)

def bs_vega(S, K, T, r, sigma):
    """Vega of a European call (same for put)."""
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return S * norm_pdf(d1) * math.sqrt(T)

def implied_vol(market_price, S, K, T, r, tol=1e-6, max_iter=100):
    """
    Newton-Raphson to compute implied volatility.
    Returns IV or None if convergence fails.
    """
    if market_price <= 0 or T <= 0:
        return None
    
    sigma = 0.2  # initial guess
    for _ in range(max_iter):
        price = bs_call_price(S, K, T, r, sigma)
        vega = bs_vega(S, K, T, r, sigma)
        if abs(vega) < 1e-10:
            break
        sigma = sigma - (price - market_price) / vega
        sigma = max(sigma, 0.001)  # floor at 0.1% vol
        if abs(price - market_price) < tol:
            return sigma
    
    return sigma if abs(bs_call_price(S, K, T, r, sigma) - market_price) < 1.0 else None


def strategy_option(self, voucher, underlying, strike, tte_years, state, data):
    """
    IV mean-reversion strategy for options.
    
    Args:
        voucher: option product name (e.g., "VOUCHER_10000")
        underlying: underlying product name (e.g., "VOLCANIC_ROCK")
        strike: option strike price
        tte_years: time to expiry in years
    
    Returns:
        (voucher_orders, underlying_orders) - two separate lists.
    
    INTEGRATION WARNING: This returns orders for TWO products. When merging
    into the result dict, use extend() not assignment to avoid overwriting
    existing orders (e.g., from market making on the underlying):
    
        v_orders, u_orders = self.strategy_option(...)
        result.setdefault(voucher, []).extend(v_orders)
        result.setdefault(underlying, []).extend(u_orders)
    
    If combining with market making on the underlying, you must also ensure
    the TOTAL orders across both strategies respect the underlying's position
    limit. Consider computing the market-making orders first, then passing the
    remaining budget to the options hedge.
    """
    IV_WINDOW = 50
    IV_ENTRY_THRESHOLD = 0.02  # trade when IV deviates this much from mean
    
    init_product_data(data, voucher, {"iv_history": []})
    
    # Get underlying mid
    u_depth = state.order_depths.get(underlying)
    if not u_depth or not u_depth.buy_orders or not u_depth.sell_orders:
        return [], []
    S = (max(u_depth.buy_orders.keys()) + min(u_depth.sell_orders.keys())) / 2
    
    # Get option mid
    v_depth = state.order_depths.get(voucher)
    if not v_depth or not v_depth.buy_orders or not v_depth.sell_orders:
        return [], []
    option_mid = (max(v_depth.buy_orders.keys()) + min(v_depth.sell_orders.keys())) / 2
    
    # Compute IV
    iv = implied_vol(option_mid, S, strike, tte_years, 0)
    if iv is None:
        return [], []
    
    append_capped(data[voucher]["iv_history"], round(iv, 6), IV_WINDOW)
    
    iv_hist = data[voucher]["iv_history"]
    if len(iv_hist) < 20:
        return [], []
    
    mean_iv = sum(iv_hist) / len(iv_hist)
    
    voucher_orders = []
    underlying_orders = []
    
    v_position = state.position.get(voucher, 0)
    v_limit = self.LIMITS.get(voucher, 50)
    u_position = state.position.get(underlying, 0)
    u_limit = self.LIMITS.get(underlying, 50)
    
    if iv > mean_iv + IV_ENTRY_THRESHOLD:
        # IV high -> option expensive -> SELL
        sell_budget = v_limit + v_position
        if sell_budget > 0:
            best_bid = max(v_depth.buy_orders.keys())
            qty = min(sell_budget, 5)  # conservative size
            voucher_orders.append(Order(voucher, best_bid, -qty))
            
            # Delta hedge: selling calls -> buy underlying
            delta = bs_delta(S, strike, tte_years, 0, iv)
            hedge_qty = round(delta * qty)
            hedge_budget = u_limit - u_position
            hedge_qty = min(hedge_qty, hedge_budget)
            if hedge_qty > 0:
                best_ask = min(u_depth.sell_orders.keys())
                underlying_orders.append(Order(underlying, best_ask, hedge_qty))
    
    elif iv < mean_iv - IV_ENTRY_THRESHOLD:
        # IV low -> option cheap -> BUY
        buy_budget = v_limit - v_position
        if buy_budget > 0:
            best_ask = min(v_depth.sell_orders.keys())
            qty = min(buy_budget, 5)
            voucher_orders.append(Order(voucher, best_ask, qty))
            
            # Delta hedge: buying calls -> sell underlying
            delta = bs_delta(S, strike, tte_years, 0, iv)
            hedge_qty = round(delta * qty)
            hedge_budget = u_limit + u_position
            hedge_qty = min(hedge_qty, hedge_budget)
            if hedge_qty > 0:
                best_bid = max(u_depth.buy_orders.keys())
                underlying_orders.append(Order(underlying, best_bid, -hedge_qty))
    
    return voucher_orders, underlying_orders
```

---

## 10. Bot Tracker (Round 5) <a name="10-bot-tracker"></a>

```python
def track_bots(self, state, data):
    """
    Track bot trading behavior from market_trades.
    Call every timestep in Round 5 to build bot profiles.
    """
    if "bots" not in data:
        data["bots"] = {}
    
    for product in state.market_trades:
        for trade in state.market_trades[product]:
            for actor, is_buy in [(trade.buyer, True), (trade.seller, False)]:
                if actor == "SUBMISSION":  # that's us
                    continue
                if actor not in data["bots"]:
                    data["bots"][actor] = {
                        "buy_count": 0, "sell_count": 0,
                        "buy_value": 0.0, "sell_value": 0.0,
                    }
                bot = data["bots"][actor]
                if is_buy:
                    bot["buy_count"] += trade.quantity
                    bot["buy_value"] += trade.price * trade.quantity
                else:
                    bot["sell_count"] += trade.quantity
                    bot["sell_value"] += trade.price * trade.quantity

def get_profitable_bots(data, min_trades=50):
    """
    Identify bots with avg_sell > avg_buy (consistently profitable).
    Returns list of (bot_name, edge_per_unit) sorted by profitability.
    """
    results = []
    for name, stats in data.get("bots", {}).items():
        if stats["buy_count"] >= min_trades and stats["sell_count"] >= min_trades:
            avg_buy = stats["buy_value"] / stats["buy_count"]
            avg_sell = stats["sell_value"] / stats["sell_count"]
            edge = avg_sell - avg_buy
            if edge > 0:
                results.append((name, edge))
    return sorted(results, key=lambda x: -x[1])
```

---

## 11. Data Reuse Detection <a name="11-data-reuse"></a>

Run this in a Jupyter notebook, NOT in the Trader class.

```python
import numpy as np

def check_data_reuse(new_prices, historical_dict):
    """
    Check if new_prices correlate with any historical series.
    
    Args:
        new_prices: list of float, the new round's mid prices
        historical_dict: dict of {"P3_KELP": [...], "P2_STARFRUIT": [...], ...}
    
    Returns:
        list of (name, correlation) sorted by abs(correlation), descending
    """
    results = []
    new = np.array(new_prices)
    
    for name, hist in historical_dict.items():
        hist = np.array(hist)
        min_len = min(len(new), len(hist))
        if min_len < 50:
            continue
        
        # Spearman rank correlation (robust to scaling/offset differences)
        from scipy.stats import spearmanr  # OK in notebook, NOT in submission
        corr, pval = spearmanr(new[:min_len], hist[:min_len])
        
        if abs(corr) > 0.8:
            results.append((name, round(corr, 4)))
    
    return sorted(results, key=lambda x: -abs(x[1]))
```

---

## 12. FX Arbitrage Solver (Manual Challenge) <a name="12-fx-arb"></a>

```python
import math

def find_fx_arbitrage(rates):
    """
    Find profitable currency conversion cycles using Bellman-Ford.
    
    Args:
        rates: dict of {("USD", "EUR"): 0.92, ("EUR", "GBP"): 0.86, ...}
    
    Returns:
        (cycle, profit_multiplier) or None if no arbitrage exists
        cycle is a list of currencies, e.g. ["USD", "EUR", "GBP", "USD"]
    """
    # Extract all currencies
    currencies = set()
    for (a, b) in rates:
        currencies.add(a)
        currencies.add(b)
    currencies = list(currencies)
    
    # Bellman-Ford on -log(rate) to find negative cycles
    dist = {c: 0.0 for c in currencies}
    parent = {c: None for c in currencies}
    
    # Relax edges |V| times
    for iteration in range(len(currencies)):
        updated = False
        for (a, b), rate in rates.items():
            if rate <= 0:
                continue
            weight = -math.log(rate)
            if dist[a] + weight < dist[b] - 1e-10:
                dist[b] = dist[a] + weight
                parent[b] = a
                updated = True
        if not updated:
            break
    
    # Check for negative cycle (= profitable arbitrage)
    for (a, b), rate in rates.items():
        if rate <= 0:
            continue
        weight = -math.log(rate)
        if dist[a] + weight < dist[b] - 1e-10:
            # Found arbitrage. Trace the cycle.
            # Walk back |V| times to ensure we're in the cycle
            node = b
            for _ in range(len(currencies)):
                if parent.get(node) is None:
                    node = b  # fallback
                    break
                node = parent[node]
            
            # Now trace the cycle
            cycle_start = node
            cycle = [cycle_start]
            current = parent[cycle_start]
            safety = 0
            while current != cycle_start and safety < len(currencies) + 1:
                cycle.append(current)
                current = parent[current]
                safety += 1
            cycle.append(cycle_start)
            cycle.reverse()
            
            # Compute profit multiplier
            profit = 1.0
            for i in range(len(cycle) - 1):
                key = (cycle[i], cycle[i + 1])
                if key in rates:
                    profit *= rates[key]
            
            return cycle, profit
    
    return None
```

---

## 13. New Round Analysis Notebook <a name="13-analysis"></a>

Run this immediately when a new round's data becomes available. This is Person B's first task.

```python
"""
NEW ROUND ANALYSIS TEMPLATE
Run in Jupyter. NOT part of the Trader class.
"""
import numpy as np
import pandas as pd
# import matplotlib.pyplot as plt  # if available

# --- 1. Load data ---
# Adapt this to P4's data format (check the backtester output or downloaded logs)
# df = pd.read_csv("round_N_data.csv")

# --- 2. Per-product analysis ---
def analyze_product(prices, name):
    """Quick characterization of a product."""
    prices = np.array(prices)
    returns = np.diff(prices)
    
    print(f"\n=== {name} ===")
    print(f"  Mean: {prices.mean():.2f}")
    print(f"  Std:  {prices.std():.2f}")
    print(f"  Min:  {prices.min():.2f}")
    print(f"  Max:  {prices.max():.2f}")
    
    # Is it stable? (std < 5 and mean near 10,000)
    if prices.std() < 5:
        print(f"  -> STABLE PRODUCT. Hardcode fair value = {round(prices.mean())}")
        return "stable"
    
    # Mean-reverting or trending?
    autocorr = np.corrcoef(returns[:-1], returns[1:])[0, 1]
    print(f"  Return autocorrelation: {autocorr:.4f}")
    if autocorr < -0.1:
        print(f"  -> MEAN-REVERTING. Use mean-reversion strategy.")
        return "mean_reverting"
    elif autocorr > 0.1:
        print(f"  -> TRENDING. Use EMA/momentum strategy.")
        return "trending"
    else:
        print(f"  -> UNCLEAR. Use EMA with wide spread.")
        return "unclear"

# --- 3. Cross-product correlations ---
def check_correlations(products_dict):
    """
    products_dict: {"PRODUCT_A": [prices], "PRODUCT_B": [prices], ...}
    """
    names = list(products_dict.keys())
    print("\n=== CORRELATIONS ===")
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a = np.array(products_dict[names[i]])
            b = np.array(products_dict[names[j]])
            min_len = min(len(a), len(b))
            corr = np.corrcoef(a[:min_len], b[:min_len])[0, 1]
            if abs(corr) > 0.7:
                print(f"  HIGH: {names[i]} vs {names[j]}: {corr:.4f}")

# --- 4. Check for basket relationships ---
# If a BASKET product exists, try to find the weights:
# synthetic = w1 * comp1_mid + w2 * comp2_mid + ...
# Try integer weights 1-10 and check which combination
# minimizes the spread variance.

# --- 5. Data reuse check ---
# Load prior-year price series from cloned GitHub repos
# Run check_data_reuse() from Section 11
```
