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
