/* Human Review — unified "all cases" view (pending + resolved). */

let currentReviewCases = [];
let currentReview = null;

async function loadHumanReview() {
  currentReviewCases = await apiGet("/api/human-review?include_resolved=true");
  renderHumanReviewTable();
}

function reviewTypeLabel(type) {
  return type === "unreadable" ? "Unreadable Attachment" : "Corrupted Email";
}

function reviewTypeBadge(type) {
  return type === "unreadable"
    ? "bg-amber-100 text-amber-900 border border-amber-300"
    : "bg-rose-100 text-rose-800 border border-rose-300";
}

function setHumanReviewFilter() {
  /* Buttons removed; both tables render every load. Kept as a no-op so old
     inline calls do not error. */
  renderHumanReviewTable();
}

function reviewRowHtml(item) {
  return `
      <tr class="hover:bg-ivory-light/80 transition">
        <td class="p-3.5 font-bold">${escapeHtml(item.sender || "Unknown sender")}</td>
        <td class="p-3.5 font-semibold text-navy/90">${escapeHtml(item.subject)}</td>
        <td class="p-3.5"><span class="px-2.5 py-0.5 ${reviewTypeBadge(item.review_type)} rounded-md font-bold text-[10px] whitespace-nowrap">${reviewTypeLabel(item.review_type)}</span></td>
        <td class="p-3.5 font-mono text-navy/60">${escapeHtml(item.email_id)}</td>
        <td class="p-3.5"><span class="px-2.5 py-0.5 ${item.is_resolved ? "bg-emerald-100 text-emerald-800 border border-emerald-300" : "bg-amber-100 text-amber-900 border border-amber-300"} rounded-md font-bold text-[10px]">${item.is_resolved ? "Resolved" : "Pending Review"}</span></td>
        <td class="p-3.5 text-right">
          <button onclick="openReviewDetail('${escapeHtml(item.email_id)}')" class="px-3 py-1.5 ${item.is_resolved ? "bg-navy text-gold border gold-border hover:bg-navy-light" : "gold-gradient text-navy-dark"} font-extrabold text-xs rounded-lg shadow-sm whitespace-nowrap transition">${item.is_resolved ? "View" : "Open Review"}</button>
        </td>
      </tr>`;
}

function emptyRowHtml(message) {
  return `<tr><td colspan="6" class="p-10 text-center text-xs text-navy/50">${message}</td></tr>`;
}

function renderHumanReviewTable() {
  const pendingCount = currentReviewCases.filter((c) => !c.is_resolved).length;
  const resolvedCount = currentReviewCases.filter((c) => c.is_resolved).length;
  const chipPending = document.getElementById("hr-chip-pending");
  const chipResolved = document.getElementById("hr-chip-resolved");
  if (chipPending) chipPending.innerText = pendingCount;
  if (chipResolved) chipResolved.innerText = resolvedCount;

  // Table 1: every human review case (pending + resolved)
  const allTbody = document.getElementById("hr-all-tbody");
  const showing = document.getElementById("hr-showing-count");
  if (showing) showing.innerText = `${currentReviewCases.length} cases total`;
  if (allTbody) {
    allTbody.innerHTML = currentReviewCases.length
      ? currentReviewCases.map(reviewRowHtml).join("")
      : emptyRowHtml("No human review cases.");
  }

  // Table 2: reviewed (resolved) files only
  const reviewedTbody = document.getElementById("hr-reviewed-tbody");
  const reviewedCount = document.getElementById("hr-reviewed-count");
  if (reviewedCount) reviewedCount.innerText = `${resolvedCount} reviewed`;
  if (reviewedTbody) {
    const resolvedRows = currentReviewCases.filter((c) => c.is_resolved);
    reviewedTbody.innerHTML = resolvedRows.length
      ? resolvedRows.map(reviewRowHtml).join("")
      : emptyRowHtml("No reviewed files yet. Resolved cases will appear here.");
  }
}

/* ------------------------------------------------------------------ */
/* Detail view: populated from the API row, confirm resolves the case  */
/* ------------------------------------------------------------------ */

