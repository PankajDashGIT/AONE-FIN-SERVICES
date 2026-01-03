(function () {

const form = document.getElementById("ledger_filters");

/* AUTO SUBMIT FILTERS */
["led_brand","led_category","led_section","led_size","led_supplier"]
.forEach(id => {
    const el = document.getElementById(id);
    el && el.addEventListener("change", () => form.submit());
});

/* EXPAND / COLLAPSE SINGLE */
document.addEventListener("click", function (e) {
    if (!e.target.classList.contains("toggle-details")) return;

    const btn = e.target;
    const id = btn.dataset.stockId;
    const row = document.getElementById(`details-${id}`);
    const content = document.getElementById(`details-content-${id}`);

    if (row.style.display === "table-row") {
        row.style.display = "none";
        btn.textContent = "+";
        return;
    }

    row.style.display = "table-row";
    btn.textContent = "-";

    // Load only once
    if (content.dataset.loaded) return;

    fetch(`/ledger/details/${id}/`)
        .then(r => r.json())
        .then(d => {
            const profitVal = parseFloat(d.profit);
const profitText = isNaN(profitVal) ? "-" : profitVal.toFixed(2);

let cls = "text-secondary";
if (!isNaN(profitVal)) {
    if (profitVal > 0) cls = "text-success";
    else if (profitVal < 0) cls = "text-danger";
}

content.innerHTML = `
    <table class="table table-sm mb-0">
        <tr><th>Purchase Date</th><td>${d.purchase_date}</td></tr>
        <tr><th>Purchase Price</th><td>₹ ${d.purchase_price}</td></tr>
        <tr><th>Sale Date</th><td>${d.sale_date}</td></tr>
        <tr><th>Sale Price</th><td>₹ ${d.sale_price}</td></tr>
        <tr><th>Sale Invoice No</th><td>₹ ${d.sale_invoice}</td></tr>
        <tr>
            <th>Profit</th>
            <td class="${cls}">₹ ${profitText}</td>
        </tr>
    </table>
`;
            content.dataset.loaded = "1";
        });
});


/* EXPAND ALL */
document.getElementById("expandAll")?.addEventListener("click", () => {
    document.querySelectorAll(".toggle-details").forEach(btn => {
        const id = btn.dataset.stockId;
        const row = document.getElementById(`details-${id}`);
        if (row.style.display !== "table-row") btn.click();
    });
});

/* collapseAll */
document.getElementById("collapseAll")?.addEventListener("click", () => {
    document.querySelectorAll(".toggle-details").forEach(btn => {
        const id = btn.dataset.stockId;
        const row = document.getElementById(`details-${id}`);
        if (row.style.display === "table-row") btn.click();
    });
});


})();
