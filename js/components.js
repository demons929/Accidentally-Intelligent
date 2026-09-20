document.addEventListener("DOMContentLoaded", function () {
    fetch("components/header.html")
        .then(response => response.text())
        .then(data => {
            document.getElementById("header-container").innerHTML = data;
        })
        .catch(error => {
            console.error("Error loading header:", error);
        });
    
        // Load Sidebar
    fetch("components/sidebar.html")
        .then(response => response.text())
        .then(data => {
            document.getElementById("sidebar-container").innerHTML = data;

        // Update sidebar numbers after sidebar is loaded
            updateCategoryCounts();
         // Set Inbox as default active
            updateSidebarActive("nav-inbox");
        })
        .catch(error => {
        console.error("Error loading sidebar:", error);
    });

    fetch("components/profile.html")
        .then(response => response.text())
        .then(data => {
            document.getElementById("profile-container").innerHTML = data;
        })
        .catch(error => {
        console.error("Error loading profile:", error);
        });
    
    fetch("components/logout.html")
    .then(response => response.text())
    .then(data => {
        document.getElementById("logout-container").innerHTML = data;
    })
    .catch(error => {
        console.error("Error loading logout:", error);
    });

    fetch("inbox.html")
    .then(response => response.text())
    .then(data => {
        document.getElementById("inbox-container").innerHTML = data;

        // Update category counts after Inbox has loaded
        updateCategoryCounts();
    })
    .catch(error => {
        console.error("Error loading inbox:", error);
    });

    fetch("humanreview.html")
    .then(response => response.text())
    .then(data => {
        document.getElementById("humanreview-container").innerHTML = data;
    })
    .catch(error => {
        console.error("Error loading human review:", error);
    });

    fetch("spam.html")
    .then(response => response.text())
    .then(data => {
        document.getElementById("spam-container").innerHTML = data;
        updateCategoryCounts();
        applySpamSearch();
    });
});

function updateSidebarActive(activeId) {

    const navItems = [
        "nav-inbox",
        "nav-review",
        "nav-comparison",
        "nav-si",
        "nav-invoice",
        "nav-general",
        "nav-spam"
    ];

    // Remove active state from ALL items
    navItems.forEach(id => {
        const item = document.getElementById(id);

        if (item) {
            item.classList.remove("gold-active-nav");
            item.classList.remove("sidebar-active-gold");
            item.classList.remove("sidebar-active-red");
        }
    });

    // Add active state to selected item
    const activeItem = document.getElementById(activeId);

    if (activeItem) {
            activeItem.classList.add("sidebar-active-gold");
        }
    }
function openModal(id) {
    document.getElementById(id).classList.remove('hidden');
}

function closeModal(id) {
    document.getElementById(id).classList.add('hidden');
}

function openLogoutModal() {
    closeModal('profile-modal');
    openModal('logout-modal');
}
function closeLogoutModal() {
    closeModal('logout-modal');
    openModal('profile-modal');
}
function confirmLogout() {
    window.location.href = "login.html";
}