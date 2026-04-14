# ROUND 1 CHECKLIST

## On round open
- Read full spec
- Confirm product names
- Confirm position limits
- Confirm tick sizes
- Verify sell_orders sign convention unchanged

## Product identification (Person B)
- Run analyze_product on downloaded data
- Identify stable product -> note fair value
- Identify volatile product(s) -> EMA
- Check data reuse against historical_data/

## Implementation (Person A)
- Update LIMITS dict with correct product names and limits
- Update product name strings in run() dispatcher
- Set FAIR_VALUE for stable product
- Set EMA_ALPHA for volatile product
- Run local backtester - confirm positive PnL
- Safety submission within 90 min of open

## Review
- Person B reviews trader.py before final submission
- No print statements
- All products handled (including previous rounds)
- Position limits respected
- traderData serialization working

## Optimization
- Parameter sweep (SPREAD, ALPHA, RETREAT)
- Second submission with tuned params

## Manual challenge (Person B)
- Read problem
- Run fx_arbitrage.py or expected_value.py as applicable
- Submit manual answer

## Final
- Final submission 2+ hours before deadline
- Both people confirm submission is live