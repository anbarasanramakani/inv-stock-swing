import re

with open("app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if "run_full_btn" in l:
        print(f"{i+1}: {l.strip().encode('ascii', 'ignore').decode('ascii')}")
