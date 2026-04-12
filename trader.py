import json
import math
from datamodel import OrderDepth, TradingState, Order


# ── Math utilities ─────────────────────────────────────────────────────────────

def norm_cdf(x):
    a1, a2, a3, a4, a5, p = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429, 0.3275911
    sign = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return 0.5 * (1.0 + sign * y)

def norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


# ── State serialization ────────────────────────────────────────────────────────

def init_product_data(data, product, defaults=None):
    if product not in data:
        data[product] = defaults or {}

def append_capped(lst, value, max_len=50):
    lst.append(value)
    if len(lst) > max_len:
        del lst[:-max_len]


# ── Position budget + order placement ─────────────────────────────────────────

def compute_orders_with_budget(product, order_depth, fair_value, position, limit, spread=2.0, retreat=0.0):
    """
    sell_orders volumes are NEGATIVE (verified from runner.py).
    Order price and quantity must be int (verified from type_check_orders).
    """
    orders = []
    buy_budget = limit - position
    sell_budget = limit + position

    theo = fair_value - retreat * position

    # Phase 1: take mispriced resting orders
    if order_depth.sell_orders:
        for price in sorted(order_depth.sell_orders.keys()):
            if price < theo and buy_budget > 0:
                available = -order_depth.sell_orders[price]  # negate: volumes are negative
                qty = min(available, buy_budget)
                if qty > 0:
                    orders.append(Order(product, int(price), int(qty)))
                    buy_budget -= qty

    if order_depth.buy_orders:
        for price in sorted(order_depth.buy_orders.keys(), reverse=True):
            if price > theo and sell_budget > 0:
                available = order_depth.buy_orders[price]
                qty = min(available, sell_budget)
                if qty > 0:
                    orders.append(Order(product, int(price), -int(qty)))
                    sell_budget -= qty

    # Phase 2: passive quotes with remaining capacity
    bid_price = int(math.floor(theo - spread))
    ask_price = int(math.ceil(theo + spread))

    if buy_budget > 0:
        orders.append(Order(product, bid_price, int(buy_budget)))
    if sell_budget > 0:
        orders.append(Order(product, ask_price, -int(sell_budget)))

    return orders


# ── Wall-mid calculator ────────────────────────────────────────────────────────

def compute_wall_mid(order_depth):
    if not order_depth.buy_orders or not order_depth.sell_orders:
        return None
    wall_bid = max(order_depth.buy_orders.keys(), key=lambda p: order_depth.buy_orders[p])
    wall_ask = max(order_depth.sell_orders.keys(), key=lambda p: abs(order_depth.sell_orders[p]))
    return (wall_bid + wall_ask) / 2


# ── Trader class ───────────────────────────────────────────────────────────────

