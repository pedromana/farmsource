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

function updateOutreachProgress(progress) {
  if (!progress) return;
  const percent = document.querySelector("[data-outreach-progress-percent]");
  const researched = document.querySelector("[data-outreach-researched]");
  const researchedInline = document.querySelector("[data-outreach-researched-inline]");
  const total = document.querySelector("[data-outreach-total]");
  const researching = document.querySelector("[data-outreach-researching]");
  const researchingInline = document.querySelector("[data-outreach-researching-inline]");
  const remaining = document.querySelector("[data-outreach-remaining]");
  const foundContact = document.querySelector("[data-outreach-found-contact]");
  const queuedPercent = document.querySelector("[data-outreach-queued-percent]");
  const queueMessage = document.querySelector("[data-outreach-queue-message]");
  const bar = document.querySelector("[data-outreach-progress-bar]");
  if (percent) percent.textContent = `${progress.percent}%`;
  if (researched) researched.textContent = String(progress.researched || 0);
  if (researchedInline) researchedInline.textContent = String(progress.researched || 0);
  if (total) total.textContent = String(progress.total || 0);
  if (researching) researching.textContent = String(progress.researching || 0);
  if (researchingInline) researchingInline.textContent = String(progress.researching || 0);
  if (remaining) remaining.textContent = String(progress.remaining || 0);
  if (foundContact) foundContact.textContent = String(progress.found_contact || 0);
  if (queuedPercent) queuedPercent.textContent = String(progress.queued_percent || 0);
  if (bar) bar.style.width = `${progress.percent || 0}%`;
  if (queueMessage) {
    if ((progress.researching || 0) > 0) {
      queueMessage.textContent = "Use Research next 10 to research and save the next batch immediately. Use Research now on a row for a specific farm.";
    } else if ((progress.remaining || 0) === 0) {
      queueMessage.textContent = "There are no remaining candidates to research.";
    } else {
      queueMessage.textContent = "Use Research next 10 to research and save a batch immediately.";
    }
  }
}

function updateOutreachRow(candidate) {
  if (!candidate) return;
  const row = document.querySelector(`[data-outreach-row="${candidate.id}"]`);
  if (!row) return;
  row.classList.add("is-updating");
  window.setTimeout(() => row.classList.remove("is-updating"), 700);

  const researchStatus = row.querySelector("[data-research-status]");
  if (researchStatus) researchStatus.textContent = candidate.research_status || "";
  const researchButton = row.querySelector("[data-research-button]");
  const completedStatuses = ["found_contact", "verified"];
  if (researchButton && completedStatuses.includes(candidate.research_status)) {
    researchButton.disabled = true;
    researchButton.textContent = "Researched";
  } else if (researchButton && candidate.research_status === "no_contact_found") {
    researchButton.disabled = false;
    researchButton.textContent = "Research again";
  } else if (researchButton) {
    researchButton.disabled = false;
    researchButton.textContent = "Research now";
  }

  const email = row.querySelector("[data-contact-email]");
  const phone = row.querySelector("[data-contact-phone]");
  if (email) email.textContent = candidate.contact_email || "";
  if (phone) phone.textContent = candidate.contact_phone || "";

  const contactCell = row.querySelector("[data-contact-cell]");
  if (contactCell && candidate.website_url && !contactCell.querySelector("[data-website-link]")) {
    const link = document.createElement("a");
    link.dataset.websiteLink = "true";
    link.href = candidate.website_url;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "Website";
    contactCell.prepend(document.createElement("br"));
    contactCell.prepend(link);
  }
  if (contactCell && candidate.instagram_url && !contactCell.querySelector("[data-instagram-link]")) {
    const link = document.createElement("a");
    link.dataset.instagramLink = "true";
    link.href = candidate.instagram_url;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "Instagram";
    contactCell.prepend(document.createElement("br"));
    contactCell.prepend(link);
  }
  if (contactCell && candidate.facebook_url && !contactCell.querySelector("[data-facebook-link]")) {
    const link = document.createElement("a");
    link.dataset.facebookLink = "true";
    link.href = candidate.facebook_url;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "Facebook";
    contactCell.prepend(document.createElement("br"));
    contactCell.prepend(link);
  }
  if (
    contactCell &&
    candidate.contact_email &&
    ["found_contact", "verified"].includes(candidate.research_status) &&
    !contactCell.querySelector("[data-email-draft-link]")
  ) {
    const link = document.createElement("a");
    link.className = "button";
    link.dataset.emailDraftLink = "true";
    link.href = `/admin/outreach/candidates/${candidate.id}/email-suggestion`;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "Email draft";
    contactCell.append(document.createElement("br"), link);
  }

  const form = row.querySelector("[data-outreach-form]");
  if (!form) return;
  const values = {
    outreach_status: candidate.outreach_status,
    research_status: candidate.research_status,
    website_url: candidate.website_url,
    contact_email: candidate.contact_email,
    contact_phone: candidate.contact_phone,
    instagram_url: candidate.instagram_url,
    facebook_url: candidate.facebook_url,
    next_step: candidate.next_step,
    notes: candidate.notes,
  };
  Object.entries(values).forEach(([name, value]) => {
    const field = form.elements[name];
    if (field && document.activeElement !== field) field.value = value || "";
  });
}

