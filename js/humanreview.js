
    let humanReviewCases = [
        {
            id: 1,
            type: "unreadable",
            status: "pending"
        },
        {
            id: 2,
            type: "corrupted",
            status: "pending"
        },
        {
            id: 3,
            type: "corrupted",
            status: "pending"
        },
        {
            id: 4,
            type: "unreadable",
            status: "resolved"
        },
        {
            id: 5,
            type: "unreadable",
            status: "resolved"
        },
        {
            id: 6,
            type: "corrupted",
            status: "resolved"
        },
        {
            id: 7,
            type: "corrupted",
            status: "resolved"
        }
    ];


    function updateHumanReviewCounts() {

        const unreadableCount = humanReviewCases.filter(
            item => item.type === "unreadable" && item.status === "pending"
        ).length;

        const corruptedCount = humanReviewCases.filter(
            item => item.type === "corrupted" && item.status === "pending"
        ).length;

        const resolvedCount = humanReviewCases.filter(
            item => item.status === "resolved"
        ).length;


        document.getElementById("unreadable-count").innerText = unreadableCount;

        document.getElementById("corrupted-count").innerText = corruptedCount;

        document.getElementById("resolved-count").innerText = resolvedCount;
    
        document.getElementById("total-review-count").innerText =
        unreadableCount + corruptedCount + resolvedCount;

        document.getElementById("summary-unreadable-count").innerText =
        unreadableCount;

        document.getElementById("summary-corrupted-count").innerText =
        corruptedCount;

        document.getElementById("summary-resolved-count").innerText =
        resolvedCount;
    }


    updateHumanReviewCounts();
    function resolveHumanReviewCase(id) {
    const caseItem = humanReviewCases.find(item => item.id === id);

    if (caseItem) {
        caseItem.status = "resolved";

        updateHumanReviewCounts();
        const row = document.getElementById("unreadable-case-" + id);

        if (row) {
            row.remove();
        }

        alert("Case marked as Resolved.");
        switchReviewSubPage("resolved-list");
        }
    }

    function requestNewAttachment(id) {
    const caseItem = humanReviewCases.find(item => item.id === id);

    if (caseItem) {
        caseItem.status = "waiting";

        alert("New attachment request sent to sender.");
        switchReviewSubPage("dashboard");
        }
    }

    function requestResend(id) {
    const caseItem = humanReviewCases.find(item => item.id === id);

    if (caseItem) {
        caseItem.status = "waiting";

        alert("Resend request issued to sender.");
        switchReviewSubPage("dashboard");
        }
    }