# DATAMODEL NOTES - Verified from prosperity4bt source

## TradingState fields
- traderData: str (empty string "" on first tick, NOT None)
- timestamp: int
- listings: Dict[Symbol, Listing]
- order_depths: Dict[Symbol, OrderDepth]
- own_trades: Dict[Symbol, List[Trade]]
- market_trades: Dict[Symbol, List[Trade]]
- position: Dict[Product, Position]
- observations: Observation

## OrderDepth
- buy_orders: Dict[int, int] — volumes are POSITIVE
- sell_orders: Dict[int, int] — volumes are NEGATIVE (confirmed: runner sets sell_orders[price] = -volume)

## Order constructor
Order(symbol: str, price: int, quantity: int)
- price MUST be int (type_check_orders raises ValueError on float)
- quantity MUST be int
- quantity > 0 = buy, quantity < 0 = sell

## state.position
- Dict[Product, Position]
- Missing key = product not in dict
- Always use state.position.get(product, 0)

## run() return signature
(dict[Symbol, list[Order]], int, str) = (orders, conversions, trader_data)

## Position limit enforcement
- From prosperity4bt.data.LIMITS
- Tutorial: EMERALDS=80, TOMATOES=80
- If ANY order causes breach: ENTIRE product order list is dropped (not just the excess)

## traderData serialization
- Must return as str from run()
- Initial value is "" (empty string)
- Parse with: json.loads(state.traderData) if state.traderData else {}
