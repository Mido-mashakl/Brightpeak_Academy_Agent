let bpCurrentType = "all";

document.addEventListener("DOMContentLoaded", async () => {
  bpRenderNav({ active: "requests", searchPlaceholder: "Search requests..." });

  document.querySelectorAll(".bp-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".bp-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      bpCurrentType = tab.dataset.type;
      loadRequests();
    });
  });

  await loadRequests();
});

async function loadRequests() {
  const { items, total } = await bpFetchRequests({ type: bpCurrentType });

  document.getElementById("bp-requests-body").innerHTML = items
    .map((r) => {
      const meta = BP_STATUS_META[r.status];
      return `
        <tr>
          <td class="bp-row-id">${r.id}</td>
          <td>${r.student}</td>
          <td>${r.type}</td>
          <td><span class="bp-badge ${meta.badgeClass}">${meta.label}</span></td>
          <td class="bp-muted">${r.updated}</td>
          <td>
            <a class="bp-action-btn" href="request-detail.html?id=${r.id}" title="View request">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
              </svg>
            </a>
          </td>
        </tr>`;
    })
    .join("");

  document.getElementById("bp-showing").textContent = `Showing 1 to ${items.length} of ${total} requests`;

  // The backend returns the full queue in one response (no server-side
  // pagination exists yet), so there is only ever one real page here —
  // showing a fake multi-page control would misrepresent that.
  document.getElementById("bp-pagination").innerHTML =
    `<button class="bp-page-btn active">1</button>`;
}