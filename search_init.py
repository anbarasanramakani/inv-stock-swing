import re

with open("app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if "st.session_state:" in l or "st.session_state" in l:
        if "if " in l and "not in" in l:
            print(f"{i+1}: {l.strip().encode('ascii', 'ignore').decode('ascii')}")
