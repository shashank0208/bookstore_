// Shared cart logic — used by books.html, topseller.html, genre.html, cart.html
// Cart item schema: { id, title, price, quantity }

function getCart() {
    return JSON.parse(localStorage.getItem("cart")) || [];
}

function saveCart(cart) {
    localStorage.setItem("cart", JSON.stringify(cart));
}

function addToCart(bookId, title, price) {
    let cart = getCart();
    const existing = cart.find(item => item.id === bookId);

    if (existing) {
        existing.quantity += 1;
    } else {
        cart.push({ id: bookId, title: title, price: price, quantity: 1 });
    }

    saveCart(cart);
    alert(`${title} added to cart!`);
}
