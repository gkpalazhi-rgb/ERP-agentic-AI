from services.erp_tools.customer_service import create_customer
from services.erp_tools.invoice_service import create_invoice
from services.erp_tools.order_service import create_order
from services.erp_tools.inventory_service import get_inventory


customer = create_customer("Vivek", "vivek@email.com")

invoice = create_invoice(customer["id"], 5000)

order = create_order(customer["id"], "Laptop", 1)

inventory = get_inventory("Laptop")


print(customer)
print(invoice)
print(order)
print(inventory)