async function requestCandidateResearch(button) {
  const candidateId = button.dataset.candidateId;
  if (!candidateId) return;
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "Researching...";
  try {
    const response = await fetch(`/admin/outreach/candidates/${candidateId}/research`, {
      method: "POST",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    if (!response.ok) throw new Error("Research request failed");
    const data = await response.json();
    updateOutreachRow(data.candidate);
    updateOutreachProgress(data.progress);
    showToast(data.already_completed ? "Research was already completed" : "Research completed");
  } catch (error) {
    showToast("Unable to request research.");
    button.disabled = false;
    button.textContent = originalText || "Research now";
  }
}

async function requestAllCandidateResearch(button) {
  const page = document.querySelector("[data-outreach-page]");
  if (!page) return;
  button.disabled = true;
  button.dataset.originalText = button.textContent;
  button.textContent = "Researching 10...";
  const formData = new FormData();
  formData.set("region", page.dataset.region || "seattle");
  try {
    const response = await fetch("/admin/outreach/research-all", {
      method: "POST",
      body: formData,
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    if (!response.ok) throw new Error("Research all request failed");
    const data = await response.json();
    updateOutreachProgress(data.progress);
    (data.candidates || []).forEach(updateOutreachRow);
    showToast(`${data.researched || 0} farms researched`);
  } catch (error) {
    showToast("Unable to research batch.");
  } finally {
    button.disabled = false;
    button.textContent = button.dataset.originalText || "Research next 10";
  }
}

async function submitOutreachForm(form) {
  const response = await fetch(form.action, {
    method: "POST",
    body: new FormData(form),
    headers: { "X-Requested-With": "XMLHttpRequest" },
  });
  if (!response.ok) throw new Error("Save failed");
  return response.json();
}

async function refreshOutreachUpdates() {
  const page = document.querySelector("[data-outreach-page]");
  if (!page) return;
  const params = new URLSearchParams();
  params.set("region", page.dataset.region || "seattle");
  if (page.dataset.statusFilter) params.set("status", page.dataset.statusFilter);
  if (page.dataset.researchFilter) params.set("research_status", page.dataset.researchFilter);
  const response = await fetch(`/admin/outreach/updates?${params}`, {
    headers: { "X-Requested-With": "XMLHttpRequest" },
  });
  if (!response.ok) return;
  const data = await response.json();
  updateOutreachProgress(data.progress);
  (data.candidates || []).forEach(updateOutreachRow);
}

document.addEventListener("click", (event) => {
  const allButton = event.target.closest("[data-research-all-button]");
  if (allButton) {
    requestAllCandidateResearch(allButton);
    return;
  }
  const button = event.target.closest("[data-research-button]");
  if (!button) return;
  requestCandidateResearch(button);
});

document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-outreach-form]");
  if (!form) return;
  event.preventDefault();
  const button = form.querySelector('button[type="submit"]');
  if (button) {
    button.disabled = true;
    button.dataset.originalText = button.textContent;
    button.textContent = "Saving...";
  }
  try {
    const data = await submitOutreachForm(form);
    updateOutreachRow(data.candidate);
    updateOutreachProgress(data.progress);
    showToast("Outreach candidate saved");
  } catch (error) {
    showToast("Unable to save outreach candidate.");
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = button.dataset.originalText || "Save";
    }
  }
});

document.addEventListener("submit", (event) => {
  if (event.defaultPrevented) return;
  const form = event.target.closest("form");
  if (!form || form.matches(".inline-cart-form, .quantity-form, [data-cart-quantity-form]")) return;
  const button = form.querySelector('button[type="submit"], button:not([type])');
  if (!button) return;
  button.dataset.originalText = button.textContent;
  button.classList.add("is-loading");
  button.textContent = "Working...";
});

refreshCartBadge().catch(() => {});
if (document.querySelector("[data-outreach-page]")) {
  refreshOutreachUpdates().catch(() => {});
  window.setInterval(() => refreshOutreachUpdates().catch(() => {}), 5000);
}
