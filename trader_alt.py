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


# ── State serialization ────────────────────────────────────────────────────────

def init_product_data(data, product, defaults=None):
    if product not in data:
        data[product] = defaults or {}

def append_capped(lst, value, max_len=50):
    lst.append(value)
    if len(lst) > max_len:
        del lst[:-max_len]


# ── Position budget + order placement (R1/R2 utility, kept for ASH/IPR/basket)─

def compute_orders_with_budget(product, order_depth, fair_value, position, limit, spread=2.0, retreat=0.0, sell_offset=2):
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
                available = -order_depth.sell_orders[price]
                qty = min(available, buy_budget)
                if qty > 0:
                    orders.append(Order(product, int(price), int(qty)))
                    buy_budget -= qty

    if order_depth.buy_orders:
        for price in sorted(order_depth.buy_orders.keys(), reverse=True):
            if price > theo + sell_offset and sell_budget > 0:
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

def compute_wall_mid_blend(order_depth):
    """70% wall_mid + 30% microprice. 15% lower MAE vs hidden FV."""
    if not order_depth.buy_orders or not order_depth.sell_orders:
        return None
    wb = max(order_depth.buy_orders.keys(), key=lambda p: order_depth.buy_orders[p])
    wa = max(order_depth.sell_orders.keys(), key=lambda p: abs(order_depth.sell_orders[p]))
    wm = (wb + wa) / 2

    best_bid = max(order_depth.buy_orders.keys())
    best_ask = min(order_depth.sell_orders.keys())
    v_bid = order_depth.buy_orders[best_bid]
    v_ask = abs(order_depth.sell_orders[best_ask])
    if v_bid + v_ask == 0:
        return wm
    mp = (best_bid * v_ask + best_ask * v_bid) / (v_ask + v_bid)

    return 0.7 * wm + 0.3 * mp


# ── Trader class ───────────────────────────────────────────────────────────────