class Trader:

    LIMITS = {
        "EMERALDS": 80,
        "TOMATOES": 80,
    }

    # SWEEP PARAMS - do not rename these lines
    EMERALDS_SPREAD = 3
    TOMATOES_ALPHA  = 0.15
    TOMATOES_SPREAD = 5
    TOMATOES_RETREAT = 0.02

    # EMERALDS: stable product. Verify exact fair value from tutorial data.
    EMERALDS_FAIR_VALUE = 10000  # UPDATE after running analysis notebook on tutorial data

    def run(self, state: TradingState):
        result = {}
        conversions = 0

        data = json.loads(state.traderData) if state.traderData else {}

        if "EMERALDS" in state.order_depths:
            result["EMERALDS"] = self.strategy_stable("EMERALDS", state, data)

        if "TOMATOES" in state.order_depths:
            result["TOMATOES"] = self.strategy_ema("TOMATOES", state, data)

        traderData = json.dumps(data)
        return result, conversions, traderData

    def strategy_stable(self, product, state, data):
        EMERALDS_SPREAD = self.EMERALDS_SPREAD

        order_depth = state.order_depths[product]
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return []
        position = state.position.get(product, 0)
        limit = self.LIMITS[product]
        return compute_orders_with_budget(
            product, order_depth, self.EMERALDS_FAIR_VALUE, position, limit,
            spread=EMERALDS_SPREAD, retreat=0.0
        )

    def strategy_ema(self, product, state, data):
        EMA_ALPHA = self.TOMATOES_ALPHA
        TOMATOES_SPREAD = self.TOMATOES_SPREAD
        RETREAT = self.TOMATOES_RETREAT

        init_product_data(data, product, {"ema": None})

        order_depth = state.order_depths[product]
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return []

        position = state.position.get(product, 0)
        limit = self.LIMITS[product]

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2

        if data[product]["ema"] is None:
            data[product]["ema"] = mid
        else:
            data[product]["ema"] = EMA_ALPHA * mid + (1 - EMA_ALPHA) * data[product]["ema"]

        fair_value = data[product]["ema"]

        return compute_orders_with_budget(
            product, order_depth, fair_value, position, limit,
            spread=TOMATOES_SPREAD, retreat=RETREAT
        )
    
    def strategy_option(self, voucher, underlying, strike, tte_years, state, data):
        IV_WINDOW = 50
        IV_ENTRY_THRESHOLD = 0.02

        init_product_data(data, voucher, {"iv_history": []})

        u_depth = state.order_depths.get(underlying)
        if not u_depth or not u_depth.buy_orders or not u_depth.sell_orders:
            return [], []
        S = (max(u_depth.buy_orders.keys()) + min(u_depth.sell_orders.keys())) / 2

        v_depth = state.order_depths.get(voucher)
        if not v_depth or not v_depth.buy_orders or not v_depth.sell_orders:
            return [], []
        option_mid = (max(v_depth.buy_orders.keys()) + min(v_depth.sell_orders.keys())) / 2

        iv = implied_vol(option_mid, S, strike, tte_years, 0)
        if iv is None:
            return [], []

        append_capped(data[voucher]["iv_history"], round(iv, 6), IV_WINDOW)
        iv_hist = data[voucher]["iv_history"]
        if len(iv_hist) < 20:
            return [], []

        mean_iv = sum(iv_hist) / len(iv_hist)

        v_position = state.position.get(voucher, 0)
        v_limit    = self.LIMITS.get(voucher, 50)
        u_position = state.position.get(underlying, 0)
        u_limit    = self.LIMITS.get(underlying, 400)

        voucher_orders    = []
        underlying_orders = []

        if iv > mean_iv + IV_ENTRY_THRESHOLD:
            sell_budget = v_limit + v_position
            if sell_budget > 0:
                best_bid = max(v_depth.buy_orders.keys())
                qty = min(sell_budget, 5)
                voucher_orders.append(Order(voucher, int(best_bid), -int(qty)))
                delta      = bs_delta(S, strike, tte_years, 0, iv)
                hedge_qty  = min(round(delta * qty), u_limit - u_position)
                if hedge_qty > 0:
                    best_ask = min(u_depth.sell_orders.keys())
                    underlying_orders.append(Order(underlying, int(best_ask), int(hedge_qty)))

        elif iv < mean_iv - IV_ENTRY_THRESHOLD:
            buy_budget = v_limit - v_position
            if buy_budget > 0:
                best_ask = min(v_depth.sell_orders.keys())
                qty = min(buy_budget, 5)
                voucher_orders.append(Order(voucher, int(best_ask), int(qty)))
                delta      = bs_delta(S, strike, tte_years, 0, iv)
                hedge_qty  = min(round(delta * qty), u_limit + u_position)
                if hedge_qty > 0:
                    best_bid = max(u_depth.buy_orders.keys())
                    underlying_orders.append(Order(underlying, int(best_bid), -int(hedge_qty)))

        return voucher_orders, underlying_orders
    
    def track_bots(self, state, data):
        if "bots" not in data:
            data["bots"] = {}
        for product in state.market_trades:
            for trade in state.market_trades[product]:
                for actor, is_buy in [(trade.buyer, True), (trade.seller, False)]:
                    if not actor or actor == "SUBMISSION":
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

    def get_profitable_bots(self, data, min_trades=50):
        results = []
        for name, stats in data.get("bots", {}).items():
            if stats["buy_count"] >= min_trades and stats["sell_count"] >= min_trades:
                avg_buy = stats["buy_value"] / stats["buy_count"]
                avg_sell = stats["sell_value"] / stats["sell_count"]
                edge = avg_sell - avg_buy
                if edge > 0:
                    results.append((name, edge))
        return sorted(results, key=lambda x: -x[1])
    
