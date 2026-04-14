# DAILY WORK SPLIT: APRIL 11-14

**Today is April 11 (Saturday). Round 1 opens April 14.**
**Person A (you):** Stronger Python, HFT/LOB background, more domain knowledge
**Person B (teammate):** Less Python experience, learning the domain

---

## DAY 1: APRIL 11 (SATURDAY) - TOOLING & FOUNDATION

### Morning Session (both together, ~2 hours)

**Both:**
- [ ] Create the private Git repo
- [ ] Set up MS Teams channel
- [ ] `pip install prosperity4btx` on both machines
- [ ] Both read this playbook's 01_MASTERPLAN.md together (30 min)
- [ ] Person A walks Person B through the Trader class skeleton and explains TradingState, OrderDepth, Order

**Deliverable:** Both people can explain what `run()` receives and returns.

---

### Person A: April 11 Afternoon (~4-5 hours)

**Task 1: Inspect the P4 datamodel (30 min)**
```bash
pip install prosperity4btx
python3 -c "import prosperity4btx; help(prosperity4btx)"
# Or find the package location and read datamodel.py directly:
pip show prosperity4btx
```

Write down and commit to the repo a file `DATAMODEL_NOTES.md`:
- [ ] Exact fields on `TradingState` (position, order_depths, market_trades, traderData, observations, etc.)
- [ ] Are `sell_orders` volumes negative or positive?
- [ ] Exact `Order` constructor: `Order(symbol, price, quantity)` - verify argument order
- [ ] What does `state.position` return when you have no position? (`0` or missing key?)
- [ ] Does `run()` return `(result, conversions, traderData)` or different?

**Deliverable:** `DATAMODEL_NOTES.md` committed. All sign conventions confirmed.

**Task 2: Build the working Trader skeleton (1 hour)**
- [ ] Create `trader.py` with the skeleton from 02_CODE_TEMPLATES.md Section 1
- [ ] Add `norm_cdf`, `norm_pdf` (Section 2)
- [ ] Add `init_product_data`, `append_capped` (Section 3)
- [ ] Add `compute_orders_with_budget` (Section 4) - adjust sign convention based on Task 1 findings
- [ ] Add tick-size rounding using correct tick from tutorial spec

**Deliverable:** `trader.py` committed. Contains skeleton + utilities. Not yet functional.

**Task 3: Implement stable product market maker (1 hour)**
- [ ] Add `strategy_stable` (Section 5)
- [ ] Wire it into `run()` for the tutorial round's stable product
- [ ] Fill in `LIMITS` dict from tutorial spec
- [ ] Set `FAIR_VALUE` based on tutorial product price

**Deliverable:** `trader.py` handles the stable tutorial product.

**Task 4: Test submission on tutorial round (30 min)**
- [ ] Submit to the Prosperity platform
- [ ] Verify it runs without errors
- [ ] Check: does it produce positive PnL?
- [ ] If errors: fix, re-submit, until clean

**Deliverable:** Screenshot or log of a successful tutorial submission with positive PnL. Share in Teams.

**Task 5: Implement EMA volatile product market maker (1 hour)**
- [ ] Add `strategy_ema` (Section 6)
- [ ] Wire into `run()` for the tutorial's volatile product
- [ ] Add `compute_wall_mid` (Section 7) as a utility, even if not used yet
- [ ] Re-submit to tutorial. Verify both products now trade.

**Deliverable:** `trader.py` handles both tutorial products. Committed and submitted.

---

### Person B: April 11 Afternoon (~4-5 hours)

**Task 1: Clone all Tier 1 repos (30 min)**
```bash
mkdir ~/prosperity-reference && cd ~/prosperity-reference

git clone https://github.com/TimoDiehm/imc-prosperity-3.git
git clone https://github.com/chrispyroberts/imc-prosperity-3.git
git clone https://github.com/ericcccsliu/imc-prosperity-2.git
git clone https://github.com/ShubhamAnandJain/IMC-Prosperity-2023-Stanford-Cardinal.git
git clone https://github.com/CarterT27/imc-prosperity-3.git
git clone https://github.com/pe049395/IMC-Prosperity-2024.git
```

**Deliverable:** All 6 repos cloned locally. Confirm in Teams.

**Task 2: Read the Frankfurt Hedgehogs writeup (1.5 hours)**