function openReviewDetail(emailId) {
  const item = currentReviewCases.find((entry) => entry.email_id === emailId);
  if (!item) return;
  currentReview = item;

  const type = item.review_type === "unreadable" ? "unreadable" : "corrupted";
  switchReviewSubPage(`${type}-detail`);

  const setText = (id, value) => {
    const node = document.getElementById(id);
    if (node) node.innerText = value;
  };
  // Both the unreadable (base ids) and corrupted (`-c` ids) detail layouts
  // are populated so the same handler works for either type.
  setText("detail-sender", item.sender || "Unknown sender");
  setText("detail-subject", item.subject || "(no subject)");
  setText("detail-attachment", (item.attachments || []).join(", ") || item.review_type || "—");
  const bodyNode = document.getElementById("detail-body");
  if (bodyNode) {
    const bodyText = (item.body || "").trim();
    if (bodyText) {
      bodyNode.innerText = bodyText;
      bodyNode.classList.remove("hidden");
    } else {
      bodyNode.classList.add("hidden");
    }
  }
  setText("detail-issue", item.error || (type === "unreadable" ? "Unable to extract content" : "Parsing failed"));
  setText("detail-email-id", item.email_id);
  setText("detail-status-badge", type === "unreadable" ? "OCR_FAILED" : "PARSER_FAILED");
  setText("detail-received", formatReceived(item.received_time));
  setText("detail-sender-c", item.sender || "Unknown sender");
  setText("detail-subject-c", item.subject || "(no subject)");
  setText("detail-email-id-c", item.email_id);
  const bodyNodeC = document.getElementById("detail-body-c");
  if (bodyNodeC) {
    const bodyTextC = (item.body || "").trim();
    if (bodyTextC) {
      bodyNodeC.innerText = bodyTextC;
      bodyNodeC.classList.remove("hidden");
    } else {
      bodyNodeC.classList.add("hidden");
    }
  }
  setText("detail-received-c", formatReceived(item.received_time));
  setText("detail-error-log-c", item.error || "MIME / JSON parsing failed for this email.");

  const remarks = document.getElementById(`review-remarks-${type}`);
  if (remarks) remarks.value = "";
  const confirmBtn = document.getElementById(`btn-confirm-${type}`);
  if (confirmBtn) {
    if (item.is_resolved) {
      confirmBtn.disabled = true;
      confirmBtn.className = "w-full py-2.5 bg-emerald-600 text-white font-extrabold text-xs rounded-xl transition flex items-center justify-center cursor-default";
      confirmBtn.innerHTML = '<i class="fa-solid fa-check-circle mr-2"></i> Resolved';
      confirmBtn.removeAttribute("onclick");
    } else {
      confirmBtn.disabled = true;
      confirmBtn.className = "w-full py-2.5 bg-gray-400 text-white font-extrabold text-xs rounded-xl cursor-not-allowed transition flex items-center justify-center";
      confirmBtn.setAttribute("onclick", `handleConfirm('${type}')`);
      confirmBtn.innerHTML = '<i class="fa-solid fa-check-circle mr-2"></i> Confirm Review';
    }
  }
}

function formatReceived(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function triggerRequestNewAttachment(type) {
  if (!currentReview) return;
  alert(`Request for a new attachment has been sent to ${currentReview.sender || "the sender"}.`);
  const remarks = document.getElementById(`review-remarks-${type}`);
  if (remarks) remarks.value = remarks.value || "New attachment requested from sender.";
  checkConfirmStatus(type);
}

function checkConfirmStatus(type) {
  const remarksInput = document.getElementById(`review-remarks-${type}`);
  const remarks = remarksInput ? remarksInput.value.trim() : "";
  const confirmBtn = document.getElementById(`btn-confirm-${type}`);
  if (!confirmBtn) return;
  if (currentReview && currentReview.is_resolved) return; // resolved cases stay locked
  if (remarks.length > 0) {
    confirmBtn.disabled = false;
    confirmBtn.className = "w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-xs rounded-xl shadow transition flex items-center justify-center cursor-pointer";
  } else {
    confirmBtn.disabled = true;
    confirmBtn.className = "w-full py-2.5 bg-gray-400 text-white font-extrabold text-xs rounded-xl cursor-not-allowed transition flex items-center justify-center";
  }
}

async function handleConfirm(type) {
  if (!currentReview) return;
  const remarks = document.getElementById(`review-remarks-${type}`);
  try {
    await apiPost(`/api/human-review/${encodeURIComponent(currentReview.email_id)}/resolve`, {
      remark: remarks ? remarks.value.trim() : "",
    });
    await loadHumanReview();
    await updateDashboardSummary();
    alert("Review confirmed and case marked as resolved.");
    humanReviewFilter = "all";
    setHumanReviewFilter("all");
    switchReviewSubPage("dashboard");
  } catch (error) {
    alert(`Could not resolve case: ${error.message}`);
  }
}

async function resolveHumanReviewCase(emailId) {
  await apiPost(`/api/human-review/${emailId}/resolve`);
  await loadHumanReview();
  await updateDashboardSummary();
  renderHumanReviewTable();
  switchReviewSubPage("dashboard");
}

function requestNewAttachment() {
  triggerRequestNewAttachment(currentReview ? currentReview.review_type || "unreadable" : "unreadable");
}

function requestResend() {
  alert("Resend request logged for manual follow-up.");
}
