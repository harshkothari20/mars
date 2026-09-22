const http = require("http");
const fs = require("fs");
const { MongoClient } = require("mongodb");

const mongoClient = new MongoClient("mongodb://localhost:27017");

let ordersCollection;


const server = http.createServer((req, res) => {

    // Open the webpage
    if (req.method === "GET" && req.url === "/") {

        fs.readFile(__dirname + "/index.html", (err, data) => {

            if (err) {
                res.writeHead(500);
                res.end("Error loading webpage");
                return;
            }

            res.writeHead(200, {
                "Content-Type": "text/html; charset=UTF-8"
            });

            res.end(data);
        });

        return;
    }


    // Receive the order
    if (req.method === "POST" && req.url === "/order") {

        let body = "";

        req.on("data", chunk => {
            body += chunk;
        });

        req.on("end", async () => {

            try {

                const order = JSON.parse(body);

                // Create a unique order ID
                const orderId = "ORDER-" + Date.now();

                // Add order information
                order.orderId = orderId;
                order.status = "PENDING";

                // Save order into MongoDB
                await ordersCollection.insertOne(order);

                console.log("\n========== NEW ORDER ==========");
                console.log("Order ID: " + orderId);

                for (let fruit in order.cart) {

                    const item = order.cart[fruit];

                    console.log(
                        fruit +
                        " x " +
                        item.quantity +
                        " = Rs." +
                        (item.price * item.quantity)
                    );
                }

                console.log("-------------------------------");
                console.log("Total Items: " + order.totalItems);
                console.log("Total Price: Rs." + order.totalPrice);
                console.log("===============================\n");


                // Order saved successfully
                res.writeHead(200, {
                    "Content-Type": "text/plain"
                });

                res.end("Order received!");

            } catch (error) {

                console.error("Order error:", error);

                res.writeHead(500);
                res.end("Error processing order");

            }

        });

        return;
    }


    // Serve CSS
    if (req.method === "GET" && req.url === "/style.css") {

        fs.readFile(__dirname + "/style.css", (err, data) => {

            if (err) {
                res.writeHead(500);
                res.end("Error loading CSS");
                return;
            }

            res.writeHead(200, {
                "Content-Type": "text/css; charset=UTF-8"
            });

            res.end(data);
        });

        return;
    }


    // Serve JavaScript
    if (req.method === "GET" && req.url === "/script.js") {

        fs.readFile(__dirname + "/script.js", (err, data) => {

            if (err) {
                res.writeHead(500);
                res.end("Error loading JavaScript");
                return;
            }

            res.writeHead(200, {
                "Content-Type": "text/javascript; charset=UTF-8"
            });

            res.end(data);
        });

        return;
    }


    // Page not found
    res.writeHead(404);
    res.end("Not Found");

});


// Start server and connect to MongoDB
async function startServer() {

    await mongoClient.connect();

    const db = mongoClient.db("shopping_cart");

    ordersCollection = db.collection("orders");

    console.log("Connected to MongoDB!");

    server.listen(3000, () => {

        console.log("Server running at http://localhost:3000");

    });

}


startServer();