Read `imc-prosperity-3/README.md` (TimoDiehm). This is the single most important document.

Take notes in a file `REFERENCE_NOTES.md` answering:
- [ ] What is "wall mid" and when did they use it?
- [ ] What strategies did they use per product?
- [ ] What was the "hardcoding exploit" they found?
- [ ] What was their fallback system?
- [ ] What parameters did they use for basket arb (z-score thresholds)?
- [ ] What did they say about options pricing?

**Deliverable:** `REFERENCE_NOTES.md` committed. Key insights extracted.

**Task 3: Read the CMU Physics writeup (1 hour)**

Read `imc-prosperity-3/README.md` (chrispyroberts).

Add to `REFERENCE_NOTES.md`:
- [ ] What went wrong with their options model?
- [ ] What strategies worked per product?
- [ ] What did they say about Squid Ink?
- [ ] What was their code structure?

**Deliverable:** `REFERENCE_NOTES.md` updated with CMU insights.

**Task 4: Extract historical price data (1.5 hours)**

From each cloned repo, find the price data (CSV files, backtest logs, or hardcoded arrays in the code). Create:

```
historical_data/
    p1/
        pearls.csv      (or .json or raw values)
        bananas.csv
        coconuts.csv
        pina_coladas.csv
    p2/
        amethysts.csv
        starfruit.csv
        orchids.csv
        chocolate.csv
        strawberries.csv
        roses.csv
        gift_basket.csv
        coconut.csv
        coconut_coupon.csv
    p3/
        rainforest_resin.csv
        kelp.csv
        squid_ink.csv
        croissants.csv
        jams.csv
        djembes.csv
        picnic_basket1.csv
        picnic_basket2.csv
        volcanic_rock.csv
```

Not every file will exist. Extract what you can find. Even partial data (a few hundred mid prices) is useful for correlation checking.

**Deliverable:** `historical_data/` folder committed with whatever price series are extractable.

---

### Day 1 Evening Sync (both together, 30 min)

- [ ] Person A demos the working tutorial submission
- [ ] Person B shares key insights from writeup reading
- [ ] Both review `DATAMODEL_NOTES.md` together
- [ ] Person A walks Person B through `compute_orders_with_budget` logic
- [ ] Agree on Day 2 plan

---

## DAY 2: APRIL 12 (SUNDAY) - STRATEGY TEMPLATES

### Person A: April 12 (~5-6 hours)

**Task 1: Implement basket arbitrage template (1.5 hours)**
- [ ] Add `strategy_basket` from Section 8 of CODE_TEMPLATES
- [ ] Cannot test on tutorial (no basket products yet), but verify it compiles
- [ ] Write a standalone test: create mock order depths, verify z-score computation produces correct values
- [ ] Verify position budget logic works within the basket strategy

```python
# Quick self-test (run outside Trader class)
history = [50.0] * 30 + [55.0]  # spread jumps
mean_s = sum(history) / len(history)
var_s = sum((x - mean_s) ** 2 for x in history) / len(history)
import math
std_s = math.sqrt(var_s) if var_s > 0 else 1
z = (55.0 - mean_s) / std_s
print(f"z-score: {z:.2f}")  # should be positive, >2
```

**Deliverable:** `strategy_basket` in `trader.py`. Self-test passes.

**Task 2: Implement Black-Scholes + options strategy (2 hours)**
- [ ] Add `bs_call_price`, `bs_delta`, `bs_vega`, `implied_vol` from Section 9
- [ ] Add `strategy_option` from Section 9 (with integration warning)
- [ ] Write self-tests:

```python
# Verify B-S
price = bs_call_price(10000, 10000, 0.5, 0, 0.16)
iv = implied_vol(price, 10000, 10000, 0.5, 0)
assert abs(iv - 0.16) < 0.001, f"IV roundtrip failed: {iv}"

# Verify delta makes sense
d = bs_delta(10000, 10000, 0.5, 0, 0.16)
assert 0.4 < d < 0.6, f"ATM delta out of range: {d}"
print("All options tests pass")
```

**Deliverable:** Options strategy in `trader.py`. Self-tests pass.

**Task 3: Implement bot tracker (45 min)**
- [ ] Add `track_bots` and `get_profitable_bots` from Section 10
- [ ] Cannot test until Round 5 but verify it compiles and handles empty market_trades

**Deliverable:** Bot tracker in `trader.py`.