class Trader:

    LIMITS = {
        # R1 products (kept for cumulative scoring; not active in R3+)
        "ASH_COATED_OSMIUM": 80,
        "INTARIAN_PEPPER_ROOT": 80,
        # R3+ products
        "HYDROGEL_PACK": 200,
        "VELVETFRUIT_EXTRACT": 200,
        "VEV_4000": 300,
        "VEV_4500": 300,
        "VEV_5000": 300,
        "VEV_5100": 300,
        "VEV_5200": 300,
        "VEV_5300": 300,
        "VEV_5400": 300,
        "VEV_5500": 300,
        "VEV_6000": 300,   # spec confirms 300 for all 10 vouchers
        "VEV_6500": 300,
    }

    # ── R1 params (ASH/IPR) ──────────────────────────────────────────────────
    ASH_COATED_OSMIUM_SPREAD       = 6
    ASH_COATED_OSMIUM_SELL_OFFSET  = 0
    ASH_COATED_OSMIUM_WALL_WEIGHT  = 0.9
    ASH_COATED_OSMIUM_FAIR_VALUE   = 10000
    ASH_TAKE_MARGIN                = 3
    IPR_BID_OFFSET                 = 0
    MAF_BID                        = 1500   # R2 manual hint (kept)

    # ── R3 delta-1 MM params (HYDROGEL, VE) ──────────────────────────────────
    HYDROGEL_PACK_SPREAD       = 6
    HYDROGEL_PACK_SELL_OFFSET  = -1
    HYDROGEL_PACK_TAKE_MARGIN  = 10

    VELVETFRUIT_EXTRACT_SPREAD      = 4
    VELVETFRUIT_EXTRACT_SELL_OFFSET = 0
    VELVETFRUIT_EXTRACT_TAKE_MARGIN = 100  # effectively disabled; VE MM loses on trending moves, options handle exposure

    ANCHOR_HYDROGEL    = 9976   # irrelevant; overridden by first wall_mid cold-start
    ANCHOR_VE          = 5262   # irrelevant; overridden by first wall_mid cold-start
    DELTA1_EMA_ALPHA   = 0.001  # was 0.00003; half-life 693 ticks. Faster convergence on live data.
    HYDROGEL_RETREAT   = 6
    VE_RETREAT         = 2

    # ── VEV (option chain) params ────────────────────────────────────────────
    VEV_STRIKES              = [5000, 5100, 5200, 5300, 5400, 5500]
    # Calibrated to 2.5-sigma of realized IV distribution from R3/R4 data.
    # Previous values (0.002-0.009) were below 1-sigma, causing noise-trading
    # and net unhedged delta exposure that lost ~5k when VE fell 42 ticks.
    VEV_THRESHOLDS           = {5000: 0.062, 5100: 0.011, 5200: 0.007,
                                5300: 0.004, 5400: 0.004, 5500: 0.009}
    VEV_POS_CAP              = 150
    VEV_IV_WINDOW            = 50
    VEV_TREND_GUARD_K        = 5400
    VEV_TREND_GUARD_THRESH   = 0.01
    VEV_HEDGE_DELTA_THRESH   = 10.0
    VEV_HEDGE_VE_BUDGET      = 30    # small; batch-only hedge via VE (30/200 = 15% of VE capacity)

    # ── R4 TTE config ────────────────────────────────────────────────────────
    # Spec: "VEV_5000 has TTE=4 days in round 4". Treated as TTE at the start
    # of R4 day 1. Robust tracking via tick counter: independent of state.day.
    # ⚠ VERIFY ON FIRST R4 SUBMISSION: print state.day & state.timestamp on
    #   the first run() call to confirm cold-start matches actual platform day.
    VEV_INITIAL_TTE_DAYS = 4.0
    TICKS_PER_DAY        = 1_000_000

    # ── Mark counterparty signal config (R4 reveal) ──────────────────────────
    # Calibrated from R3 historical (= R4 zip data) trade analysis:
    #   Mark 14 = informed, edge +12.65/HYDROGEL +18.82/VEV_4000 +4.74/VE
    #   Mark 38 = mirror dumb money, edge -12.36/-18.75 (no VE activity)
    # Strategy: smart-buy or dumb-sell -> bullish; smart-sell or dumb-buy -> bearish
    SMART_MARK             = "Mark 14"
    DUMB_MARK              = "Mark 38"
    MARK_SIGNAL_PRODUCTS   = ["HYDROGEL_PACK", "VELVETFRUIT_EXTRACT", "VEV_4000"]
    MARK_FLOW_WINDOW       = 50           # rolling buffer length per product
    # ticks of take_fair shift per unit of net signal qty.
    # Conservative: edge is 12-18 ticks/RT; we capture a fraction.
    MARK_LEAN_COEF = {
        "HYDROGEL_PACK":       0.04,
        "VELVETFRUIT_EXTRACT": 0.02,
        "VEV_4000":            0.04,
    }
    # Cap absolute lean to avoid runaway shifts on noisy bursts
    MARK_LEAN_MAX_TICKS = 4.0

    def bid(self):
        return self.MAF_BID

    # ──────────────────────────────────────────────────────────────────────────
    # ENTRY POINT
    # ──────────────────────────────────────────────────────────────────────────
    
    def run(self, state: TradingState):
        result = {}
        conversions = 0
        data = (json.loads(state.traderData) if state.traderData else None) or {}

        if state.observations:
            data["obs"] = str(state.observations)[:200]

        mark_signals = self._update_mark_signals(state, data)

        # ── TTE + elapsed_days FIRST — gates everything below ──────────────
        tte = self._compute_tte(state, data)
        elapsed_days = data.get("tte_counter", 0) / float(self.TICKS_PER_DAY)

        # ── R1 products ────────────────────────────────────────────────────
        if "ASH_COATED_OSMIUM" in state.order_depths:
            result["ASH_COATED_OSMIUM"] = self.strategy_stable("ASH_COATED_OSMIUM", state, data)
        if "INTARIAN_PEPPER_ROOT" in state.order_depths:
            result["INTARIAN_PEPPER_ROOT"] = self.strategy_ipr("INTARIAN_PEPPER_ROOT", state, data)

        # ── Mark 14 direct copy on HYDROGEL ────────────────────────────────
        m14_orders = self._mark14_copy_hydrogel(state, data)
        for k, v in m14_orders.items():
            result.setdefault(k, []).extend(v)

        mark38_orders = self._mark38_anti_copy(state, data)
        for k, v in mark38_orders.items():
            result.setdefault(k, []).extend(v)

        # ── HYDROGEL ───────────────────────────────────────────────────────
        if "HYDROGEL_PACK" in state.order_depths:
            lean = self._compute_lean("HYDROGEL_PACK", mark_signals)
            result["HYDROGEL_PACK"] = self.strategy_delta1(
                "HYDROGEL_PACK", state, data,
                spread=self.HYDROGEL_PACK_SPREAD,
                sell_offset=self.HYDROGEL_PACK_SELL_OFFSET,
                take_margin=self.HYDROGEL_PACK_TAKE_MARGIN,
                anchor_init=self.ANCHOR_HYDROGEL,
                ema_alpha=self.DELTA1_EMA_ALPHA,
                retreat=self.HYDROGEL_RETREAT,
                mark_lean=lean,
            )

        # ── VE: day-aware parameters ───────────────────────────────────────
        # D1/D2: VE rises, run full MM (take_margin=25, no passive cap)
        # D3+:   VE falls, suppress long accumulation
        if "VELVETFRUIT_EXTRACT" in state.order_depths:
            lean = self._compute_lean("VELVETFRUIT_EXTRACT", mark_signals)
            if elapsed_days < 2.0:
                ve_take_margin = 25
                ve_plc = None
            else:
                ve_take_margin = 100
                ve_plc = 0
            result["VELVETFRUIT_EXTRACT"] = self.strategy_delta1(
                "VELVETFRUIT_EXTRACT", state, data,
                spread=self.VELVETFRUIT_EXTRACT_SPREAD,
                sell_offset=self.VELVETFRUIT_EXTRACT_SELL_OFFSET,
                take_margin=ve_take_margin,
                anchor_init=self.ANCHOR_VE,
                ema_alpha=self.DELTA1_EMA_ALPHA,
                retreat=self.VE_RETREAT,
                mark_lean=lean,
                passive_long_cap=ve_plc,
            )

        # ── Intrinsic MM on deep-ITM strikes ───────────────────────────────
        vev_mm_orders = self.strategy_vev_intrinsic_mm(state, data, mark_signals)
        for k, v in vev_mm_orders.items():
            result[k] = v

        # ── Settlement: LONG on D1/D2 (VE rising), SHORT on D3 (VE falling)
        if tte is not None and tte > 0:
            if elapsed_days < 2.0:
                settle_orders = self.strategy_vev_settlement_long(state, data, tte)
            else:
                settle_orders = self.strategy_vev_settlement_short(state, data, tte)
            for k, v in settle_orders.items():
                result[k] = v

        traderData = json.dumps(data)
        return result, conversions, traderData

    # ──────────────────────────────────────────────────────────────────────────
    # HELPERS: TTE + Mark signals
    # ──────────────────────────────────────────────────────────────────────────

    def _compute_tte(self, state, data):
        ts = state.timestamp
        if "tte_counter" not in data:
            data["tte_last_ts"] = ts
            # Cold start: infer day from VE price and VEV_5300 price
            # Day 1 start: VE~5245, VEV_5300~44.  Day 2: VE~5267, VEV_5300~43.
            # Day 3 start: VE~5295, VEV_5300~58.  Day 3 is unambiguous.
            day_estimate = 0
            ve_depth = state.order_depths.get("VELVETFRUIT_EXTRACT")
            v53_depth = state.order_depths.get("VEV_5300")
            if ve_depth and ve_depth.buy_orders and ve_depth.sell_orders:
                ve_mid = (max(ve_depth.buy_orders.keys()) + min(ve_depth.sell_orders.keys())) / 2.0
                if ve_mid > 5285:
                    day_estimate = 2
                elif ve_mid > 5260:
                    day_estimate = 1
            if day_estimate < 2 and v53_depth and v53_depth.buy_orders:
                v53_bid = max(v53_depth.buy_orders.keys())
                if v53_bid > 50:
                    day_estimate = 2
            data["tte_counter"] = day_estimate * self.TICKS_PER_DAY
        else:
            if ts < data["tte_last_ts"]:
                data["tte_counter"] += self.TICKS_PER_DAY
            data["tte_last_ts"] = ts

        elapsed_ticks = data["tte_counter"] + ts
        elapsed_days = elapsed_ticks / float(self.TICKS_PER_DAY)
        tte_days = self.VEV_INITIAL_TTE_DAYS - elapsed_days
        if tte_days <= 0:
            return None
        return tte_days / 365.0

    def _update_mark_signals(self, state, data):
        """
        Maintain a rolling buffer of (timestamp, signed_qty) per signal product.
        Sign convention:
            smart buy  or dumb sell -> +qty (bullish)
            smart sell or dumb buy  -> -qty (bearish)
        Returns {product: aggregate_signed_qty_in_window}.
        """
        if "mark_flow" not in data:
            data["mark_flow"] = {p: [] for p in self.MARK_SIGNAL_PRODUCTS}
        else:
            # Self-heal if config product list changed across deploys
            for p in self.MARK_SIGNAL_PRODUCTS:
                data["mark_flow"].setdefault(p, [])

        signals = {}
        for prod in self.MARK_SIGNAL_PRODUCTS:
            buf = data["mark_flow"][prod]
            trades = state.market_trades.get(prod, []) if state.market_trades else []
            for tr in trades:
                net = 0
                if tr.buyer == self.SMART_MARK:
                    net += tr.quantity
                if tr.seller == self.SMART_MARK:
                    net -= tr.quantity
                if tr.buyer == self.DUMB_MARK:
                    net -= tr.quantity
                if tr.seller == self.DUMB_MARK:
                    net += tr.quantity
                if net != 0:
                    buf.append([tr.timestamp, net])
            # Cap buffer length
            if len(buf) > self.MARK_FLOW_WINDOW:
                del buf[:-self.MARK_FLOW_WINDOW]
            signals[prod] = sum(n for (_, n) in buf)
        return signals

    def _compute_lean(self, product, mark_signals):
        """Convert raw signal qty to clamped tick-shift for take_fair."""
        raw = mark_signals.get(product, 0)
        coef = self.MARK_LEAN_COEF.get(product, 0.0)
        lean = raw * coef
        cap = self.MARK_LEAN_MAX_TICKS
        if lean > cap:  return cap
        if lean < -cap: return -cap
        return lean

    # ──────────────────────────────────────────────────────────────────────────
    # R1 STRATEGIES (kept verbatim per instruction)
    # ──────────────────────────────────────────────────────────────────────────

    def strategy_ipr(self, product, state, data):
        order_depth = state.order_depths[product]
        if not order_depth.sell_orders:
            return []
        position = state.position.get(product, 0)
        limit = self.LIMITS[product]
        buy_budget = limit - position
        if buy_budget <= 0:
            return []

        best_ask = min(order_depth.sell_orders.keys())
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        mid = (best_ask + best_bid) / 2 if best_bid else best_ask - 7

        orders = []

        # Only eat the BEST ask level (cheapest)
        cheapest_ask = best_ask
        available = -order_depth.sell_orders[cheapest_ask]
        eat_qty = min(available, buy_budget)
        if eat_qty > 0:
            orders.append(Order(product, int(cheapest_ask), int(eat_qty)))
            buy_budget -= eat_qty

        # Post aggressive bid inside the spread for remaining
        if buy_budget > 0:
            bid_price = int(mid + self.IPR_BID_OFFSET)
            orders.append(Order(product, bid_price, int(buy_budget)))

        return orders

    def strategy_stable(self, product, state, data):
        order_depth = state.order_depths[product]
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return []
        position = state.position.get(product, 0)
        limit = self.LIMITS.get(product)
        if limit is None:
            return []

        # passive fair: tracks short-term book state
        w = self.ASH_COATED_OSMIUM_WALL_WEIGHT
        wb = max(order_depth.buy_orders.keys(), key=lambda p: order_depth.buy_orders[p])
        wa = max(order_depth.sell_orders.keys(), key=lambda p: abs(order_depth.sell_orders[p]))
        wm = (wb + wa) / 2
        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        v_bid = order_depth.buy_orders[best_bid]
        v_ask = abs(order_depth.sell_orders[best_ask])
        mp = (best_bid * v_ask + best_ask * v_bid) / (v_ask + v_bid) if (v_bid + v_ask) > 0 else wm
        passive_fair = w * wm + (1 - w) * mp

        # take fair: anchored on TRUE mean (ASH is strongly mean-reverting to 10000)
        take_fair = self.ASH_COATED_OSMIUM_FAIR_VALUE  # = 10000

        orders = []
        buy_budget = limit - position
        sell_budget = limit + position

        # Phase 1a: take asks below TAKE_FAIR - K (strong mean-revert buy)
        if order_depth.sell_orders:
            for price in sorted(order_depth.sell_orders.keys()):
                if price <= take_fair - self.ASH_TAKE_MARGIN and buy_budget > 0:
                    available = -order_depth.sell_orders[price]
                    qty = min(available, buy_budget)
                    if qty > 0:
                        orders.append(Order(product, int(price), int(qty)))
                        buy_budget -= qty

        # Phase 1b: take bids above TAKE_FAIR + K (strong mean-revert sell)
        if order_depth.buy_orders:
            for price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if price >= take_fair + self.ASH_TAKE_MARGIN and sell_budget > 0:
                    available = order_depth.buy_orders[price]
                    qty = min(available, sell_budget)
                    if qty > 0:
                        orders.append(Order(product, int(price), -int(qty)))
                        sell_budget -= qty

        # Phase 1c: additional take based on passive_fair
        if order_depth.sell_orders:
            for price in sorted(order_depth.sell_orders.keys()):
                if price < passive_fair and buy_budget > 0:
                    available = -order_depth.sell_orders[price]
                    qty = min(available, buy_budget)
                    if qty > 0:
                        orders.append(Order(product, int(price), int(qty)))
                        buy_budget -= qty
        if order_depth.buy_orders:
            for price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if price > passive_fair + self.ASH_COATED_OSMIUM_SELL_OFFSET and sell_budget > 0:
                    available = order_depth.buy_orders[price]
                    qty = min(available, sell_budget)
                    if qty > 0:
                        orders.append(Order(product, int(price), -int(qty)))
                        sell_budget -= qty

        # Phase 2: passive quotes around passive_fair
        bid_price = int(math.floor(passive_fair - self.ASH_COATED_OSMIUM_SPREAD))
        ask_price = int(math.ceil(passive_fair + self.ASH_COATED_OSMIUM_SPREAD))
        if buy_budget > 0:
            orders.append(Order(product, bid_price, int(buy_budget)))
        if sell_budget > 0:
            orders.append(Order(product, ask_price, -int(sell_budget)))
        return orders

    # ──────────────────────────────────────────────────────────────────────────
    # R2 STRATEGY (template, kept per instruction; not currently dispatched)
    # ──────────────────────────────────────────────────────────────────────────

    def strategy_basket(self, basket_product, state, data):
        COMPONENTS  = {}   # fill if a basket reappears
        Z_ENTRY     = 1.5
        Z_EXIT      = 0.5
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
        variance    = sum((x - mean_spread) ** 2 for x in history) / len(history)
        std_spread  = math.sqrt(variance) if variance > 0 else 1.0
        z_score     = (spread - mean_spread) / std_spread

        position = state.position.get(basket_product, 0)
        limit    = self.LIMITS.get(basket_product, 50)
        orders   = []

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

    # ──────────────────────────────────────────────────────────────────────────
    # R3+ STRATEGIES
    # ──────────────────────────────────────────────────────────────────────────

    def strategy_delta1(self, product, state, data, *, spread, sell_offset, take_margin,
                        anchor_init, ema_alpha=0.001, retreat=0, mark_lean=0.0, passive_long_cap=None):
        """
        Delta-1 MM with EMA-anchor split-FV + inventory-aversion + Mark lean overlay.
          take_fair    = EMA anchor + mark_lean (ticks of bias)
          passive_fair = wall_mid_blend (Phase 2 quote center)
          mark_lean    = + bullish (smart buy / dumb sell), - bearish
        Signs: sell_orders volumes NEGATIVE; Order qty positive=buy, negative=sell.
        """
        depth = state.order_depths[product]
        init_product_data(data, product, {"last_wm": None, "anchor": None, "anchor_init": anchor_init})

        wm = compute_wall_mid_blend(depth)
        if wm is not None:
            data[product]["last_wm"] = wm
        else:
            wm = data[product].get("last_wm")
        if wm is None:
            return []

        if not depth.buy_orders or not depth.sell_orders:
            return []

        position = state.position.get(product, 0)
        limit = self.LIMITS.get(product)
        if limit is None:
            return []

        # Cold-start anchor from first wall_mid, not hardcoded constant.
        # Hardcoded 9976 vs R4 actual mean 10033 caused 57-tick gap -> -4681 HYDROGEL loss.
        if data[product]["anchor"] is None:
            data[product]["anchor"] = wm
        data[product]["anchor"] = (1 - ema_alpha) * data[product]["anchor"] + ema_alpha * wm

        # Mark lean shifts take_fair: bullish lean = willing to BUY higher / SELL higher
        take_fair    = data[product]["anchor"] + mark_lean
        passive_fair = wm

        buy_budget  = limit - position
        sell_budget = limit + position
        orders = []

        # Phase 1a: take asks below take_fair - take_margin (mean-revert buy)
        # Guard: skip if at max long. Prevents catching falling knife at position ceiling.
        at_max_long = position >= (limit - 5)
        if not at_max_long:
            for price in sorted(depth.sell_orders.keys()):
                if price <= take_fair - take_margin and buy_budget > 0:
                    available = -depth.sell_orders[price]
                    qty = min(available, buy_budget)
                    if qty > 0:
                        orders.append(Order(product, int(price), int(qty)))
                        buy_budget -= qty

        # Phase 1b: take bids above take_fair + take_margin + sell_offset (mean-revert sell)
        # Guard: skip entirely if already at max short (prevents runaway short accumulation
        # when anchor is stale; the HYDROGEL -4681 loss was caused by this firing constantly).
        at_max_short = position <= -(limit - 5)
        # passive_long_cap: if set, suppresses Phase2 passive bid when position >= cap.
        # Set to 0 for VE to eliminate all passive buys on falling market.
        _plc = passive_long_cap if passive_long_cap is not None else (limit - 5)
        at_max_long_passive = position >= _plc
        if not at_max_short:
            for price in sorted(depth.buy_orders.keys(), reverse=True):
                if price >= take_fair + take_margin + sell_offset and sell_budget > 0:
                    available = depth.buy_orders[price]
                    qty = min(available, sell_budget)
                    if qty > 0:
                        orders.append(Order(product, int(price), -int(qty)))
                        sell_budget -= qty

        # Phase 2: inventory-aversion passive quotes around passive_fair
        inv_adjust = retreat * position / limit if limit > 0 else 0
        adjusted_fair = passive_fair - inv_adjust
        bid_price = int(math.floor(adjusted_fair - spread))
        ask_price = int(math.ceil(adjusted_fair + spread + sell_offset))
        # Symmetric guards: suppress passive bid at max long, passive ask at max short.
        # Prevents passive accumulation at the extremes when underlying is trending.
        if buy_budget > 0 and not at_max_long_passive:
            orders.append(Order(product, bid_price, int(buy_budget)))
        if sell_budget > 0 and not at_max_short:
            orders.append(Order(product, ask_price, -int(sell_budget)))

        return orders

    def strategy_vev_batch(self, state, data, tte):
        """
        IV mean-reversion across 6 ATM/OTM strikes (5000-5500) with net-delta hedge via VE.
        Returns {voucher: [orders], "__ve_hedge__": [orders]}.
        Caller merges __ve_hedge__ with VE MM orders before adding to result.
        """
        ve_depth = state.order_depths.get("VELVETFRUIT_EXTRACT")
        if not ve_depth or not ve_depth.buy_orders or not ve_depth.sell_orders:
            return {}
        ve_bid = max(ve_depth.buy_orders.keys())
        ve_ask = min(ve_depth.sell_orders.keys())
        S = (ve_bid + ve_ask) / 2.0
        ve_half_spread = (ve_ask - ve_bid) / 2.0

        result = {}
        net_delta_new = 0.0  # delta contribution from orders placed THIS tick

        for K in self.VEV_STRIKES:
            voucher = "VEV_{}".format(K)
            v_depth = state.order_depths.get(voucher)
            if not v_depth or not v_depth.buy_orders or not v_depth.sell_orders:
                continue
            v_bid = max(v_depth.buy_orders.keys())
            v_ask = min(v_depth.sell_orders.keys())
            option_mid = (v_bid + v_ask) / 2.0

            iv = implied_vol(option_mid, S, K, tte, 0)
            if iv is None:
                continue

            init_product_data(data, voucher, {"iv_history": []})
            append_capped(data[voucher]["iv_history"], round(iv, 6), self.VEV_IV_WINDOW)
            iv_hist = data[voucher]["iv_history"]
            if len(iv_hist) < 20:
                continue

            # K=5400 trend guard: skip when IV trends > 1% over last 50 samples
            if K == self.VEV_TREND_GUARD_K and len(iv_hist) >= self.VEV_IV_WINDOW:
                if abs(iv_hist[-1] - iv_hist[-self.VEV_IV_WINDOW]) > self.VEV_TREND_GUARD_THRESH:
                    continue

            mean_iv = sum(iv_hist) / len(iv_hist)
            threshold = self.VEV_THRESHOLDS[K]
            delta = bs_delta(S, K, tte, 0, iv)
            v_pos = state.position.get(voucher, 0)
            cap = self.VEV_POS_CAP
            lim = self.LIMITS.get(voucher, 300)

            if iv > mean_iv + threshold:
                # IV elevated: sell voucher (short vega)
                can_sell = min(cap + v_pos, lim + v_pos)
                if can_sell > 0:
                    qty = min(can_sell, 15)
                    result[voucher] = [Order(voucher, int(v_bid), -int(qty))]
                    net_delta_new -= delta * qty   # short call = short delta

            elif iv < mean_iv - threshold:
                # IV depressed: buy voucher (long vega)
                can_buy = min(cap - v_pos, lim - v_pos)
                if can_buy > 0:
                    qty = min(can_buy, 15)
                    result[voucher] = [Order(voucher, int(v_ask), int(qty))]
                    net_delta_new += delta * qty   # long call = long delta

        # Net-delta hedge via VE when threshold crossed and spread acceptable
        if abs(net_delta_new) > 0 and ve_half_spread <= 3.0:
            existing_delta = 0.0
            # Only include batch-owned strikes (5000-5500) in existing_delta.
            # VEV_4000/4500 are owned by intrinsic_mm, not batch; including them
            # causes the hedge to spiral by re-hedging positions it didn't create.
            for K in self.VEV_STRIKES:
                vk_pos = state.position.get("VEV_{}".format(K), 0)
                if vk_pos == 0:
                    continue
                vk_depth = state.order_depths.get("VEV_{}".format(K))
                if not vk_depth or not vk_depth.buy_orders or not vk_depth.sell_orders:
                    continue
                vk_mid = (max(vk_depth.buy_orders.keys()) + min(vk_depth.sell_orders.keys())) / 2.0
                vk_iv = implied_vol(vk_mid, S, K, tte, 0)
                if vk_iv:
                    existing_delta += vk_pos * bs_delta(S, K, tte, 0, vk_iv)
                elif K in (4000, 4500):
                    # Deep ITM at R3/R4 spot (~5240): solver returns None when extrinsic
                    # exceeds 1 tick because vega ≈ 0 at sigma=0.2. Delta is ~1.0.
                    existing_delta += vk_pos * 1.0
                # else: solver failed on near-ATM/OTM strike; skip (rare).

            total_delta = existing_delta + net_delta_new
            if abs(total_delta) > self.VEV_HEDGE_DELTA_THRESH:
                # Hedge via VE. Budget=30 (15% of VE capacity) avoids overwhelming VE MM.
                # Only batch positions (5000-5500) are tracked in existing_delta.
                # VEV_4000/4500 from intrinsic_mm are excluded: batch doesn't manage those.
                desired_ve_target = -round(total_delta)
                ve_pos = state.position.get("VELVETFRUIT_EXTRACT", 0)
                hedge_change = desired_ve_target - ve_pos
                ve_lim = self.LIMITS.get("VELVETFRUIT_EXTRACT", 200)
                budget = self.VEV_HEDGE_VE_BUDGET
                if hedge_change > 0:
                    qty = min(hedge_change, budget, ve_lim - ve_pos)
                    if qty > 0:
                        result["__ve_hedge__"] = [Order("VELVETFRUIT_EXTRACT", int(ve_ask), int(qty))]
                elif hedge_change < 0:
                    qty = min(-hedge_change, budget, ve_lim + ve_pos)
                    if qty > 0:
                        result["__ve_hedge__"] = [Order("VELVETFRUIT_EXTRACT", int(ve_bid), -int(qty))]

        return result

    def strategy_vev_intrinsic_mm(self, state, data, mark_signals=None):
        """
        Passive MM on deep-ITM strikes (4000, 4500) — fair value ≈ intrinsic.
        Quote 1 tick inside the visible book; capture the bot spread.
        Mark lean for VEV_4000: aggressive bid bump or ask cut on strong signal.
        Signs: sell_orders volumes NEGATIVE.
        """
        ve_depth = state.order_depths.get("VELVETFRUIT_EXTRACT")
        if not ve_depth or not ve_depth.buy_orders or not ve_depth.sell_orders:
            return {}
        ve_mid = (max(ve_depth.buy_orders.keys()) + min(ve_depth.sell_orders.keys())) / 2.0

        # Deep ITM only: fair value ≈ intrinsic, low gamma risk, wide spread.
        # 5200-5500 are handled by settlement_short (too-tight spreads for passive MM).
        STRIKE_CONFIG = {
            4000: (200, 30, 2),
            4500: (200, 30, 2),
        }

        out = {}
        for K, (cap, quote_qty, min_spread) in STRIKE_CONFIG.items():
            voucher = "VEV_{}".format(K)
            v_depth = state.order_depths.get(voucher)
            if not v_depth or not v_depth.buy_orders or not v_depth.sell_orders:
                continue
            v_bid = max(v_depth.buy_orders.keys())
            v_ask = min(v_depth.sell_orders.keys())
            if v_ask - v_bid < min_spread:
                continue

            v_pos = state.position.get(voucher, 0)
            v_lim = self.LIMITS.get(voucher, 300)

            buy_budget  = min(cap - v_pos, v_lim - v_pos)
            sell_budget = min(cap + v_pos, v_lim + v_pos)

            bid_price = int(v_bid + 1)
            ask_price = int(v_ask - 1)

            if mark_signals and voucher == "VEV_4000":
                lean = self._compute_lean(voucher, mark_signals)
                if lean > 1.0:
                    bid_price += 1
                elif lean < -1.0:
                    ask_price -= 1

            if bid_price >= ask_price:
                continue

            intrinsic = max(ve_mid - K, 0.0)
            if ask_price <= intrinsic:
                sell_budget = 0
            elif bid_price >= intrinsic + 50:
                buy_budget = 0

            orders = []
            if buy_budget > 0:
                orders.append(Order(voucher, bid_price,  int(min(quote_qty, buy_budget))))
            if sell_budget > 0:
                orders.append(Order(voucher, ask_price, -int(min(quote_qty, sell_budget))))
            if orders:
                out[voucher] = orders

        return out

    def strategy_vev_settlement_short(self, state, data, tte):
        """
        Short all strikes 5100-5500. Exit threshold = K + estimated_premium_at_entry.
        This is break-even based, not OTM-boundary based.
        5000 excluded: break-even = 5296, VE starts at 5295, zero margin.
        4000/4500 handled by intrinsic_mm (passive, no directional risk).
        """
        if tte is None or tte <= 0:
            return {}

        ve_depth = state.order_depths.get("VELVETFRUIT_EXTRACT")
        if not ve_depth or not ve_depth.buy_orders or not ve_depth.sell_orders:
            return {}
        ve_mid = (max(ve_depth.buy_orders.keys()) + min(ve_depth.sell_orders.keys())) / 2.0

        # Exit threshold = K + approximate current bid of that voucher at entry.
        # These are calibrated to this round's observed prices. Update if re-running on
        # different round data. The logic: we only lose at expiry if VE > K + what we sold for.
        EXIT_VE = {
            5000: 5290,   # VE starts at 5295; only enter after it falls 5+ ticks
            5100: 5315,
            5200: 5330,
            5300: 5360,
            5400: 5425,
            5500: 5510,
        }
        TARGETS = {5000: -300, 5100: -300, 5200: -300, 5300: -300, 5400: -300, 5500: -300}
        ENTRY_QTY = 30

        out = {}
        for K, target in TARGETS.items():
            voucher = "VEV_{}".format(K)
            v_pos   = state.position.get(voucher, 0)
            v_lim   = self.LIMITS.get(voucher, 300)
            v_depth = state.order_depths.get(voucher)

            exit_threshold = EXIT_VE[K]
            if ve_mid >= exit_threshold:
                # VE above break-even: cut the short immediately
                if v_pos < 0 and v_depth and v_depth.sell_orders:
                    best_ask = min(v_depth.sell_orders.keys())
                    qty = min(-v_pos, v_lim - v_pos)
                    if qty > 0:
                        out[voucher] = [Order(voucher, int(best_ask), int(qty))]
                continue

            if not v_depth or not v_depth.buy_orders:
                continue
            v_bid = max(v_depth.buy_orders.keys())
            if v_bid < 1:
                continue

            remaining = (-target) - (-v_pos)
            if remaining <= 0:
                continue

            qty = min(remaining, v_lim + v_pos, ENTRY_QTY)
            if qty > 0:
                out[voucher] = [Order(voucher, int(v_bid), -int(qty))]

        return out

    def _track_all_bots(self, state, data):
        """Track all bot buy/sell behavior from market_trades (R5 bot-reveal round)."""
        if "bots" not in data:
            data["bots"] = {}
        if not state.market_trades:
            return
        for product, trades in state.market_trades.items():
            for tr in trades:
                for actor, is_buy in [(tr.buyer, True), (tr.seller, False)]:
                    if not actor or actor == "SUBMISSION":
                        continue
                    key = actor
                    if key not in data["bots"]:
                        data["bots"][key] = {"bc": 0, "bv": 0.0, "sc": 0, "sv": 0.0, "prods": {}}
                    b = data["bots"][key]
                    if is_buy:
                        b["bc"] += tr.quantity; b["bv"] += tr.price * tr.quantity
                    else:
                        b["sc"] += tr.quantity; b["sv"] += tr.price * tr.quantity
                    b["prods"][product] = b["prods"].get(product, 0) + tr.quantity

    def _bot_copy_trade(self, state, data):
        """
        Copy-trade the most profitable bot identified from market_trades history.
        Profitable bot: avg_sell > avg_buy (buys low, sells high).
        When that bot buys -> we buy at same price; when it sells -> we sell.
        Cap: 50% of position limit to avoid conflicts with existing strategies.
        Requires min 100 trades on each side before trusting the signal.
        """
        if not state.market_trades or "bots" not in data:
            return {}

        # Find most profitable bot with sufficient data
        best_bot = None; best_edge = 0.0
        for name, stats in data["bots"].items():
            if stats["bc"] < 100 or stats["sc"] < 100:
                continue
            avg_buy  = stats["bv"] / stats["bc"]
            avg_sell = stats["sv"] / stats["sc"]
            edge = avg_sell - avg_buy
            if edge > best_edge:
                best_edge = edge; best_bot = name

        if not best_bot:
            return {}

        result = {}
        # This tick's trades by the profitable bot
        for product, trades in state.market_trades.items():
            if product not in self.LIMITS:
                continue
            if product.startswith("VEV_"):
                continue
            limit = self.LIMITS[product]
            copy_cap = limit // 2  # 50% of limit for copy-trades
            position = state.position.get(product, 0)
            depth = state.order_depths.get(product)
            if not depth:
                continue

            for tr in trades:
                if tr.buyer == best_bot and depth.sell_orders:
                    # Bot bought -> we buy at best ask
                    buy_budget = min(copy_cap - position, limit - position)
                    if buy_budget > 0:
                        best_ask = min(depth.sell_orders.keys())
                        qty = min(buy_budget, tr.quantity)
                        if qty > 0:
                            result.setdefault(product, []).append(Order(product, int(best_ask), int(qty)))
                elif tr.seller == best_bot and depth.buy_orders:
                    # Bot sold -> we sell at best bid
                    sell_budget = min(copy_cap + position, limit + position)
                    if sell_budget > 0:
                        best_bid = max(depth.buy_orders.keys())
                        qty = min(sell_budget, tr.quantity)
                        if qty > 0:
                            result.setdefault(product, []).append(Order(product, int(best_bid), -int(qty)))
        return result
    
    def _mark38_anti_copy(self, state, data):
        """
        Direct anti-copy of Mark 38 (confirmed dumb money).
        M38 buys -> we sell. M38 sells -> we buy.
        Capped at 20 units/tick to avoid conflicts with existing positions.
        Only on products where M38 is confirmed active: HG and VEV_4000.
        """
        if not state.market_trades:
            return {}
        result = {}
        for product in ("HYDROGEL_PACK", "VEV_4000"):
            if product not in state.order_depths or product not in self.LIMITS:
                continue
            depth = state.order_depths[product]
            position = state.position.get(product, 0)
            limit = self.LIMITS[product]
            for tr in state.market_trades.get(product, []):
                if tr.buyer == self.DUMB_MARK and depth.buy_orders:
                    sell_budget = min(limit + position, 20)
                    if sell_budget > 0:
                        qty = min(sell_budget, tr.quantity)
                        if qty > 0:
                            best_bid = max(depth.buy_orders.keys())
                            result.setdefault(product, []).append(
                                Order(product, int(best_bid), -int(qty)))
                            position -= qty
                elif tr.seller == self.DUMB_MARK and depth.sell_orders:
                    buy_budget = min(limit - position, 20)
                    if buy_budget > 0:
                        qty = min(buy_budget, tr.quantity)
                        if qty > 0:
                            best_ask = min(depth.sell_orders.keys())
                            result.setdefault(product, []).append(
                                Order(product, int(best_ask), int(qty)))
                            position += qty
        return result
    
    def _mark14_copy_hydrogel(self, state, data):
        """
        Direct copy of Mark 14 on HYDROGEL + VEV_4000.
        Mark 14 edge: +12.65/HG, +18.82/VEV_4000. Take from ask when she buys.
        Capped at 15 units/tick to avoid overwhelming strategy_delta1.
        """
        if not state.market_trades:
            return {}
        result = {}
        for product in ("HYDROGEL_PACK", "VEV_4000"):
            depth = state.order_depths.get(product)
            if not depth or not depth.sell_orders:
                continue
            best_ask = min(depth.sell_orders.keys())
            position = state.position.get(product, 0)
            limit = self.LIMITS.get(product, 80)
            for tr in state.market_trades.get(product, []):
                if tr.buyer == self.SMART_MARK:
                    qty = min(15, limit - position, tr.quantity)
                    if qty > 0:
                        result.setdefault(product, []).append(Order(product, int(best_ask), int(qty)))
                        position += qty
                elif tr.seller == self.SMART_MARK:
                    qty = min(15, limit + position, tr.quantity)
                    if qty > 0:
                        best_bid = max(depth.buy_orders.keys())
                        result.setdefault(product, []).append(Order(product, int(best_bid), -int(qty)))
                        position -= qty
        return result
    
    def strategy_vev_settlement_long(self, state, data, tte):
        """
        LONG all option strikes on days 1-2 when VE is rising.
        VE historically +20-28 ticks/day on days 1-2: options gain delta value.
        Take from ask for guaranteed fills, build max +300 fast.
        Flip to settlement_short on day 3 happens automatically via elapsed_days.
        """
        TARGETS = {
            5000: 300,
            5100: 300,
            5200: 300,
            5300: 300,
            5400: 300,
            5500: 300,
        }
        ENTRY_QTY = 30

        out = {}
        for K, target in TARGETS.items():
            voucher = "VEV_{}".format(K)
            v_depth = state.order_depths.get(voucher)
            if not v_depth or not v_depth.sell_orders:
                continue
            v_ask = min(v_depth.sell_orders.keys())
            v_pos = state.position.get(voucher, 0)
            v_lim = self.LIMITS.get(voucher, 300)
            remaining = target - v_pos
            if remaining <= 0:
                continue
            qty = min(remaining, v_lim - v_pos, ENTRY_QTY)
            if qty > 0:
                out[voucher] = [Order(voucher, int(v_ask), int(qty))]
        return out