# app/api/erp_routes.py

from fastapi import APIRouter

from app.services.erp_tools.customer_service import create_customer, get_customer
from app.services.erp_tools.invoice_service import create_invoice
from app.services.erp_tools.order_service import create_order
from app.services.erp_tools.inventory_service import get_inventory, update_inventory


router = APIRouter()


@router.post("/customer")
def add_customer(name: str, email: str):
    return create_customer(name, email)


@router.get("/customer/{customer_id}")
def fetch_customer(customer_id: int):
    return get_customer(customer_id)


@router.post("/invoice")
def add_invoice(customer_id: int, amount: int):
    return create_invoice(customer_id, amount)


@router.post("/order")
def add_order(customer_id: int, product: str, quantity: int):
    return create_order(customer_id, product, quantity)


@router.get("/inventory/{product}")
def check_inventory(product: str):
    return get_inventory(product)


@router.put("/inventory")
def modify_inventory(product: str, quantity: int):
    return update_inventory(product, quantity)