if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/js/service-worker.js").catch(() => {});
  });
}

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

function setCartBadge(count) {
  document.querySelectorAll("[data-cart-count]").forEach((badge) => {
    badge.textContent = String(count || 0);
    badge.hidden = !count;
  });
}

function showToast(message) {
  const toast = document.querySelector("[data-toast]");
  if (!toast) return;
  toast.textContent = message;
  toast.hidden = false;
  toast.classList.add("is-visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toast.classList.remove("is-visible");
    window.setTimeout(() => {
      toast.hidden = true;
    }, 180);
  }, 2600);
}

async function refreshCartBadge() {
  const response = await fetch("/customer/cart/summary", {
    headers: { "X-Requested-With": "XMLHttpRequest" },
  });
  if (!response.ok) return;
  const cart = await response.json();
  setCartBadge(cart.count);
}

let cartBubbleTimer;

function showCartBubble(productName) {
  const bubble = document.querySelector("[data-cart-bubble]");
  if (!bubble) return;
  const text = bubble.querySelector("[data-cart-bubble-text]");
  if (text) {
    text.textContent = productName ? `${productName} added to the cart.` : "Item added to the cart.";
  }
  bubble.hidden = false;
  bubble.classList.remove("is-visible");
  window.requestAnimationFrame(() => bubble.classList.add("is-visible"));
  window.clearTimeout(cartBubbleTimer);
  cartBubbleTimer = window.setTimeout(() => {
    bubble.classList.remove("is-visible");
    window.setTimeout(() => {
      bubble.hidden = true;
    }, 180);
  }, 3200);
}

function showCartAddedNotice(productName) {
  if (localStorage.getItem("farmsourceCartDialogSeen") === "true") {
    showCartBubble(productName);
    return;
  }
  const dialog = document.querySelector("[data-cart-dialog]");
  if (!dialog) return;
  const title = dialog.querySelector("[data-cart-dialog-title]");
  if (title) {
    title.textContent = "Item added to your cart.";
  }
  localStorage.setItem("farmsourceCartDialogSeen", "true");
  if (typeof dialog.showModal === "function") {
    if (dialog.open) dialog.close();
    dialog.showModal();
  }
}

async function submitCartForm(form) {
  const response = await fetch(form.action, {
    method: "POST",
    body: new FormData(form),
    headers: { "X-Requested-With": "XMLHttpRequest" },
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Cart update failed");
  }
  return response.json();
}

function updateCartTotals(cart) {
  setCartBadge(cart.count);
  const values = {
    "[data-cart-subtotal]": cart.subtotal,
    "[data-cart-delivery]": cart.delivery_fee,
    "[data-cart-taxes]": cart.taxes,
    "[data-cart-total]": cart.total,
  };
  Object.entries(values).forEach(([selector, value]) => {
    const element = document.querySelector(selector);
    if (element) element.textContent = money.format(value || 0);
  });
  cart.items.forEach((item) => {
    const row = document.querySelector(`[data-cart-row][data-item-id="${item.id}"]`);
    if (!row) return;
    const lineTotal = row.querySelector("[data-line-total]");
    if (lineTotal) lineTotal.textContent = money.format(item.total_price || 0);
  });
}

document.addEventListener("submit", async (event) => {
  const addForm = event.target.closest(".inline-cart-form, .quantity-form");
  if (!addForm) return;
  event.preventDefault();
  const button = addForm.querySelector(".add-cart-button, button[type='submit']");
  const originalText = button?.textContent || "Add to cart";
  if (button) {
    button.disabled = true;
    button.classList.remove("is-added");
    button.classList.add("is-adding");
    button.textContent = "Adding...";
  }
  try {
    const cart = await submitCartForm(addForm);
    setCartBadge(cart.count);
    if (button) {
      button.classList.remove("is-adding");
      button.classList.add("is-added");
      button.textContent = "Added";
      window.setTimeout(() => {
        button.classList.remove("is-added");
        button.disabled = false;
        button.textContent = originalText;
      }, 1400);
    }
    showCartAddedNotice(addForm.dataset.productName);
    showToast("Added to cart");
  } catch (error) {
    if (button) {
      button.classList.remove("is-adding", "is-added");
      button.disabled = false;
      button.textContent = originalText;
    }
    showToast("Unable to add this item to cart.");
  }
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-qty-step]");
  if (!button) return;
  const form = button.closest("[data-cart-quantity-form]");
  const input = form?.querySelector('input[name="quantity"]');
  if (!form || !input) return;
  input.value = String(Math.max(0, Number(input.value || 0) + Number(button.dataset.qtyStep)));
  input.dispatchEvent(new Event("change", { bubbles: true }));
});

document.addEventListener("change", async (event) => {
  const input = event.target.closest('[data-cart-quantity-form] input[name="quantity"]');
  if (!input) return;
  const form = input.closest("[data-cart-quantity-form]");
  try {
    const cart = await submitCartForm(form);
    if (Number(input.value) <= 0) {
      form.closest("[data-cart-row]")?.remove();
    }
    updateCartTotals(cart);
    showToast("Cart updated");
  } catch (error) {
    showToast("Unable to update cart quantity.");
  }
});

document.addEventListener("submit", (event) => {
  const form = event.target.closest("form");
  if (!form || form.matches(".inline-cart-form, .quantity-form, [data-cart-quantity-form]")) return;
  const button = form.querySelector('button[type="submit"], button:not([type])');
  if (!button) return;
  button.dataset.originalText = button.textContent;
  button.classList.add("is-loading");
  button.textContent = "Working...";
});

refreshCartBadge().catch(() => {});
