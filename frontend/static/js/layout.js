/* ==========================================================================
 * HarryPort shared layout — sidebar + topbar + common modals.
 * Loaded on every app page. Renders chrome into #hp-sidebar / #hp-topbar
 * placeholders and provides the shared nav / modal helpers.
 * ========================================================================== */
(function () {
  const isComparison = location.pathname.includes("Comparison.html");

  /* ---------- routing adapts to current page ---------- */
  window.hpNav = {
    inbox() {
      if (isComparison) location.href = "/frontpage.html";
      else switchView("inbox");
    },
    review() {
      if (isComparison) location.href = "/frontpage.html?view=review";
      else switchReviewSubPage("dashboard");
    },
    compare() {
      if (!isComparison) location.href = "/Comparison.html";
    },
    category(cat) {
      if (isComparison) location.href = "/frontpage.html?category=" + encodeURIComponent(cat);
      else filterByCategory(cat);
    },
  };

  /* ---------- sidebar ---------- */
  function sidebarHtml(active) {
    const navBtn = (id, label, icon, handler, extra) => `
      <button onclick="${handler}" id="${id}" class="w-full flex items-center p-2.5 ${active === id ? "gold-active-nav font-bold" : "text-ivory/80 hover:text-ivory hover:bg-navy-light/50 font-semibold"} rounded-xl transition">
        <i class="fa-solid ${icon} w-6 text-center gold-text"></i>
        <span class="sidebar-text ml-3 text-sm whitespace-nowrap">${label}</span>
        ${extra || ""}
      </button>`;

    const cat = (id, label, dot, countId) => `
      <li onclick="hpNav.category('${label}')" class="flex items-center justify-between text-sm text-ivory/90 p-2 hover:bg-navy-light/60 hover:text-gold rounded-lg cursor-pointer transition group">
        <div class="flex items-center min-w-0">
          <span class="w-2.5 h-2.5 rounded-full ${dot} shrink-0 mr-3 shadow-sm group-hover:scale-110 transition-transform"></span>
          <span class="sidebar-text font-medium text-xs whitespace-nowrap truncate">${label}</span>
        </div>
        <span id="${countId}" class="sidebar-text text-xs font-bold bg-navy-light border gold-border text-gold px-2 py-0.5 rounded-full min-w-[22px] text-center">0</span>
      </li>`;

    return `
      <div>
        <div class="h-16 flex items-center px-4 border-b gold-border justify-between bg-navy-dark/40">
          <div class="flex items-center space-x-3 overflow-hidden">
            <img src="/resources/image/logo.png" alt="HarryPort Logo"
                 onerror="this.onerror=null; this.src='https://cdn-icons-png.flaticon.com/512/2942/2942544.png';"
                 class="h-9 w-9 object-contain shrink-0 filter drop-shadow-md">
            <span id="brand-text" class="font-extrabold text-lg text-ivory tracking-wide whitespace-nowrap">Harry<span class="gold-text">Port</span></span>
          </div>
        </div>

        <nav class="p-3 space-y-1.5">
          ${navBtn("nav-inbox", "Inbox", "fa-inbox", "hpNav.inbox()")}
          ${navBtn("nav-review", "Human Review", "fa-triangle-exclamation", "hpNav.review()",
            '<span id="review-badge" class="sidebar-text ml-auto gold-gradient text-navy-dark text-xs font-black py-0.5 px-2 rounded-full shadow-sm">0</span>')}
          ${navBtn("nav-comparison", "Compare", "fa-scale-balanced", "hpNav.compare()",
            '<i class="fa-solid fa-arrow-up-right-from-square sidebar-text ml-auto text-[10px] text-gold/70"></i>')}
        </nav>

        <div class="px-3 py-2 mt-2">
          <div class="flex items-center justify-between px-2 mb-2">
            <p class="sidebar-text text-[11px] font-extrabold gold-text uppercase tracking-widest">Categories</p>
          </div>
          <ul class="space-y-1">
            ${cat("sidebar-count-comparison", "Comparison requests", "bg-gold", "sidebar-count-comparison")}
            ${cat("sidebar-count-si", "New SI requests", "bg-amber-400", "sidebar-count-si")}
            ${cat("sidebar-count-invoice", "Invoice queries", "bg-amber-600", "sidebar-count-invoice")}
            ${cat("sidebar-count-general", "General mail", "bg-slate-400", "sidebar-count-general")}
            ${cat("sidebar-count-spam", "Spam", "bg-rose-500", "sidebar-count-spam")}
          </ul>
        </div>
      </div>

      <div class="p-3 border-t gold-border space-y-1 bg-navy-dark/30">
        <button onclick="openModal('settings-modal')" class="w-full flex items-center p-2 text-ivory/80 hover:text-gold hover:bg-navy-light/50 rounded-lg transition">
          <i class="fa-solid fa-gear w-6 text-center gold-text"></i>
          <span class="sidebar-text ml-3 text-sm font-semibold whitespace-nowrap">Settings</span>
        </button>
        <button onclick="openModal('logout-modal')" class="w-full flex items-center p-2 text-rose-300 hover:text-rose-200 hover:bg-rose-950/40 rounded-lg transition">
          <i class="fa-solid fa-arrow-right-from-bracket w-6 text-center"></i>
          <span class="sidebar-text ml-3 text-sm font-semibold whitespace-nowrap">Log Out</span>
        </button>
      </div>`;
  }

  /* ---------- topbar ---------- */
  function topbarHtml(title, subtitle) {
    return `
      <div class="flex items-center space-x-4">
        <button onclick="toggleSidebar()" class="text-ivory/80 hover:text-gold p-2 rounded-lg hover:bg-navy-light/50 transition">
          <i class="fa-solid fa-bars text-lg"></i>
        </button>
        <div class="flex items-center space-x-3">
          <h1 id="page-title" class="font-extrabold text-lg text-ivory tracking-wide">${title}</h1>
          <span class="hidden md:inline-block text-xs font-semibold px-2.5 py-0.5 rounded-full border gold-border text-gold bg-navy-light">${subtitle || "HarryPort Operations"}</span>
        </div>
      </div>
      <div class="flex items-center space-x-4">
        <button class="p-2 text-ivory/80 hover:text-gold"><i class="fa-solid fa-bell text-lg"></i></button>
        <div class="h-6 w-px bg-gold/20"></div>
        <div onclick="openProfileModal()" class="flex items-center space-x-3 cursor-pointer p-1.5 rounded-xl hover:bg-navy-light/50 transition border border-transparent hover:border-gold/30">
          <div id="header-avatar" class="w-9 h-9 rounded-xl gold-gradient text-navy-dark flex items-center justify-center font-black text-sm shadow-md border border-ivory/20">C</div>
          <div class="hidden sm:block">
            <p id="header-user-name" class="text-xs font-bold text-ivory leading-none">Captain</p>
            <p id="header-user-role" class="text-[10px] text-gold font-medium mt-0.5">Port Administrator</p>
          </div>
        </div>
      </div>`;
  }

  /* ---------- profile + logout modals ---------- */
  function modalsHtml() {
    return `
    <div id="profile-modal" class="hidden fixed inset-0 bg-navy/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div class="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 space-y-4 border gold-border relative">
        <div class="flex items-center justify-between border-b gold-border pb-3">
          <h3 class="font-extrabold text-navy text-base"><i class="fa-solid fa-user gold-text mr-2"></i>User Profile</h3>
          <button onclick="closeModal('profile-modal')" class="text-navy/50 hover:text-gold"><i class="fa-solid fa-xmark text-lg"></i></button>
        </div>
        <div class="flex items-center space-x-4">
          <div id="profile-avatar" class="w-16 h-16 rounded-2xl gold-gradient text-navy-dark flex items-center justify-center font-black text-2xl">C</div>
          <div class="min-w-0">
            <p id="profile-name" class="font-extrabold text-navy text-lg leading-tight">&mdash;</p>
            <p id="profile-role" class="text-xs gold-text font-bold mt-0.5">&mdash;</p>
            <p id="profile-email" class="text-[11px] text-navy/60 mt-0.5 truncate">&mdash;</p>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-3 text-xs">
          <div class="bg-ivory rounded-xl border gold-border p-3"><p class="text-navy/50 font-bold uppercase text-[10px]">Job Title</p><p id="profile-job-title" class="font-bold text-navy mt-0.5">&mdash;</p></div>
          <div class="bg-ivory rounded-xl border gold-border p-3"><p class="text-navy/50 font-bold uppercase text-[10px]">Department</p><p id="profile-department" class="font-bold text-navy mt-0.5">&mdash;</p></div>
        </div>
        <button onclick="closeModal('profile-modal')" class="w-full py-2.5 gold-gradient text-navy-dark font-black text-xs rounded-xl">Close</button>
      </div>
    </div>
    <div id="settings-modal" class="hidden fixed inset-0 bg-navy/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div class="bg-white rounded-2xl shadow-2xl max-w-sm w-full p-6 space-y-4 border gold-border">
        <div class="flex items-center justify-between border-b gold-border pb-3">
          <h3 class="font-extrabold text-navy text-base"><i class="fa-solid fa-gear gold-text mr-2"></i>Settings</h3>
          <button onclick="closeModal('settings-modal')" class="text-navy/50 hover:text-gold"><i class="fa-solid fa-xmark text-lg"></i></button>
        </div>
        <div class="flex items-center justify-between">
          <span class="text-sm font-bold text-navy">Dark Mode</span>
          <button id="hp-theme-switch" onclick="toggleTheme(); syncThemeSwitch()" class="relative w-28 h-10 rounded-full bg-white border gold-border shadow transition-colors duration-300 flex items-center px-1.5" aria-label="Toggle dark mode">
            <span id="hp-theme-label" class="text-xs font-extrabold text-navy/40 ml-1 select-none">OFF</span>
            <span id="hp-theme-knob" class="absolute right-1 w-8 h-8 rounded-full gold-gradient shadow flex items-center justify-center transition-all duration-300">
              <i class="fa-solid fa-moon text-navy-dark text-xs"></i>
            </span>
          </button>
        </div>
        <button onclick="closeModal('settings-modal')" class="w-full py-2.5 gold-gradient text-navy-dark font-black text-xs rounded-xl">Close</button>
      </div>
    </div>
    <div id="logout-modal" class="hidden fixed inset-0 bg-navy/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div class="bg-white rounded-2xl shadow-2xl max-w-sm w-full p-6 text-center space-y-4 border gold-border">
        <div class="w-12 h-12 bg-rose-100 text-rose-700 rounded-full flex items-center justify-center text-xl mx-auto border border-rose-200"><i class="fa-solid fa-right-from-bracket"></i></div>
        <div><h3 class="font-extrabold text-navy text-base">Confirm Logout</h3><p class="text-xs text-navy/60 mt-1">Are you sure you want to exit your HarryPort session?</p></div>
        <div class="flex space-x-3">
          <button onclick="closeModal('logout-modal')" class="flex-1 py-2.5 bg-ivory text-navy font-bold text-xs rounded-xl border gold-border">Cancel</button>
          <button onclick="signOut()" class="flex-1 py-2.5 bg-rose-700 hover:bg-rose-800 text-white font-bold text-xs rounded-xl shadow">Log Out</button>
        </div>
      </div>
    </div>`;
  }

  /* ---------- mount ---------- */
  window.syncThemeSwitch = function () {
  const dark = document.body.classList.contains("dark-mode");
  const sw = document.getElementById("hp-theme-switch");
  const label = document.getElementById("hp-theme-label");
  const knob = document.getElementById("hp-theme-knob");
  if (!sw || !label || !knob) return;
  if (dark) {
    sw.classList.remove("bg-white"); sw.classList.add("bg-slate-800");
    label.innerText = "ON"; label.classList.remove("text-navy/40"); label.classList.add("text-white/70");
    knob.style.right = "auto"; knob.style.left = "calc(100% - 2.25rem)";
    knob.innerHTML = '<i class="fa-solid fa-moon text-navy-dark text-sm"></i>';
  } else {
    sw.classList.add("bg-white"); sw.classList.remove("bg-slate-800");
    label.innerText = "OFF"; label.classList.add("text-navy/40"); label.classList.remove("text-white/70");
    knob.style.right = "0.25rem"; knob.style.left = "auto";
    knob.innerHTML = '<i class="fa-solid fa-sun text-navy-dark text-sm"></i>';
  }
};
window.selectTheme = function (dark) { if (typeof applyTheme === "function") { applyTheme(dark); syncThemeSwitch(); } };
  window.mountLayout = function ({ active = "inbox", title = "Inbox", subtitle } = {}) {
    const map = { inbox: "nav-inbox", review: "nav-review", comparison: "nav-comparison" };
    active = map[active] || active;
    const sb = document.getElementById("hp-sidebar");
    if (sb) { sb.innerHTML = sidebarHtml(active); sb.id = "sidebar"; sb.className = "w-64 bg-navy text-ivory flex flex-col justify-between h-full border-r gold-border shrink-0 relative z-20 shadow-xl transition-all duration-300"; }
    const tb = document.getElementById("hp-topbar");
    if (tb) { tb.innerHTML = topbarHtml(title, subtitle); }
    const modals = document.getElementById("hp-modals");
    if (modals) modals.innerHTML = modalsHtml();
  };
})();
