from pymongo import MongoClient

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017")

# Shopping cart database
db = client["shopping_cart"]

# QR collection
qr_collection = db["order_qr"]


qr_list = [
    {
        "qr_id": "APPLE001",
        "product_id": "APPLE001",
        "product": "Apple"
    },
    {
        "qr_id": "BANANA001",
        "product_id": "BANANA001",
        "product": "Banana"
    },
    {
        "qr_id": "ORANGE001",
        "product_id": "ORANGE001",
        "product": "Orange"
    },
    {
        "qr_id": "GRAPES001",
        "product_id": "GRAPES001",
        "product": "Grapes"
    },
    {
        "qr_id": "WATERMELON001",
        "product_id": "WATERMELON001",
        "product": "Watermelon"
    },
    {
        "qr_id": "MANGO001",
        "product_id": "MANGO001",
        "product": "Mango"
    }
]


for qr in qr_list:

    qr_collection.update_one(
        {"qr_id": qr["qr_id"]},
        {"$set": qr},
        upsert=True
    )


print("Product QR records added to MongoDB!")

client.close()