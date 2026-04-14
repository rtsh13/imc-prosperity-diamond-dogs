import re

with open("trader.py", "r") as f:
    original = f.read()

code = original
code = re.sub(r"EMA_ALPHA = \S+", "EMA_ALPHA = 0.1", code)
code = re.sub(r"TOMATOES_SPREAD = \S+", "TOMATOES_SPREAD = 3", code)
code = re.sub(r"RETREAT = \S+", "RETREAT = 0.01", code)
code = re.sub(r"EMERALDS_SPREAD = \S+", "EMERALDS_SPREAD = 2", code)

with open("trader_sweep.py", "w") as f:
    f.write(code)

print("DIFF:")
for i, (a, b) in enumerate(zip(original.splitlines(), code.splitlines())):
    if a != b:
        print(f"Line {i+1}: ORIGINAL: {a!r}")
        print(f"         PATCHED:  {b!r}")