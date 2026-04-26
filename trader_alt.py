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


# ── Position budget + order placement ─────────────────────────────────────────

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
        "ASH_COATED_OSMIUM": 80,
        "INTARIAN_PEPPER_ROOT": 80,
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
    }

    # SWEEP PARAMS - do not rename these lines
    ASH_COATED_OSMIUM_SPREAD  = 6  # passive MM spread
    #INTARIAN_PEPPER_ROOT_ALPHA   = 0.15
    # INTARIAN_PEPPER_ROOT_SPREAD  = 4
    # INTARIAN_PEPPER_ROOT_RETREAT = 0.01
    ASH_COATED_OSMIUM_SELL_OFFSET = 0
    ASH_COATED_OSMIUM_WALL_WEIGHT = 0.9
    IPR_BID_OFFSET = 0

    ASH_COATED_OSMIUM_FAIR_VALUE = 10000
    ASH_TAKE_MARGIN = 3  # aggressive mean-revert take at 10000 +/- 3


    MAF_BID = 1500

    # R3 delta-1 MM params
    HYDROGEL_PACK_SPREAD       = 6
    HYDROGEL_PACK_SELL_OFFSET  = -1
    HYDROGEL_PACK_TAKE_MARGIN  = 10  # sweep-optimized: sym 33.9%/33.1% on live, fires at peak ts=68800

    VELVETFRUIT_EXTRACT_SPREAD      = 4
    VELVETFRUIT_EXTRACT_SELL_OFFSET = 0
    VELVETFRUIT_EXTRACT_TAKE_MARGIN = 7  # sweep-optimized: sym 10.3%/12.7% on live, cascade SAFE

    # EMA anchors: cold-start constants, updated each tick via slow EMA
    ANCHOR_HYDROGEL    = 9976  # sweep-optimized around live mean 9979
    ANCHOR_VE          = 5262  # calibrated to live day mean (confirmed from 375207+376559)
    DELTA1_EMA_ALPHA      = 0.00003  # half-life ~23K ticks (~2.3 days)
    HYDROGEL_RETREAT      = 6   # safe: bot spread=16, max bid-shift=6 < half-spread=8
    VE_RETREAT            = 2   # safe: VE spread min=1 tick; retreat=2 → bid=wm-2+2=wm, never crosses ask

    # VEV params kept for future passive-MM implementation; NOT dispatched this version
    VEV_STRIKES              = [5000, 5100, 5200, 5300, 5400, 5500]
    VEV_THRESHOLDS           = {5000: 0.009, 5100: 0.004, 5200: 0.002,
                                5300: 0.002, 5400: 0.002, 5500: 0.003}
    VEV_POS_CAP              = 25
    VEV_IV_WINDOW            = 50
    VEV_TREND_GUARD_K        = 5400
    VEV_TREND_GUARD_THRESH   = 0.01
    VEV_HEDGE_DELTA_THRESH   = 20.0
    VEV_HEDGE_VE_BUDGET      = 30

    def bid(self):
        return self.MAF_BID

    # TTE (time to expiry) schedule: end-of-day values in years
    _TTE_END = {0: 8.0 / 365, 1: 7.0 / 365, 2: 6.0 / 365}

    def run(self, state: TradingState):
        result = {}
        conversions = 0

        data = (json.loads(state.traderData) if state.traderData else None) or {}

        if state.observations:
            data["obs"] = str(state.observations)[:200]

        if "ASH_COATED_OSMIUM" in state.order_depths:
            result["ASH_COATED_OSMIUM"] = self.strategy_stable("ASH_COATED_OSMIUM", state, data)

        if "INTARIAN_PEPPER_ROOT" in state.order_depths:
            result["INTARIAN_PEPPER_ROOT"] = self.strategy_ipr("INTARIAN_PEPPER_ROOT", state, data)

        if "HYDROGEL_PACK" in state.order_depths:
            result["HYDROGEL_PACK"] = self.strategy_delta1(
                "HYDROGEL_PACK", state, data,
                spread=self.HYDROGEL_PACK_SPREAD,
                sell_offset=self.HYDROGEL_PACK_SELL_OFFSET,
                take_margin=self.HYDROGEL_PACK_TAKE_MARGIN,
                anchor_init=self.ANCHOR_HYDROGEL,
                ema_alpha=self.DELTA1_EMA_ALPHA,
                retreat=self.HYDROGEL_RETREAT,
            )

        if "VELVETFRUIT_EXTRACT" in state.order_depths:
            result["VELVETFRUIT_EXTRACT"] = self.strategy_delta1(
                "VELVETFRUIT_EXTRACT", state, data,
                spread=self.VELVETFRUIT_EXTRACT_SPREAD,
                sell_offset=self.VELVETFRUIT_EXTRACT_SELL_OFFSET,
                take_margin=self.VELVETFRUIT_EXTRACT_TAKE_MARGIN,
                anchor_init=self.ANCHOR_VE,
                ema_alpha=self.DELTA1_EMA_ALPHA,
                retreat=self.VE_RETREAT,
            )

        vev_mm_orders = self.strategy_vev_intrinsic_mm(state, data)
        for k, v in vev_mm_orders.items():
            result[k] = v

        # settlement short: enable manually when taking the OTM expiry bet
        # vev_short_orders = self.strategy_vev_settlement_short(state, data)
        # for k, v in vev_short_orders.items():
        #     result[k] = v

        traderData = json.dumps(data)
        return result, conversions, traderData

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
            # Bid at mid + 2 (inside spread, well above natural bid)
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
        
        # Phase 1c: additional take based on passive_fair (original behavior, catches short-term dislocations)
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

    def strategy_delta1(self, product, state, data, *, spread, sell_offset, take_margin,
                        anchor_init, ema_alpha=0.001, retreat=0):
        """
        Delta-1 MM with EMA-anchor split-FV + inventory-aversion (retreat).
          take_fair    = EMA anchor (slow mean, cold-starts at anchor_init) — Phase 1 signal
          passive_fair = wall_mid_blend — Phase 2 quote center
          retreat      = inventory aversion coefficient; shifts Phase 2 quotes toward exit
        At retreat=6, position=+limit: ask = wm-2 (aggressively attracts sellers to exit long).
        Signs: sell_orders values NEGATIVE; Order qty positive=buy, negative=sell.
        """
        depth = state.order_depths[product]
        init_product_data(data, product, {"last_wm": None, "anchor": anchor_init})

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

        data[product]["anchor"] = (1 - ema_alpha) * data[product]["anchor"] + ema_alpha * wm

        take_fair    = data[product]["anchor"]
        passive_fair = wm

        buy_budget  = limit - position
        sell_budget = limit + position
        orders = []

        # Phase 1a: take asks below take_fair - take_margin (mean-revert buy)
        for price in sorted(depth.sell_orders.keys()):
            if price <= take_fair - take_margin and buy_budget > 0:
                available = -depth.sell_orders[price]
                qty = min(available, buy_budget)
                if qty > 0:
                    orders.append(Order(product, int(price), int(qty)))
                    buy_budget -= qty

        # Phase 1b: take bids above take_fair + take_margin + sell_offset (mean-revert sell)
        for price in sorted(depth.buy_orders.keys(), reverse=True):
            if price >= take_fair + take_margin + sell_offset and sell_budget > 0:
                available = depth.buy_orders[price]
                qty = min(available, sell_budget)
                if qty > 0:
                    orders.append(Order(product, int(price), -int(qty)))
                    sell_budget -= qty

        # Phase 2: inventory-aversion passive quotes
        # inv_adjust > 0 when long: shifts quotes DOWN (lower ask = easier to exit long)
        # inv_adjust < 0 when short: shifts quotes UP (higher bid = easier to exit short)
        inv_adjust = retreat * position / limit if limit > 0 else 0
        adjusted_fair = passive_fair - inv_adjust
        bid_price = int(math.floor(adjusted_fair - spread))
        ask_price = int(math.ceil(adjusted_fair + spread + sell_offset))
        if buy_budget > 0:
            orders.append(Order(product, bid_price, int(buy_budget)))
        if sell_budget > 0:
            orders.append(Order(product, ask_price, -int(sell_budget)))

        return orders

    def strategy_vev_batch(self, state, data, tte):
        """
        IV mean-reversion across 6 ATM strikes (5000-5500) with net-delta hedge via VE.
        Returns {voucher: [orders], "__ve_hedge__": [orders]} where present.
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
        net_delta_new = 0.0  # delta contribution from orders placed this tick

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

            # K=5400: skip when IV has trended > 1% over last 50 samples
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
                    qty = min(can_sell, 5)
                    result[voucher] = [Order(voucher, int(v_bid), -int(qty))]
                    net_delta_new -= delta * qty  # short call = short delta

            elif iv < mean_iv - threshold:
                # IV depressed: buy voucher (long vega)
                can_buy = min(cap - v_pos, lim - v_pos)
                if can_buy > 0:
                    qty = min(can_buy, 5)
                    result[voucher] = [Order(voucher, int(v_ask), int(qty))]
                    net_delta_new += delta * qty  # long call = long delta

        # Net-delta hedge via VE when threshold crossed and spread acceptable
        if abs(net_delta_new) > 0 and ve_half_spread <= 3.0:
            # Existing VEV portfolio delta
            existing_delta = 0.0
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

            total_delta = existing_delta + net_delta_new
            if abs(total_delta) > self.VEV_HEDGE_DELTA_THRESH:
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

    def strategy_vev_intrinsic_mm(self, state, data):
        """
        Passive MM on deep-ITM and near-money VEV strikes whose fair value is
        near-intrinsic. We quote 1 tick inside the visible book on each side,
        capturing the bot spread without computing IV or crossing.
        Signs: sell_orders values NEGATIVE; Order qty positive=buy, negative=sell.
        """
        ve_depth = state.order_depths.get("VELVETFRUIT_EXTRACT")
        if not ve_depth or not ve_depth.buy_orders or not ve_depth.sell_orders:
            return {}
        ve_mid = (max(ve_depth.buy_orders.keys()) + min(ve_depth.sell_orders.keys())) / 2.0

        ITM_STRIKES      = [4000, 4500, 5000, 5100, 5200]
        POS_CAP          = 100   # conservative; lift to 200-300 after live confirmation
        QUOTE_QTY        = 30    # per side per tick; < typical bot top-vol (~10-22 visible)
        MIN_SPREAD_TICKS = 2     # VEV_5200 avg spread ~3; include it

        out = {}
        for K in ITM_STRIKES:
            voucher = "VEV_{}".format(K)
            v_depth = state.order_depths.get(voucher)
            if not v_depth or not v_depth.buy_orders or not v_depth.sell_orders:
                continue
            v_bid = max(v_depth.buy_orders.keys())
            v_ask = min(v_depth.sell_orders.keys())
            if v_ask - v_bid < MIN_SPREAD_TICKS:
                continue

            # Use observed mid as fair (incorporates extrinsic automatically)
            fair = (v_bid + v_ask) / 2.0

            v_pos = state.position.get(voucher, 0)
            v_lim = self.LIMITS.get(voucher, 300)
            cap   = POS_CAP

            buy_budget  = min(cap - v_pos, v_lim - v_pos)
            sell_budget = min(cap + v_pos, v_lim + v_pos)

            bid_price = int(v_bid + 1)
            ask_price = int(v_ask - 1)
            if bid_price >= ask_price:
                continue

            intrinsic = max(ve_mid - K, 0.0)
            if ask_price <= intrinsic:
                sell_budget = 0
            if K in [4000, 4500] and bid_price >= intrinsic + 50:
                buy_budget = 0

            orders = []
            if buy_budget > 0:
                orders.append(Order(voucher, bid_price,  int(min(QUOTE_QTY, buy_budget))))
            if sell_budget > 0:
                orders.append(Order(voucher, ask_price, -int(min(QUOTE_QTY, sell_budget))))
            if orders:
                out[voucher] = orders

        return out

    def strategy_vev_settlement_short(self, state, data):
        """
        Short OTM VEV strikes 5300/5400/5500 at the current ask (passive).
        Rationale: these trade at 41-57/12-19/4-8 ticks but Asian settlement
        is max(avg(VE)-K, 0) ≈ 0 when VE avg ~5262 << all three strikes.
        We post passive sells at the bot ask level; fills accumulate over days.
        SHORT_CAP=100 per strike (conservative; 300 is max).
        """
        OTM_STRIKES = [5300, 5400, 5500]
        SHORT_CAP   = 100
        MIN_BID     = 2   # minimum bid price to bother (ignore near-zero options)
        ENTRY_QTY   = 15  # units per tick (paced entry)

        out = {}
        for K in OTM_STRIKES:
            voucher = "VEV_{}".format(K)
            v_depth = state.order_depths.get(voucher)
            if not v_depth or not v_depth.buy_orders or not v_depth.sell_orders:
                continue

            v_bid = max(v_depth.buy_orders.keys())
            if v_bid < MIN_BID:
                continue

            v_ask   = min(v_depth.sell_orders.keys())
            v_pos   = state.position.get(voucher, 0)
            v_lim   = self.LIMITS.get(voucher, 300)
            can_short = min(SHORT_CAP + v_pos, v_lim + v_pos)
            if can_short <= 0:
                continue

            qty = min(can_short, ENTRY_QTY)
            if qty > 0:
                # Post passive sell AT the current best ask: captures buyers
                # without crossing the spread (no taker cost)
                out[voucher] = [Order(voucher, int(v_ask), -int(qty))]

        return out

    def strategy_ema(self, product, state, data):
        init_product_data(data, product, {"ema": None})

        order_depth = state.order_depths[product]
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return []

        position = state.position.get(product, 0)
        limit = self.LIMITS.get(product)
        if limit is None:
            return []

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2

        if data[product]["ema"] is None:
            data[product]["ema"] = mid
        else:
            data[product]["ema"] = self.INTARIAN_PEPPER_ROOT_ALPHA * mid + (1 - self.INTARIAN_PEPPER_ROOT_ALPHA) * data[product]["ema"]

        return compute_orders_with_budget(
            product, order_depth, data[product]["ema"], position, limit,
            spread=self.INTARIAN_PEPPER_ROOT_SPREAD, retreat=self.INTARIAN_PEPPER_ROOT_RETREAT
        )

    def strategy_basket(self, basket_product, state, data):
        # BUG 1 FIX: was at module level. Now correctly inside Trader class.
        COMPONENTS  = {}   # fill in Round 2 when product specs are known
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

    def strategy_option(self, voucher, underlying, strike, tte_years, state, data):
        IV_WINDOW          = 50
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
                delta     = bs_delta(S, strike, tte_years, 0, iv)
                # BUG 3 FIX: max(0, ...) prevents negative hedge_qty if u_position >= u_limit
                hedge_qty = max(0, min(round(delta * qty), u_limit - u_position))
                if hedge_qty > 0:
                    best_ask = min(u_depth.sell_orders.keys())
                    underlying_orders.append(Order(underlying, int(best_ask), int(hedge_qty)))

        elif iv < mean_iv - IV_ENTRY_THRESHOLD:
            buy_budget = v_limit - v_position
            if buy_budget > 0:
                best_ask = min(v_depth.sell_orders.keys())
                qty = min(buy_budget, 5)
                voucher_orders.append(Order(voucher, int(best_ask), int(qty)))
                delta     = bs_delta(S, strike, tte_years, 0, iv)
                # BUG 3 FIX: max(0, ...) prevents negative hedge_qty if u_position <= -u_limit
                hedge_qty = max(0, min(round(delta * qty), u_limit + u_position))
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
                avg_buy  = stats["buy_value"] / stats["buy_count"]
                avg_sell = stats["sell_value"] / stats["sell_count"]
                edge     = avg_sell - avg_buy
                if edge > 0:
                    results.append((name, edge))
        return sorted(results, key=lambda x: -x[1])