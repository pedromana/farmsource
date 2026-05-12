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

async function refreshCartBadge() {
  const response = await fetch("/customer/cart/summary", {
    headers: { "X-Requested-With": "XMLHttpRequest" },
  });
  if (!response.ok) return;
  const cart = await response.json();
  setCartBadge(cart.count);
}

function showCartReadyDialog() {
  const dialog = document.querySelector("[data-cart-dialog]");
  if (!dialog || localStorage.getItem("farmsourceCartDialogSeen") === "true") return;
  localStorage.setItem("farmsourceCartDialogSeen", "true");
  if (typeof dialog.showModal === "function") {
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
  try {
    const cart = await submitCartForm(addForm);
    setCartBadge(cart.count);
    showCartReadyDialog();
  } catch (error) {
    alert("Unable to add this item to cart.");
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
  } catch (error) {
    alert("Unable to update cart quantity.");
  }
});

refreshCartBadge().catch(() => {});
