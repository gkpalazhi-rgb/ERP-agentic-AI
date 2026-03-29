import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.intent_classifier import classify_and_plan, preload_model

def debug_queries():
    preload_model()
    
    queries = [
        "place order for 20 units of vicks",
        "can you order 500 syringes",
        "where is PO abc-999",
        "the shipment of 100 capsules was just delivered to us",
        "po 123 arrived with 50 units",
        "how many amrutha shampoo",
        "list all purchase orders",
        "is purchase order pending",
        "i need a new PO for shampoo",
        "are there any more leaves available?",
        "leaves"
    ]
    
    for q in queries:
        plan, metadata = classify_and_plan(q)
        print(f"Query: '{q}'")
        print(f"Plan: {plan}")
        print(f"Metadata: {metadata}")
        print("-" * 50)

if __name__ == '__main__':
    debug_queries()
