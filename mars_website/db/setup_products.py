from pymongo import MongoClient

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017")

# Shopping cart database
db = client["shopping_cart"]

# Products collection
products = db["products"]


product_list = [
    {
        "product_id": "APPLE001",
        "name": "Apple",
        "price": 120,
        "quantity": 50
    },
    {
        "product_id": "BANANA001",
        "name": "Banana",
        "price": 60,
        "quantity": 50
    },
    {
        "product_id": "ORANGE001",
        "name": "Orange",
        "price": 80,
        "quantity": 50
    },
    {
        "product_id": "GRAPES001",
        "name": "Grapes",
        "price": 100,
        "quantity": 50
    },
    {
        "product_id": "WATERMELON001",
        "name": "Watermelon",
        "price": 150,
        "quantity": 50
    },
    {
        "product_id": "MANGO001",
        "name": "Mango",
        "price": 120,
        "quantity": 50
    }
]


for product in product_list:

    products.update_one(
        {"product_id": product["product_id"]},
        {"$setOnInsert": product},
        upsert=True
    )


print("Products setup completed!")

client.close()