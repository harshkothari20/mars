import mongomock
import pytest

from mars_orders.order_store import OrderStore


@pytest.fixture
def store():
    s = OrderStore(client=mongomock.MongoClient())
    s.products.insert_many([
        {"product_id": "APPLE001", "name": "Apple", "price": 120, "quantity": 5},
        {"product_id": "BANANA001", "name": "Banana", "price": 60, "quantity": 1},
    ])
    s.qr.insert_many([
        {"qr_id": "APPLE001", "product_id": "APPLE001", "product": "Apple"},
        {"qr_id": "BANANA001", "product_id": "BANANA001", "product": "Banana"},
    ])
    return s


def add_order(store, cart, oid="ORDER-1"):
    store.orders.insert_one({"orderId": oid, "status": "PENDING", "cart": cart})


def cart(**kw):
    return {name: {"price": 1, "quantity": q} for name, q in kw.items()}


def test_claim_is_fifo_and_marks_in_progress(store):
    add_order(store, cart(Apple=1), "ORDER-1")
    add_order(store, cart(Banana=1), "ORDER-2")
    first = store.claim_next_order()
    assert first["orderId"] == "ORDER-1"
    assert first["status"] == "IN_PROGRESS"
    assert store.claim_next_order()["orderId"] == "ORDER-2"
    assert store.claim_next_order() is None


def test_remaining_items_and_unknown(store):
    add_order(store, cart(Apple=2, Mango=1))
    order = store.claim_next_order()
    items, unknown = store.remaining_items(order)
    assert [(i.product_id, i.quantity) for i in items] == [("APPLE001", 2)]
    assert unknown == ["Mango"]


def test_confirm_pick_deducts_stock_and_marks_picked(store):
    add_order(store, cart(Apple=2))
    order = store.claim_next_order()
    item = store.remaining_items(order)[0][0]
    assert store.confirm_pick(order, item) is True
    assert store.products.find_one({"product_id": "APPLE001"})["quantity"] == 3
    assert store.transactions.count_documents({"orderId": "ORDER-1", "type": "PICKED"}) == 1
    assert store.orders.find_one({"_id": order["_id"]})["picked_products"]["APPLE001"] is True


def test_confirm_pick_rejects_low_stock(store):
    add_order(store, cart(Banana=2))
    order = store.claim_next_order()
    item = store.remaining_items(order)[0][0]
    assert store.has_stock("BANANA001", 2) is False
    assert store.confirm_pick(order, item) is False
    assert store.products.find_one({"product_id": "BANANA001"})["quantity"] == 1
    assert store.transactions.count_documents({}) == 0


def test_resume_skips_picked_items(store):
    add_order(store, cart(Apple=1, Banana=1))
    order = store.claim_next_order()
    apple = store.remaining_items(order)[0][0]
    store.confirm_pick(order, apple)

    assert store.requeue_in_progress() == 1
    resumed = store.claim_next_order()
    items, _ = store.remaining_items(resumed)
    assert [i.product_id for i in items] == ["BANANA001"]


def test_complete_and_fail(store):
    add_order(store, cart(Apple=1), "ORDER-1")
    add_order(store, cart(Apple=1), "ORDER-2")
    a, b = store.claim_next_order(), store.claim_next_order()
    store.complete_order(a)
    store.fail_order(b, "arm timed out")
    assert store.orders.find_one({"orderId": "ORDER-1"})["status"] == "COMPLETED"
    failed = store.orders.find_one({"orderId": "ORDER-2"})
    assert failed["status"] == "FAILED" and failed["failure_reason"] == "arm timed out"
