import asyncio
import sys
import os

# Set up path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.services.intent_classifier import classify_and_plan, detect_intent

msgs = [
    "how many aloe vera gel 50g",
    "do we have aloe vera gel",
    "count aloe vera gel"
]

for msg in msgs:
    print(f"Message: {msg}")
    detection = detect_intent(msg)
    print(f"  Detected Intent (semantic/keyword): {detection.intent} (conf: {detection.confidence})")
    plan, metadata = classify_and_plan(msg)
    print(f"  Plan: {plan}")
    print(f"  Metadata: {metadata}")
    print("-" * 50)
