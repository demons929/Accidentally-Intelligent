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