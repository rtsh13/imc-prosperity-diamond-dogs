import subprocess
import re

with open("trader.py", "r") as f:
    original = f.read()

results = []

for ema_alpha in [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]:
    for tom_spread in [3, 4, 5]:
        for retreat in [0.005, 0.01, 0.015]:
            for em_spread in [2,3]:
                code = original
                code = re.sub(r"EMA_ALPHA = \S+", f"EMA_ALPHA = {ema_alpha}", code)
                code = re.sub(r"TOMATOES_SPREAD = \S+", f"TOMATOES_SPREAD = {tom_spread}", code)
                code = re.sub(r"RETREAT = \S+", f"RETREAT = {retreat}", code)
                code = re.sub(r"EMERALDS_SPREAD = \S+", f"EMERALDS_SPREAD = {em_spread}", code)

                with open("trader_sweep.py", "w") as f:
                    f.write(code)

                out = subprocess.run(
                    ["python3", "-m", "prosperity4bt", "trader_sweep.py",
                     "0--2", "0--1", "--merge-pnl", "--no-out", "--no-progress"],
                    capture_output=True, text=True
                )
                matches = re.findall(r"Total profit: ([\d,]+)", out.stdout)
                pnl = int(matches[-1].replace(",", "")) if matches else -1
                results.append((pnl, ema_alpha, tom_spread, retreat, em_spread))
                print(f"a={ema_alpha} ts={tom_spread} r={retreat} es={em_spread} -> {pnl}")

results.sort(reverse=True)
print("\n--- TOP 10 ---")
for pnl, a, ts, r, es in results[:10]:
    print(f"PnL={pnl}  ema_alpha={a}  tom_spread={ts}  retreat={r}  em_spread={es}")