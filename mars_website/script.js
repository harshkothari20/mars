const buttons = document.querySelectorAll(".product button");

let cart = {};

buttons.forEach(function(button) {

    button.addEventListener("click", function() {

        const product = button.parentElement;

        const fruitName = product.querySelector("h2").textContent;
        const priceText = product.querySelector("p").textContent;
        const price = Number(priceText.replace("₹", ""));

        if (cart[fruitName]) {
            cart[fruitName].quantity++;
        } else {
            cart[fruitName] = {
                price: price,
                quantity: 1
            };
        }

        updateCart();

    });

});


function updateCart() {

    const cartItems = document.getElementById("cart-items");

    cartItems.innerHTML = "";

    let totalItems = 0;
    let totalPrice = 0;

    for (let fruit in cart) {

        const item = cart[fruit];

        const itemTotal = item.price * item.quantity;

        totalItems = totalItems + item.quantity;
        totalPrice = totalPrice + itemTotal;

        const itemElement = document.createElement("p");

        itemElement.textContent =
            fruit + " × " + item.quantity + " = ₹" + itemTotal;

        cartItems.appendChild(itemElement);
    }

    document.getElementById("total-items").textContent = totalItems;

    document.getElementById("total-price").textContent = totalPrice;

    document.getElementById("cart-count").textContent = totalItems;
}


// PLACE ORDER BUTTON

document.getElementById("place-order").addEventListener("click", function() {

    if (Object.keys(cart).length === 0) {
        alert("Your cart is empty.");
        return;
    }

    fetch("http://localhost:3000/order", {

        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({
            cart: cart,
            totalItems: document.getElementById("total-items").textContent,
            totalPrice: document.getElementById("total-price").textContent
        })

    })

    .then(response => {
        if (!response.ok) {
            throw new Error("Server returned " + response.status);
        }
        return response.text();
    })

    .then(message => {

        console.log(message);

        alert("Order placed successfully!");

        cart = {};
        updateCart();

    })

    .catch(error => {

        console.error("Error:", error);

        alert("Could not place order.");

    });

});