def strategy_basket(self, basket_product, state, data):
    COMPONENTS = {}   # fill in Round 2 when product specs are known
    Z_ENTRY = 1.5
    Z_EXIT  = 0.5
    HISTORY_LEN = 100

    init_product_data(data, basket_product, {"spread_history": []})

    if not COMPONENTS:
        return []

    synthetic = 0
    for component, weight in COMPONENTS.items():
        if component not in state.order_depths:
            return []
        depth = state.order_depths[component]
        if not depth.buy_orders or not depth.sell_orders:
            return []
        comp_mid = (max(depth.buy_orders.keys()) + min(depth.sell_orders.keys())) / 2
        synthetic += weight * comp_mid

    basket_depth = state.order_depths.get(basket_product)
    if not basket_depth or not basket_depth.buy_orders or not basket_depth.sell_orders:
        return []
    basket_mid = (max(basket_depth.buy_orders.keys()) + min(basket_depth.sell_orders.keys())) / 2

    spread = basket_mid - synthetic
    append_capped(data[basket_product]["spread_history"], round(spread, 2), HISTORY_LEN)

    history = data[basket_product]["spread_history"]
    if len(history) < 30:
        return []

    mean_spread = sum(history) / len(history)
    variance = sum((x - mean_spread) ** 2 for x in history) / len(history)
    std_spread = math.sqrt(variance) if variance > 0 else 1
    z_score = (spread - mean_spread) / std_spread

    position = state.position.get(basket_product, 0)
    limit = self.LIMITS.get(basket_product, 50)
    orders = []

    if z_score > Z_ENTRY:
        sell_budget = limit + position
        if sell_budget > 0:
            best_bid = max(basket_depth.buy_orders.keys())
            qty = min(sell_budget, basket_depth.buy_orders[best_bid])
            if qty > 0:
                orders.append(Order(basket_product, int(best_bid), -int(qty)))

    elif z_score < -Z_ENTRY:
        buy_budget = limit - position
        if buy_budget > 0:
            best_ask = min(basket_depth.sell_orders.keys())
            qty = min(buy_budget, abs(basket_depth.sell_orders[best_ask]))
            if qty > 0:
                orders.append(Order(basket_product, int(best_ask), int(qty)))

    elif abs(z_score) < Z_EXIT and position != 0:
        if position > 0:
            best_bid = max(basket_depth.buy_orders.keys())
            orders.append(Order(basket_product, int(best_bid), -int(position)))
        else:
            best_ask = min(basket_depth.sell_orders.keys())
            orders.append(Order(basket_product, int(best_ask), -int(position)))

    return orders

# ── Black-Scholes + implied vol ────────────────────────────────────────────────

def bs_call_price(S, K, T, r, sigma):
    if T <= 0 or sigma <= 0:
        return max(S - K, 0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)

def bs_delta(S, K, T, r, sigma):
    if T <= 0 or sigma <= 0:
        return 1.0 if S > K else 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return norm_cdf(d1)

def bs_vega(S, K, T, r, sigma):
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return S * norm_pdf(d1) * math.sqrt(T)

def implied_vol(market_price, S, K, T, r, tol=1e-6, max_iter=100):
    if market_price <= 0 or T <= 0:
        return None
    sigma = 0.2
    for _ in range(max_iter):
        price = bs_call_price(S, K, T, r, sigma)
        vega  = bs_vega(S, K, T, r, sigma)
        if abs(vega) < 1e-10:
            break
        sigma = sigma - (price - market_price) / vega
        sigma = max(sigma, 0.001)
        if abs(bs_call_price(S, K, T, r, sigma) - market_price) < tol:
            return sigma
    return sigma if abs(bs_call_price(S, K, T, r, sigma) - market_price) < 1.0 else None

