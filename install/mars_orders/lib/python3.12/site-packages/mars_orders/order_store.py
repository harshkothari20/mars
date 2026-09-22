"""MongoDB access for the MARS order flow.

No ROS imports here, so this file can be unit-tested without ROS.
Uses the same database and collections as the website and scan_order_qr.py:
shopping_cart.{products, orders, order_qr, transactions}

Order status flow:  PENDING -> IN_PROGRESS -> COMPLETED | FAILED
"""
from dataclasses import dataclass

from pymongo import MongoClient, ReturnDocument


@dataclass
class PickItem:
    product: str       # "Apple"
    product_id: str    # "APPLE001"
    qr_id: str         # text encoded in the aisle QR code
    quantity: int


class OrderStore:
    def __init__(self, uri="mongodb://localhost:27017", db_name="shopping_cart", client=None):
        self.client = client if client is not None else MongoClient(uri)
        db = self.client[db_name]
        self.orders = db["orders"]
        self.products = db["products"]
        self.qr = db["order_qr"]
        self.transactions = db["transactions"]

    # ---------- order lifecycle ----------

    def requeue_in_progress(self):
        """Put orders left IN_PROGRESS by a crashed run back to PENDING.

        Items already picked are skipped when the order is resumed
        (see remaining_items), so stock is never deducted twice.
        """
        return self.orders.update_many(
            {"status": "IN_PROGRESS"}, {"$set": {"status": "PENDING"}}
        ).modified_count

    def claim_next_order(self):
        """Atomically take the oldest PENDING order and mark it IN_PROGRESS."""
        return self.orders.find_one_and_update(
            {"status": "PENDING"},
            {"$set": {"status": "IN_PROGRESS"}},
            sort=[("_id", 1)],
            return_document=ReturnDocument.AFTER,
        )

    def complete_order(self, order):
        self.orders.update_one({"_id": order["_id"]}, {"$set": {"status": "COMPLETED"}})

    def fail_order(self, order, reason):
        self.orders.update_one(
            {"_id": order["_id"]},
            {"$set": {"status": "FAILED", "failure_reason": reason}},
        )

    # ---------- items and stock ----------

    def remaining_items(self, order):
        """Items still to pick, in cart order.

        Returns (items, unknown_names). unknown_names are cart products that
        have no record in order_qr.
        """
        picked = order.get("picked_products", {})
        items, unknown = [], []
        for name, entry in order.get("cart", {}).items():
            rec = self.qr.find_one({"product": name})
            if rec is None:
                unknown.append(name)
                continue
            if picked.get(rec["product_id"]) is True:
                continue
            items.append(
                PickItem(name, rec["product_id"], rec["qr_id"], int(entry["quantity"]))
            )
        return items, unknown

    def has_stock(self, product_id, quantity):
        doc = self.products.find_one({"product_id": product_id})
        return doc is not None and doc.get("quantity", 0) >= quantity

    def confirm_pick(self, order, item):
        """Call when the arm reports DONE.

        Deducts stock, logs a PICKED transaction and marks the product as
        picked on the order. Returns False (and changes nothing) if stock is
        too low.
        """
        res = self.products.update_one(
            {"product_id": item.product_id, "quantity": {"$gte": item.quantity}},
            {"$inc": {"quantity": -item.quantity}},
        )
        if res.modified_count == 0:
            return False

        self.transactions.insert_one(
            {
                "orderId": order["orderId"],
                "product_id": item.product_id,
                "product": item.product,
                "quantity": item.quantity,
                "type": "PICKED",
            }
        )
        self.orders.update_one(
            {"_id": order["_id"]},
            {"$set": {f"picked_products.{item.product_id}": True}},
        )
        return True