**Task 4: Stress test state serialization (45 min)**
- [ ] Simulate 15 products, each with 200-element price history
- [ ] Serialize with `json.dumps`, measure string length
- [ ] If > 50KB, identify what to trim (use running EMA instead of raw lists)

```python
import json
data = {}
for i in range(15):
    data[f"PRODUCT_{i}"] = {
        "ema": 10000.0,
        "prices": [round(10000 + j * 0.01, 2) for j in range(200)],
        "spread_history": [round(50 + j * 0.01, 2) for j in range(100)],
        "iv_history": [round(0.16 + j * 0.0001, 6) for j in range(50)],
    }
s = json.dumps(data)
print(f"State size: {len(s)} bytes = {len(s)/1024:.1f} KB")
```

Target: under 100KB. If over, reduce history lengths.

**Deliverable:** State size verified. History lengths adjusted if needed.

**Task 5: Backtest parameter sweep on tutorial products (1 hour)**
- [ ] Run the backtester with different SPREAD values for stable product: [1, 2, 3, 4]
- [ ] Run with different EMA_ALPHA values for volatile product: [0.05, 0.1, 0.2, 0.3]
- [ ] Record PnL for each combination
- [ ] Select best parameters for tutorial round

**Deliverable:** Parameter sweep results documented (a simple table in a commit message or `TUNING_LOG.md`).

---

### Person B: April 12 (~5-6 hours)

**Task 1: Read Linear Utility P2 writeup (1 hour)**

Read `imc-prosperity-2/README.md` (ericcccsliu).

Add to `REFERENCE_NOTES.md`:
- [ ] How did they detect data reuse from P1?
- [ ] What was their backtester design?
- [ ] What parameters did they use for options (coconut coupon)?
- [ ] What did they say about position management and zero-EV trades?

**Deliverable:** `REFERENCE_NOTES.md` updated.

**Task 2: Read Stanford Cardinal P1 writeup (45 min)**

Read `IMC-Prosperity-2023-Stanford-Cardinal/README.md`.

Add to `REFERENCE_NOTES.md`:
- [ ] What strategy for Bananas (trending product)?
- [ ] What strategy for Berries (seasonal product)?
- [ ] How did they approach Diving Gear + Dolphin Sightings?
- [ ] What was their Picnic Basket approach?

**Deliverable:** `REFERENCE_NOTES.md` updated.

**Task 3: Build the data reuse detection notebook (1 hour)**
- [ ] Create `notebooks/data_reuse_check.ipynb`
- [ ] Load all historical price data from `historical_data/`
- [ ] Implement `check_data_reuse` from Section 11
- [ ] Test it: correlate P3 kelp prices with P2 starfruit (should be low correlation)
- [ ] Verify it would catch a reuse (correlate a series with itself, shuffled slightly)

**Deliverable:** Working notebook. Committed.

**Task 4: Build the new-round analysis notebook (1.5 hours)**
- [ ] Create `notebooks/round_analysis.ipynb`
- [ ] Implement `analyze_product` and `check_correlations` from Section 13
- [ ] Test on tutorial data: characterize both tutorial products
- [ ] Add a section for basket weight discovery (brute-force integer weights 1-10)
- [ ] Add a section for seasonality detection (plot price by time-of-day)

**Deliverable:** Working notebook that can analyze any round's data in <30 min. Committed.

**Task 5: Pre-code manual challenge tools (1 hour)**
- [ ] Create `manual/fx_arbitrage.py` with `find_fx_arbitrage` from Section 12
- [ ] Test with the example: USD->EUR->GBP->USD at 0.9, 0.8, 1.5 (expect 1.08x)
- [ ] Create `manual/expected_value.py` with a simple function:

```python
def best_choice(options):
    """
    options: list of {"name": str, "outcomes": [(probability, payoff), ...]}
    Returns the option with highest expected value.
    """
    best = None
    best_ev = float('-inf')
    for opt in options:
        ev = sum(p * v for p, v in opt["outcomes"])
        if ev > best_ev:
            best_ev = ev
            best = opt["name"]
    return best, best_ev
```

**Deliverable:** `manual/fx_arbitrage.py` and `manual/expected_value.py` committed and tested.

---

### Day 2 Evening Sync (both together, 1 hour)

