# PREP CHECKLIST & RESOURCES

Everything you need to install, clone, and read before April 14.

---

## CRITICAL FIRST STEPS (Do Today)

### 1. Verify Platform Access

- [ ] Both team members registered at https://prosperity.imc.com/
- [ ] Both linked to the same team
- [ ] Reminder: roster locks after Round 2

### 2. Install the Backtester

```bash
pip install prosperity4btx
```

This is jmerle's community backtester for P4, available on PyPI:
https://libraries.io/pypi/prosperity4btx

If the package name changes or doesn't install, check:
https://github.com/jmerle (jmerle maintains backtesters for every Prosperity edition)

Previous edition backtester for reference:
https://pypi.org/project/prosperity3bt/

### 3. Inspect the DataModel

After installing, inspect the actual class interfaces:

```python
# Run this to see what TradingState, Order, OrderDepth look like
import prosperity4btx
# Or check the source:
# pip show prosperity4btx  -> find the install location
# Then read the datamodel.py file
```

**VERIFY THESE BEFORE WRITING ANY CODE:**
- What fields does `TradingState` have?
- Are `sell_orders` volumes negative or positive?
- What is the exact `Order` constructor signature?
- Does `run()` return `(dict, int, str)` or something else?

### 4. Access Tutorial Round

- [ ] Log in at https://prosperity.imc.com/
- [ ] Navigate to the tutorial round
- [ ] Download any available data for the tutorial products
- [ ] Make a test submission to confirm the pipeline works

### 5. Set Up Shared Infrastructure

- [ ] Create private Git repo (GitHub/GitLab)
- [ ] Both members have push access
- [ ] Set up MS Teams channel for async comms
- [ ] Create a shared folder for Jupyter notebooks and analysis outputs

---

## GITHUB REPOS TO CLONE (Priority Order)

Clone all of these. They contain price data, strategy implementations, and writeups from top finishers.

### Tier 1: Must-Read (top-10 finishers with detailed writeups)

```bash
# Frankfurt Hedgehogs - 2nd globally, P3. Best writeup available.
git clone https://github.com/TimoDiehm/imc-prosperity-3.git

# CMU Physics - 7th globally / 1st USA, P3. Candid about mistakes.
git clone https://github.com/chrispyroberts/imc-prosperity-3.git

# Linear Utility - 2nd globally, P2. In-house backtester, P1 data reuse exploit.
git clone https://github.com/ericcccsliu/imc-prosperity-2.git

# Stanford Cardinal - 2nd globally, P1. Clean strategy implementations.
git clone https://github.com/ShubhamAnandJain/IMC-Prosperity-2023-Stanford-Cardinal.git
```

### Tier 2: Valuable Reference

```bash
# Alpha Animals - 9th globally / 2nd USA, P3. Confirmed bot copy-trading works.
git clone https://github.com/CarterT27/imc-prosperity-3.git

# Rank 13, P2. Microprice fair value, Monte Carlo augmentation.
git clone https://github.com/pe049395/IMC-Prosperity-2024.git

# jmerle - 9th, P2. Built the standard toolset (backtester, visualizer).
git clone https://github.com/jmerle/imc-prosperity-2.git

# Top 1% worldwide, P3. Combines market making, index arb, B-S options.
git clone https://github.com/Sylvain-Topeza/imc-prosperity-3.git

# Ding Crab - 28th algo / 44th overall, P3. Good documentation.
git clone https://github.com/angus4718/imc-prosperity-3-public.git
```

### Tier 3: Additional Reference

```bash
# P1 solution
git clone https://github.com/nicolassinott/IMC_Prosperity.git

# P1 solution with good README
git clone https://github.com/amogh18t/IMC-Prosperity.git

# Beginner-friendly P3 guide
git clone https://github.com/MarkBrezina/Ctrl-Alt-DefeatTheMarket.git

# P3 UCSD team
git clone https://github.com/ShivUCSD1104/IMC-Prosperity-3.git
```

---

## BLOG POSTS & WRITEUPS TO READ

### Essential

- **Frankfurt Hedgehogs P3 writeup** (in their GitHub repo README)
  - Covers: wall-mid pricing, custom dashboard, hardcoding exploit, fallback architecture
  
- **CMU Physics P3 writeup** (in their GitHub repo README)
  - Covers: what went wrong with options model, lessons on simplicity vs sophistication

