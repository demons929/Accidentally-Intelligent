let lastLoadedEmails = [];
let inboxPage = 1;
const PAGE_SIZE = 50;

async function loadInbox() {
  const category = document.getElementById("category-filter")?.value || "All";
  const search = document.getElementById("email-search")?.value || "";
  const params = new URLSearchParams();
  if (category && category !== "All") params.set("category", category);
  if (search) params.set("search", search);
  params.set("page_size", "1000");
  const payload = await apiGet(`/api/emails${params.toString() ? `?${params}` : ""}`);
  lastLoadedEmails = payload.items;
  inboxPage = 1;
  renderInbox(lastLoadedEmails, category, payload.total);
}

function renderInbox(emails, category, total) {
  const list = document.getElementById("email-list");
  if (!list) return;

  const pageCount = Math.max(1, Math.ceil(emails.length / PAGE_SIZE));
  if (inboxPage > pageCount) inboxPage = pageCount;
  const start = (inboxPage - 1) * PAGE_SIZE;
  const pageItems = emails.slice(start, start + PAGE_SIZE);

  list.innerHTML = pageItems
    .map(
      (email) => `
      <div class="email-row p-4 hover:bg-gold/10 transition cursor-pointer flex items-center justify-between group" data-category="${escapeHtml(email.category)}" onclick="openEmailDetail('${escapeHtml(email.email_id)}')">
        <div class="flex items-center space-x-3 min-w-0">
          ${email.category === "Spam" ? `<input type="checkbox" class="spam-check accent-rose-600 w-4 h-4 shrink-0" onclick="event.stopPropagation(); refreshSpamToolbar()" data-email-id="${escapeHtml(email.email_id)}">` : ""}
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
          ${email.category === "Spam" ? `<button onclick="event.stopPropagation(); deleteSpamEmail('${escapeHtml(email.email_id)}')" class="px-2 py-1.5 bg-rose-700 hover:bg-rose-800 text-white text-[10px] font-bold rounded-lg border border-rose-500/40 shadow-sm transition" title="Delete spam"><i class="fa-solid fa-trash"></i></button>` : ""}
        </div>
      </div>`
    )
    .join("") || `<div class="p-10 text-center text-xs text-navy/50">No emails found.</div>`;

  const showing = document.getElementById("showing-count");
  if (showing) {
    const from = emails.length ? start + 1 : 0;
    const to = Math.min(start + PAGE_SIZE, emails.length);
    showing.innerText = category === "All"
      ? `Showing ${from}-${to} of ${total} emails`
      : `Showing ${from}-${to} of ${total} in "${category}"`;
  }

  renderPager(pageCount);
}

function renderPager(pageCount) {
  let pager = document.getElementById("inbox-pager");
  if (!pager) return;
  const cur = inboxPage;
  const btn = (label, page, disabled, active) =>
    `<button onclick="goInboxPage(${page})" ${disabled || active ? "disabled" : ""}
      class="px-3 py-1.5 text-xs font-bold rounded-lg border gold-border transition
      ${active ? "bg-navy text-gold" : disabled ? "opacity-40 cursor-not-allowed bg-ivory" : "bg-white text-navy hover:bg-gold/10"}">${label}</button>`;
  let html = btn("Prev", cur - 1, cur <= 1, false);
  for (let i = 1; i <= pageCount; i++) {
    const from = (i - 1) * PAGE_SIZE + 1;
    const to = Math.min(i * PAGE_SIZE, lastLoadedEmails.length);
    html += btn(`${from}-${to}`, i, false, i === cur);
  }
  html += btn("Next", cur + 1, cur >= pageCount, false);
  pager.innerHTML = html;
}

function filterByCategory(category) {
  const select = document.getElementById("category-filter");
  if (select) select.value = category;
  if (typeof switchView === "function") switchView("inbox");
  loadInbox();
}

function goInboxPage(page) {
  inboxPage = page;
  const category = document.getElementById("category-filter")?.value || "All";
  renderInbox(lastLoadedEmails, category, lastLoadedEmails.length);
}

async function changeEmailCategory(sel) {
  const id = sel.getAttribute("data-email-id");
  const category = sel.value;
  if (!id || !category) return;
  try {
    await apiPost(`/api/emails/${encodeURIComponent(id)}/move`, { category });
    await loadInbox();
    if (typeof loadSidebarCounts === "function") loadSidebarCounts();
  } catch (e) {
    alert("Failed to move email: " + (e.message || e));
  }
}

async function deleteSpamEmail(id) {
  if (!id) return;
  if (!confirm("Delete this spam email? This cannot be undone.")) return;
  try {
    await apiDelete(`/api/emails/${encodeURIComponent(id)}`);
    await loadInbox();
    if (typeof loadSidebarCounts === "function") loadSidebarCounts();
  } catch (e) {
    alert("Failed to delete: " + (e.message || e));
  }
}

async function deleteSelectedSpam() {
  const checks = document.querySelectorAll(".spam-check:checked");
  if (!checks.length) { alert("No spam emails selected."); return; }
  if (!confirm(`Delete ${checks.length} selected spam email(s)? This cannot be undone.`)) return;
  for (const c of checks) {
    try { await apiDelete(`/api/emails/${encodeURIComponent(c.dataset.emailId)}`); }
    catch (e) { console.error("delete failed", c.dataset.emailId, e); }
  }
  await loadInbox();
  if (typeof loadSidebarCounts === "function") loadSidebarCounts();
  refreshSpamToolbar();
}

function refreshSpamToolbar() {
  const checked = document.querySelectorAll(".spam-check:checked");
  const bar = document.getElementById("spam-selected-bar");
  const cnt = document.getElementById("spam-selected-count");
  if (!bar) return;
  if (checked.length > 0) {
    bar.classList.remove("hidden");
    bar.classList.add("flex");
    if (cnt) cnt.innerText = checked.length + " selected";
  } else {
    bar.classList.add("hidden");
    bar.classList.remove("flex");
  }
}

function openEmailDetail(emailId) {
  const email = lastLoadedEmails.find((e) => e.email_id === emailId);
  if (!email) return;
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
  set("ed-sender", email.sender || "Unknown sender");
  set("ed-received", email.received_time ? new Date(email.received_time).toLocaleString() : "—");
  set("ed-subject", email.subject || "(no subject)");
  set("ed-category", email.category || "—");
  set("ed-body", email.body || email.preview || "(no body)");
  const att = document.getElementById("ed-attachments");
  if (att) att.innerText = (email.attachments && email.attachments.length) ? "Attachments: " + email.attachments.join(", ") : "";
  openModal("email-detail-modal");
}