- [ ] Person A walks Person B through ALL code in `trader.py` line by line
- [ ] Person B asks questions until they understand every function
- [ ] Person B shares insights from P1/P2 writeups
- [ ] Both review the analysis notebook together on tutorial data
- [ ] Discuss: which reference team's approach do we like best?
- [ ] Plan Day 3

**Deliverable by end of Day 2:**
Complete `trader.py` with all strategy templates. Both people understand all the code. Analysis tooling ready. Manual challenge tools ready.

---

## DAY 3: APRIL 13 (MONDAY) - REHEARSAL & POLISH

**NOTE: This is a weekday. If you have classes/work, do the morning rehearsal before or shift it to the evening. The afternoon tasks can be done independently and asynchronously. The critical deliverable is: rehearsal done, code reviewed, repo clean before bed.**

### Morning Session (both together, 2-3 hours): FULL DRESS REHEARSAL

**Simulate Round 1 morning.** Start a timer.

1. **Minute 0:** Person A opens the tutorial spec. Person B opens the analysis notebook.
2. **Minute 0-15:** Person A reads spec, confirms position limits and data formats haven't changed. Person B loads tutorial data into notebook, runs `analyze_product` on each product.
3. **Minute 15-30:** Sync. Person B reports: "Product X is stable at ~Y, Product Z is volatile with autocorrelation W." Person A confirms which template to use.
4. **Minute 30-90:** Person A wires the correct strategies into `run()`, sets parameters. Person B runs parameter sweep in notebook.
5. **Minute 90-120:** Person A submits. Person B reviews the submitted code.
6. **Minute 120-150:** Check results. If PnL is negative, diagnose. If positive, tune parameters.

**Record the time at each step.** Target: first submission under 90 minutes from "go."

**Deliverable:** Rehearsal complete. Both people know the exact workflow for Round 1.

---

### Person A: April 13 Afternoon (~2-3 hours)

**Task 1: Code review and hardening (1 hour)**
- [ ] Read every line of `trader.py` fresh. Look for:
  - Any function that modifies `data` but doesn't use `init_product_data` first
  - Any place where position budget could go negative
  - Any division by zero risk (especially std_spread = 0)
  - Any missing `return []` for empty order book cases
- [ ] Add defensive checks where missing:

```python
# Every strategy function should start with:
if product not in state.order_depths:
    return []
order_depth = state.order_depths[product]
if not order_depth.buy_orders or not order_depth.sell_orders:
    return []
```

**Deliverable:** Hardened `trader.py`. All edge cases handled.

**Task 2: Prepare Round 1 rapid-deployment checklist (30 min)**

Create `ROUND1_CHECKLIST.md`:
```
[ ] Read spec
[ ] Confirm product names and position limits
[ ] Update LIMITS dict in trader.py
[ ] Identify which product is stable, which is volatile
[ ] Set FAIR_VALUE for stable product
[ ] Set EMA_ALPHA for volatile product
[ ] Run backtester locally
[ ] First submission
[ ] Person B reviews code
[ ] Parameter sweep
[ ] Final submission
[ ] Manual challenge
```

**Deliverable:** `ROUND1_CHECKLIST.md` committed.

**Task 3: Test failure modes (1 hour)**
- [ ] What happens if `state.traderData` is `None`? (first timestep)
- [ ] What happens if `state.traderData` is `""`? (empty string)
- [ ] What happens if a product appears in `order_depths` but not in `LIMITS`?
- [ ] What happens if `state.position` doesn't have a key for a product?
- [ ] What happens if `order_depth.buy_orders` is empty but `sell_orders` is not?

