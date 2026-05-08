const state = { page: 1, perPage: 25, total: 0 };

const fields = [
  "search",
  "city",
  "county",
  "state",
  "products",
  "platform",
  "source",
  "destination_type",
];

function params() {
  const search = new URLSearchParams();
  for (const id of fields) {
    const value = document.getElementById(id).value.trim();
    if (value) search.set(id, value);
  }
  if (document.getElementById("delivery").checked) search.set("delivery", "true");
  if (document.getElementById("pickup").checked) search.set("pickup", "true");
  search.set("page", state.page);
  search.set("per_page", state.perPage);
  return search;
}

function text(value) {
  return value === null || value === undefined || value === "" ? "-" : value;
}

function link(label, url) {
  if (!url) return "";
  return `<a href="${url}" target="_blank" rel="noopener">${label}</a>`;
}

async function load() {
  const status = document.getElementById("status");
  status.textContent = "Loading";
  try {
    const query = params();
    const response = await fetch(`/api/producers?${query.toString()}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.total = data.total;
    document.getElementById("result-count").textContent = `${data.total} qualified producers`;
    document.getElementById("rows").innerHTML = data.items.map((item) => `
      <tr>
        <td><strong>${text(item.farm_name)}</strong><div class="reason">${text(item.classification_reason)}</div></td>
        <td>${text([item.city, item.county, item.state].filter(Boolean).join(", "))}</td>
        <td>${text(item.products)}</td>
        <td>${text(item.destination_type)}</td>
        <td>${text(item.platform_detected)}</td>
        <td>${Math.round(item.confidence_score)}</td>
        <td>${link("Listing", item.source_listing_url)} ${link("Order", item.buy_online_url || item.website_url)}</td>
      </tr>
    `).join("");
    document.getElementById("page-label").textContent = `Page ${state.page}`;
    document.getElementById("prev").disabled = state.page === 1;
    document.getElementById("next").disabled = state.page * state.perPage >= state.total;
    document.getElementById("export").href = `/export?${query.toString()}`;
    status.textContent = "";
  } catch (error) {
    status.textContent = `Error: ${error.message}`;
  }
}

document.getElementById("apply").addEventListener("click", () => {
  state.page = 1;
  load();
});
document.getElementById("prev").addEventListener("click", () => {
  if (state.page > 1) {
    state.page -= 1;
    load();
  }
});
document.getElementById("next").addEventListener("click", () => {
  state.page += 1;
  load();
});
for (const id of fields) {
  document.getElementById(id).addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      state.page = 1;
      load();
    }
  });
}
load();
