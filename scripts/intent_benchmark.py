from __future__ import annotations

import os
import sys
import statistics
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.services.semantic_router import IntentResolver


DATASET = [
    ("check inventory for brahmi chm", {"inventory_query"}),
    ("stock status for steel rods", {"inventory_query"}),
    ("only 5 units are there for cement?", {"inventory_query"}),
    ("kindly do the needful and check inventory", {"inventory_query"}),
    ("raise po for 50 pcs cement", {"purchase_order_create"}),
    ("purchese order for amber bottles", {"purchase_order_create"}),
    ("please create purchase order for capsules", {"purchase_order_create"}),
    ("PO undakkണം for tiles", {"purchase_order_create"}),
    ("apply leave for tomorrow", {"leave_application"}),
    ("half day leave for Anil", {"leave_application"}),
    ("leave request for next monday", {"leave_application"}),
    ("mark CL for today", {"leave_application"}),
    ("generate invoice for PO-1002", {"purchase_invoice_create"}),
    ("create purchese invoce", {"purchase_invoice_create"}),
    ("inv create for po 123", {"purchase_invoice_create"}),
    ("bill create for po", {"purchase_invoice_create"}),
    ("verify purchase order PO-1002", {"purchase_order_verify"}),
    ("PO is came verify it", {"purchase_order_verify"}),
    ("check and close the PO", {"purchase_order_verify"}),
    ("po status?", {"purchase_order_verify"}),
    ("update inventory for cement 20 units", {"inventory_update"}),
    ("recieve item and update inventory", {"inventory_update"}),
    ("goods received update stock", {"inventory_update"}),
    ("verify and update inventory", {"inventory_update", "purchase_order_verify"}),
    ("create po and generate invoice for cement", {"purchase_order_create", "purchase_invoice_create"}),
    ("verify and update PO-1002", {"purchase_order_verify", "inventory_update"}),
    ("what is Kerala weather now", set()),
    ("tell me a joke", set()),
]


def evaluate() -> None:
    resolver = IntentResolver()
    latencies_ms = []
    top1_correct = 0
    multi_expected = 0
    multi_detected_correct = 0
    unknown_expected = 0
    unknown_detected = 0

    for text, expected in DATASET:
        t0 = time.perf_counter()
        result = resolver.resolve(text)
        latencies_ms.append((time.perf_counter() - t0) * 1000)

        predicted = [entry["intent"] for entry in result.get("intents", [])]
        top1 = predicted[0] if predicted else "unknown_intent"

        if not expected:
            unknown_expected += 1
            if top1 == "unknown_intent":
                unknown_detected += 1
        elif top1 in expected:
            top1_correct += 1

        if len(expected) >= 2:
            multi_expected += 1
            if result.get("is_multi_intent") and any(intent in expected for intent in predicted):
                multi_detected_correct += 1

    total = len(DATASET)
    known_total = total - unknown_expected
    print("=== Intent Benchmark ===")
    print(f"Resolver mode: {resolver.mode}")
    print(f"Samples: {total}")
    print(f"Top-1 accuracy (known intents): {top1_correct}/{known_total} = {(top1_correct / known_total * 100):.2f}%")
    if multi_expected:
        print(
            f"Multi-intent detection accuracy: {multi_detected_correct}/{multi_expected} = "
            f"{(multi_detected_correct / multi_expected * 100):.2f}%"
        )
    if unknown_expected:
        print(
            f"Unknown-intent fallback precision: {unknown_detected}/{unknown_expected} = "
            f"{(unknown_detected / unknown_expected * 100):.2f}%"
        )

    print(f"Latency avg: {statistics.mean(latencies_ms):.2f} ms")
    print(f"Latency p95: {sorted(latencies_ms)[int(len(latencies_ms) * 0.95) - 1]:.2f} ms")
    print(f"Latency min/max: {min(latencies_ms):.2f} / {max(latencies_ms):.2f} ms")


if __name__ == "__main__":
    evaluate()
