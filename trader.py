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
        EMERALDS_SPREAD = 3

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
        EMA_ALPHA = 0.12
        TOMATOES_SPREAD = 5
        RETREAT = 0.01

        order_depth = state.order_depths[product]
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return []

        init_product_data(data, product, {"ema": None})

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

    def bid(self):
    	return 15  # UPDATE in Round 2 with actual bid value
