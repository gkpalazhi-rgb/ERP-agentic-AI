import re

msgs = [
    "11 neem tab arrived",
    "11 neem tab arrived , ID 260328-NEMA-001",
    "260328-NEMA-001 arrived",
]

patterns = [
    ("qty+text+arrived", re.compile(r"\b\d+\s+[a-z].+\b(?:arrived|received|delivered)\b", re.I)),
    ("POID+arrived", re.compile(r"\b\d{6}-[A-Z0-9]+-\d{3}\b.*\b(?:arrived|received|delivered)\b", re.I)),
    ("arrived+POID", re.compile(r"\b(?:arrived|received|delivered)\b.*\b\d{6}-[A-Z0-9]+-\d{3}\b", re.I)),
    ("arrived+ID/PO", re.compile(r"\b(?:arrived|received|delivered)\b\s*[,.]?\s*\b(?:id|po)\b", re.I)),
]

for msg in msgs:
    matched = [name for name, p in patterns if p.search(msg)]
    print(f"{msg!r}: matched={matched}")

# Test item extraction
print("\n--- Item Extraction ---")
pattern = re.compile(r"\b\d+\s+([a-z][a-z0-9\s]+?)\s+(?:arrived|received|delivered|has\s+arrived|have\s+arrived)\b", re.I)
for msg in msgs:
    m = pattern.search(msg)
    print(f"{msg!r}: item={m.group(1) if m else 'NONE'}")

# Test PO ID extraction
print("\n--- PO ID Extraction ---")
po_pattern = re.compile(r"(\d{6}-[A-Z0-9]+-\d{3})", re.I)
for msg in msgs:
    m = po_pattern.search(msg)
    print(f"{msg!r}: po_id={m.group(1).upper() if m else 'NONE'}")

# Test quantity extraction (scrubbed)
print("\n--- Quantity Extraction ---")
for msg in msgs:
    scrubbed = re.sub(r"\b\d{6}-[A-Z0-9]+-\d{3}\b", " ", msg, flags=re.I)
    scrubbed = re.sub(r"\b(?:po|order)\s*#?\s*\d+\b", " ", scrubbed, flags=re.I)
    m = re.search(r"\b(?:qty|quantity|for|of)?\s*(\d+)\b", scrubbed, re.I)
    print(f"{msg!r}: qty={int(m.group(1)) if m else 0}")