- **Linear Utility P2 writeup** (in their GitHub repo README)
  - Covers: backtester design, data reuse exploit, parametric optimization

### Recommended

- David Teather's P2 writeup: https://medium.com/@davidteather/imc-prosperity-2-b1c94b1ebba8
- Matius Chong's P3 writeup: https://medium.com/@matius_chong/imc-prosperity-3-challenge-2025-2af2a7a4132b
- Martin Oravec's P3 writeup: https://medium.com/@oravec.martin01/imc-prosperity-3-be859180f133
- Shriyan Gosavi top-100 strategies: https://medium.com/@shriyan.gosavi/how-i-placed-top-100-in-the-imc-trading-challenge-my-favorite-strategies-explained-286f15a5b056
- Sam Bennett top 0.8% writeup: https://medium.com/@samjgbennett/trading-triumphs-my-journey-to-finishing-4th-in-the-uk-and-top-0-8-globally-in-algo-trading-0248f862ec0b

### IMC Official

- Prosperity 4 homepage: https://prosperity.imc.com/
- P4 announcement: https://www.imc.com/us/corporate-news/prosperity-4
- P4 article: https://www.imc.com/us/articles/prosperity-4-imc-global-trading-challenge
- P3 announcement: https://www.imc.com/us/corporate-news/prosperity-3-IMCs-global-trading-challenge-returns
- Anant's Prosperity-to-internship journey: https://www.imc.com/us/articles/from-prosperity-to-imc-internship-anant-consul-s-journey
- Terms & conditions: https://prosperity.imc.com/terms-and-conditions

---

## 4-DAY PREP PLAN

### Day 1: April 10 (Today) - Tooling & Infrastructure

**Person A (you):**
- [ ] `pip install prosperity4btx`
- [ ] Inspect the datamodel classes (`TradingState`, `Order`, `OrderDepth`)
- [ ] Verify: are sell_orders volumes negative or positive?
- [ ] Build the Trader class skeleton (from 02_CODE_TEMPLATES.md Section 1)
- [ ] Test a "do nothing" submission on the tutorial round to confirm pipeline

**Person B (teammate):**
- [ ] Clone all Tier 1 GitHub repos (see list above)
- [ ] Extract price data from P1, P2, P3 repos into a reference folder
- [ ] Read the Frankfurt Hedgehogs writeup (TimoDiehm repo README)
- [ ] Read the CMU Physics writeup (chrispyroberts repo README)
- [ ] Set up the shared Git repo and MS Teams channel

**End of day deliverable:** Working skeleton that submits and runs. All repos cloned. Both people have read at least one top-team writeup.

### Day 2: April 11 - Strategy Templates

**Person A:**
- [ ] Implement stable product market maker (Section 5 of CODE_TEMPLATES)
- [ ] Implement EMA-based volatile product market maker (Section 6)
- [ ] Implement position budget tracker (Section 4)
- [ ] Implement state serialization framework (Section 3)
- [ ] Test all of the above on tutorial round data. Get positive PnL.

**Person B:**
- [ ] Read the Linear Utility P2 writeup (ericcccsliu repo)
- [ ] Read 2-3 Medium blog posts from the list above
- [ ] Create the analysis notebook template (Section 13 of CODE_TEMPLATES)
- [ ] Test the analysis notebook on tutorial round data
- [ ] Begin building the historical price dataset for data reuse detection

**End of day deliverable:** Market making strategies working on tutorial products. Analysis notebook template ready. Historical data compiled.

### Day 3: April 12 - Advanced Templates

**Person A:**
- [ ] Implement z-score basket arbitrage template (Section 8)
- [ ] Implement Black-Scholes + implied vol solver (Section 9)
- [ ] Implement bot tracker framework (Section 10)
- [ ] Verify all math functions work without scipy (pure Python only)
- [ ] Stress test: serialize/deserialize state with 15 products, 200 ticks each

**Person B:**
- [ ] Pre-code FX arbitrage solver for manual challenges (Section 12)
- [ ] Review prior-year manual challenge formats (check GitHub repo writeups)
- [ ] Build a simple game-theory expected-value calculator
- [ ] Complete the historical price dataset from all P1/P2/P3 repos
- [ ] Test data reuse detection on known cases (P2 coconuts vs P1 coconuts)

**End of day deliverable:** All strategy templates implemented and tested. Manual challenge tools ready. Data reuse pipeline validated.

