let lastLoadedEmails = [];

async function loadInbox() {
  const category = document.getElementById("category-filter")?.value || "All";
  const search = document.getElementById("email-search")?.value || "";
  const params = new URLSearchParams();
  if (category && category !== "All") params.set("category", category);
  if (search) params.set("search", search);
  params.set("page_size", "1000");
  const payload = await apiGet(`/api/emails${params.toString() ? `?${params}` : ""}`);
  lastLoadedEmails = payload.items;
  renderInbox(payload.items, category, payload.total);
}

function renderInbox(emails, category, total) {
  const list = document.getElementById("email-list");
  if (!list) return;
  list.innerHTML = emails
    .map(
      (email) => `
      <div class="email-row p-4 hover:bg-gold/10 transition cursor-pointer flex items-center justify-between group" data-category="${escapeHtml(email.category)}" onclick="openEmailDetail('${escapeHtml(email.email_id)}')">
        <div class="flex items-center space-x-4 min-w-0">
          <div class="w-10 h-10 rounded-xl bg-navy text-gold font-extrabold flex items-center justify-center shrink-0 border gold-border group-hover:scale-105 transition-transform shadow-sm">${escapeHtml(initials(email.sender))}</div>
          <div class="min-w-0">
            <div class="flex items-center space-x-2">
              <h4 class="theme-text-main font-bold text-sm text-navy truncate">${escapeHtml(email.sender || "Unknown sender")}</h4>
              <span class="px-2.5 py-0.5 ${categoryBadge(email.category)} text-[10px] font-extrabold rounded-md uppercase tracking-wide">${escapeHtml(email.category)}</span>
            </div>
            <p class="theme-text-sub font-bold text-xs text-navy/90 truncate mt-0.5">${escapeHtml(email.subject)}</p>
            <p class="theme-text-muted text-xs text-navy/60 truncate">${escapeHtml(email.preview)}</p>
          </div>
        </div>
        <div class="flex items-center ml-4 shrink-0 space-x-2">
          <span class="text-[10px] font-mono text-navy/50">${Math.round((email.confidence || 0) * 100)}%</span>
          <select data-email-id="${escapeHtml(email.email_id)}" onchange="changeEmailCategory(this)" class="px-2 py-1.5 bg-navy text-ivory text-[10px] font-bold rounded-lg border gold-border focus:outline-none opacity-0 group-hover:opacity-100 transition cursor-pointer shadow-sm hover:ring-2 hover:ring-gold/50">
            <option value="" disabled selected>Move to...</option>
            <option value="Comparison requests">Comparison</option>
            <option value="New SI requests">New SI</option>
            <option value="Invoice queries">Invoice</option>
            <option value="General mail">General</option>
            <option value="Spam">Spam</option>
          </select>
        </div>
      </div>`
    )
    .join("") || `<div class="p-10 text-center text-xs text-navy/50">No emails found.</div>`;

  const showing = document.getElementById("showing-count");
  if (showing) {
    showing.innerText =
      category === "All" ? `Showing ${emails.length} of ${total} emails` : `Showing ${total} email(s) in "${category}"`;
  }
}

function filterByCategory(category) {
  const select = document.getElementById("category-filter");
  if (select) select.value = category;
  switchView("inbox");
  loadInbox();
}

function searchEmails() {
  loadInbox();
}

function applyFilters() {
  loadInbox();
}

function openEmailDetail(emailId) {
  const email = lastLoadedEmails.find((entry) => entry.email_id === emailId);
  if (!email) return;
  const setText = (id, value) => {
    const node = document.getElementById(id);
    if (node) node.innerText = value || "—";
  };
  setText("ed-sender", email.sender || "Unknown sender");
  setText("ed-subject", email.subject || "(no subject)");
  setText("ed-received", formatReceived(email.received_time));
  setText("ed-category", email.category || "Uncategorized");
  const body = document.getElementById("ed-body");
  if (body) body.innerText = email.body || email.preview || "(No message body available for this email.)";
  const attachments = document.getElementById("ed-attachments");
  if (attachments) {
    const files = Array.isArray(email.attachments) ? email.attachments : [];
    attachments.innerText = files.length ? `Attachments: ${files.map((f) => f.split(/[\\/]/).pop()).join(", ")}` : "No attachments";
  }
  openModal("email-detail-modal");
}

async function changeEmailCategory(selectElement) {
  const emailId = selectElement.dataset.emailId;
  const category = selectElement.value;
  if (!emailId || !category) return;
  try {
    await apiPost(`/api/emails/${encodeURIComponent(emailId)}/move`, { category });
    await loadInbox();
    await updateDashboardSummary();
  } catch (error) {
    alert(`Could not move email: ${error.message}`);
  }
}