For each: verify the code handles it gracefully (returns empty orders, doesn't crash).

**Deliverable:** All 5 failure modes tested and confirmed handled.

---

### Person B: April 13 Afternoon (~2-3 hours)

**Task 1: Complete the reference notes (1 hour)**
- [ ] Skim the Alpha Animals writeup (CarterT27) for any P3-specific insights not covered
- [ ] Read 1-2 Medium blog posts (David Teather or Shriyan Gosavi)
- [ ] Final update to `REFERENCE_NOTES.md` with a summary section: "Top 5 things to remember"

**Deliverable:** Final `REFERENCE_NOTES.md` with summary.

**Task 2: Prepare the data reuse pipeline for instant execution (1 hour)**
- [ ] Verify the notebook can load all historical data in under 30 seconds
- [ ] Add a cell that takes a list of new prices as input and runs correlation against everything
- [ ] Test: if you paste in 200 numbers, does it produce results within 10 seconds?
- [ ] Pre-write the cell headers so on Round 1 day, Person B just pastes data and hits Run

**Deliverable:** Notebook ready for instant use on Round 1.

**Task 3: Review Person A's complete trader.py (1 hour)**

**TIMING: Do this AFTER Person A finishes Task 1 (hardening) and pushes to Git.** Do Tasks 1-2 first, then pull Person A's latest code for review.

- [ ] Pull latest `trader.py` from Git
- [ ] Read every line
- [ ] For each strategy function, verify:
  - Position budget is correctly computed (buy_budget = limit - position, sell_budget = limit + position)
  - Orders use negative quantities for sells, positive for buys
  - State is initialized with `init_product_data` before use
  - Lists are capped with `append_capped`
  - Return type is `list[Order]`
- [ ] Note any questions or concerns. Discuss with Person A.

**Deliverable:** Code review complete. Any issues fixed.

---

### Day 3 Evening (both, 30 min)

- [ ] Final sync: any open issues?
- [ ] Confirm both people can access the Prosperity platform and submit
- [ ] Confirm both people have the backtester installed and working
- [ ] Confirm Git repo is clean and up to date
- [ ] Set alarm for Round 1 opening time
- [ ] Go to sleep early

---

## DAY 4: APRIL 14 (TUESDAY) - ROUND 1 OPENS

**NOTE: This is a weekday. Round 1 is 72 hours, so you have until Thursday April 17 to submit. You do NOT need to rush everything on Tuesday. But getting the safety submission done on Day 1 (even if it's after classes/work) means you can iterate for the remaining 2 days. Check the exact opening time at prosperity.imc.com.**

### Hour 0: Round Opens

**Both together.** Open the spec. Start the timer.

**Person A (0-15 min):**
- [ ] Read the full spec
- [ ] Write down: product names, position limits, tick sizes
- [ ] Check: does the datamodel match our `DATAMODEL_NOTES.md`? Any surprises?
- [ ] Update `LIMITS` dict in `trader.py`

**Person B (0-15 min):**
- [ ] Download Round 1 data (if backtester data is available)
- [ ] Open `round_analysis.ipynb`
- [ ] Load new product prices
- [ ] Run `analyze_product` on each new product

### Minute 15-30: Sync

- [ ] Person B reports product characterizations: "Product X is stable at ~Y" / "Product Z is volatile"
- [ ] Person A confirms strategy assignments:
  - Stable product -> `strategy_stable`, set FAIR_VALUE
  - Volatile product -> `strategy_ema`, initial EMA_ALPHA = 0.1
  - If 3rd product exists -> decide (EMA with wide spread if unclear)
- [ ] Person B starts data reuse check against historical data

### Minute 30-90: Person A implements

- [ ] Wire strategies into `run()` dispatcher
- [ ] Set all product-specific parameters (FAIR_VALUE, SPREAD, EMA_ALPHA, RETREAT)
- [ ] Run local backtester
- [ ] If backtester PnL is positive: proceed to submission
- [ ] If negative: check position budget logic, check sign conventions

### Minute 90: First safety submission

- [ ] Person A submits `trader.py`
- [ ] Person B reviews the submitted code (while waiting for results)

### Minute 90-180: Optimize

- [ ] Person B runs parameter sweeps in notebook:
  - Stable SPREAD: [1, 2, 3]
  - Volatile EMA_ALPHA: [0.05, 0.1, 0.15, 0.2]
  - Volatile SPREAD: [2, 3, 4, 5]
  - Volatile RETREAT: [0.005, 0.01, 0.02]
- [ ] Person A implements best parameters from sweep
- [ ] Second submission with tuned parameters

### Hour 3-6: Further optimization + manual challenge

**Person A:**
- [ ] Check submission results (if available yet)
- [ ] If any product is losing money: widen spread or disable it
- [ ] Try wall-mid for the stable product (compare backtest PnL vs hardcoded fair value)
- [ ] Third submission if meaningful improvement found

**Person B:**
- [ ] Read the manual challenge problem
- [ ] If FX arbitrage: run `manual/fx_arbitrage.py` with the given rates
- [ ] If game theory: compute expected values for each option
- [ ] Submit manual challenge answer
- [ ] Report data reuse check results (any correlations > 0.85?)

### Hour 6+: Polish

- [ ] Both review final submission together
- [ ] Verify all products are handled
- [ ] Verify no print statements that could cause issues in later rounds
- [ ] Final submission 2+ hours before Round 1 deadline
- [ ] Celebrate or debug depending on leaderboard position

---

## DELIVERABLES SUMMARY

### End of Day 1 (April 11)

| Item | Owner | Status |
|---|---|---|
| Git repo created | Both | [ ] |
| MS Teams channel set up | Both | [ ] |
| `prosperity4btx` installed on both machines | Both | [ ] |
| `DATAMODEL_NOTES.md` with verified conventions | Person A | [ ] |
| `trader.py` skeleton + utilities + stable MM + EMA MM | Person A | [ ] |
| Successful tutorial submission with positive PnL | Person A | [ ] |
| 6 reference repos cloned | Person B | [ ] |
| `REFERENCE_NOTES.md` with Frankfurt + CMU insights | Person B | [ ] |
| `historical_data/` folder with extracted price series | Person B | [ ] |

### End of Day 2 (April 12)

| Item | Owner | Status |
|---|---|---|
| Basket arb strategy in `trader.py` (self-tested) | Person A | [ ] |
| Options strategy in `trader.py` (B-S + IV solver, self-tested) | Person A | [ ] |
| Bot tracker in `trader.py` | Person A | [ ] |
| State serialization stress-tested (<100KB at 15 products) | Person A | [ ] |
| Tutorial parameter sweep results documented | Person A | [ ] |
| `REFERENCE_NOTES.md` updated with P1/P2 insights | Person B | [ ] |
| `notebooks/data_reuse_check.ipynb` working | Person B | [ ] |
| `notebooks/round_analysis.ipynb` working on tutorial data | Person B | [ ] |
| `manual/fx_arbitrage.py` tested | Person B | [ ] |
| `manual/expected_value.py` tested | Person B | [ ] |
| Both people understand ALL code in `trader.py` | Both | [ ] |

### End of Day 3 (April 13)

| Item | Owner | Status |
|---|---|---|
| Dress rehearsal completed, time-to-first-submission < 90 min | Both | [ ] |
| `trader.py` hardened (all edge cases handled) | Person A | [ ] |
| `ROUND1_CHECKLIST.md` committed | Person A | [ ] |
| 5 failure modes tested and confirmed handled | Person A | [ ] |
| `REFERENCE_NOTES.md` finalized with "Top 5" summary | Person B | [ ] |
| Data reuse notebook ready for instant use | Person B | [ ] |
| Full code review of `trader.py` by Person B completed | Person B | [ ] |
| Git repo clean, all files committed and pushed | Both | [ ] |

### End of Day 4 (April 14) - Round 1

| Item | Owner | Status |
|---|---|---|
| Safety submission within 90 minutes of round opening | Person A | [ ] |
| Tuned submission within 3 hours | Person A | [ ] |
| Manual challenge submitted | Person B | [ ] |
| Data reuse check completed | Person B | [ ] |
| Code reviewed by Person B before final submission | Person B | [ ] |
| Final submission 2+ hours before deadline | Both | [ ] |

---

## IF THINGS GO WRONG

**"The backtester won't install"**
- Check Python version (need 3.10+)
- Try `pip install prosperity4btx --upgrade`
- If still broken: submit directly to the platform and use their results as your "backtester" (slower iteration but works)

**"Tutorial submission returns errors"**
- Check import: `from datamodel import ...` not `from prosperity4btx import ...`
- Check return type: must be `(dict[str, list[Order]], int, str)`
- Check that `traderData` is a string, not a dict
- Print the error in the submission log

**"We can't find historical price data in the repos"**
- Some repos store data in backtest log format, not CSV
- Check for `.json` files, hardcoded arrays in Python files, or Jupyter notebook outputs
- At minimum, extract the hardcoded fair values and parameter settings from their code

**"Person B can't understand the code"**
- Person A: slow down. Explain one function at a time with concrete examples
- Start with `compute_orders_with_budget` since it's the core of everything
- Draw the order book on paper: "Here are the bids, here are the asks, here's our theo price, here's what we'd buy and sell"

**"We disagree on a parameter"**
- Run the backtester with both values. Higher PnL wins. No debate.