### Day 4: April 13 - Rehearsal & Rest

**Both together (2-3 hours max):**
- [ ] Run a full simulated "Round 1 morning" using tutorial data:
  - Start timer
  - Pretend you just received Round 1 spec
  - Person B runs analysis notebook
  - Person A implements strategy using pre-built templates
  - Time to first submission: target < 3 hours
- [ ] Review the complete codebase together
- [ ] Discuss: what's our plan if Round 1 product is unexpectedly complex?
- [ ] Discuss: what's our kill switch if a strategy is losing money?

**Afternoon: rest.** Round 1 opens April 14. Be well-rested.

---

## DURING THE COMPETITION: ROUND-BY-ROUND CHECKLIST

### Every Round Opening

- [ ] Read the full spec carefully. Both people.
- [ ] Person A: check position limits, verify data format hasn't changed
- [ ] Person B: download data, run analysis notebook, check for data reuse
- [ ] Sync after 2-3 hours: agree on strategy per new product
- [ ] Person A (or whoever is primary coder this round): implement
- [ ] Safety submission within 4 hours
- [ ] Other person: review code, work on manual challenge
- [ ] Parameter tuning
- [ ] Final submission 2+ hours before deadline

### Every Submission

- [ ] Does the full file run without errors on the backtester?
- [ ] Are ALL products handled (including previous rounds)?
- [ ] Are position limits respected for every product?
- [ ] Is traderData serialization working?
- [ ] Has the other person reviewed the code?
- [ ] Are there any unnecessary print statements? (strip them in later rounds)

### The 4-Day Intermission (Between R2 and R3)

- [ ] Both people: full code review of everything submitted so far
- [ ] Refactor if the file is getting messy
- [ ] Review Round 1 and 2 results: which strategies made money, which didn't?
- [ ] Prepare for options (Round 3 likely): verify B-S templates work
- [ ] Rest. Rounds 3-5 are rapid fire (48h each, back to back).

---

## QUICK REFERENCE: KEY NUMBERS

| Metric | Value |
|---|---|
| Total rounds | 5 |
| Round 1-2 duration | 72 hours each |
| Round 3-5 duration | 48 hours each |
| Total competition span | ~16 days |
| Max team size | 5 (you're using 2) |
| Roster lock | After Round 2 |
| Currency | XIRECs |
| Prize: 1st place | $25,000 |
| Prize: 2nd | $10,000 |
| Prize: 3rd | $5,000 |
| Prize: Best Manual Trader | $5,000 |
| Expected products by R5 | 10-15 |
| Position limits | Product-specific, given in spec |
| Language | Python only, single file |
| Execution | Asynchronous (submit code, engine runs it) |

**NOTE:** Prize amounts and exact round durations are from official P4 sources but should be reverified at https://prosperity.imc.com/ and https://prosperity.imc.com/terms-and-conditions as IMC may amend terms before the competition starts.

---

## FILE STRUCTURE FOR YOUR REPO

```
prosperity4/
    README.md
    
    # Competition submission (ONE file)
    trader.py                    # The actual submission file
    
    # Local development
    templates/
        math_utils.py            # norm_cdf, norm_pdf, B-S functions
        strategy_stable.py       # Stable product market maker
        strategy_ema.py          # EMA volatile product market maker
        strategy_basket.py       # Z-score basket arb
        strategy_options.py      # IV mean-reversion
        strategy_bots.py         # Bot tracker (Round 5)
    
    # Analysis
    notebooks/
        round_N_analysis.ipynb   # Per-round analysis (Person B)
        data_reuse_check.ipynb   # Cross-year correlation check
        parameter_sweep.ipynb    # Backtest parameter optimization
    
    # Historical data (from cloned repos)
    historical_data/
        p1_prices/               # Extracted from Stanford Cardinal repo
        p2_prices/               # Extracted from Linear Utility repo
        p3_prices/               # Extracted from Frankfurt Hedgehogs repo
    
    # Manual challenge tools
    manual/
        fx_arbitrage.py
        game_theory.py
    
    # Playbook (these files)
    playbook/
        01_MASTERPLAN.md
        02_CODE_TEMPLATES.md
        03_PREP_CHECKLIST.md
```

**IMPORTANT:** When submitting, you submit ONLY `trader.py`. Copy all needed functions (math utils, strategy code) into that single file. The templates/ folder is for development organization only.
