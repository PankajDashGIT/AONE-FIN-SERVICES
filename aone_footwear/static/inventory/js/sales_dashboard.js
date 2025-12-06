console.log("sales_dashboard.js loaded");

let currentPage = 1;
let currentPageSize = 10;
let currentStartDate = "";
let currentEndDate = "";
let currentSearch = "";

// ----------------------- helpers -----------------------

function formatMoney(val) {
    const num = parseFloat(val || 0);
    return num.toFixed(2);
}

function loadDashboard() {
    const params = new URLSearchParams({
        page: currentPage,
        page_size: currentPageSize,
        start_date: currentStartDate,
        end_date: currentEndDate,
        search: currentSearch,
    });

    fetch(`/api/sales/dashboard-data/?${params.toString()}`)
        .then(res => res.json())
        .then(data => {
            updateKPIs(data.kpis);
            updatePayments(data.payments);
            updateBestSelling(data.best_selling);
            updateTable(data.table);
            updateMeta(data.meta);
        })
        .catch(err => {
            console.error("Dashboard load error", err);
        });
}

function updateKPIs(kpis) {
    document.getElementById("kpi_today_sales").innerText = formatMoney(kpis.today_sales);
    document.getElementById("kpi_last7_sales").innerText = formatMoney(kpis.last_7_sales);
    document.getElementById("kpi_total_sales").innerText = formatMoney(kpis.total_sales);
    document.getElementById("kpi_total_qty").innerText = kpis.total_qty || 0;
}

function updatePayments(payments) {
    const container = document.getElementById("payment_modes_container");
    container.innerHTML = "";

    if (!payments || payments.length === 0) {
        container.innerHTML = `<div class="text-muted small">No sales yet.</div>`;
        return;
    }

    const total = payments.reduce((sum, p) => sum + (p.amount || 0), 0) || 1;

    payments.forEach(p => {
        const percent = (p.amount / total) * 100;
        const row = document.createElement("div");
        row.className = "mb-2";

        row.innerHTML = `
            <div class="d-flex justify-content-between">
                <span>${p.mode}</span>
                <span>₹ ${formatMoney(p.amount)}</span>
            </div>
            <div class="progress" style="height:6px;">
                <div class="progress-bar" role="progressbar"
                     style="width:${percent.toFixed(1)}%;"></div>
            </div>
        `;
        container.appendChild(row);
    });
}

function updateBestSelling(best) {
    const container = document.getElementById("best_article_container");
    container.innerHTML = "";

    if (!best) {
        container.innerHTML = `<div class="text-muted small">No sales yet.</div>`;
        return;
    }

    container.innerHTML = `
        <div class="fw-semibold mb-1">${best.name}</div>
        <div class="small text-muted mb-1">Quantity sold</div>
        <div class="h4 mb-1">${best.qty}</div>
        <div class="small text-muted">Revenue: ₹ ${formatMoney(best.amount)}</div>
    `;
}

function updateTable(table) {
    const tbody = document.getElementById("sales_table_body");
    tbody.innerHTML = "";

    if (!table.rows || table.rows.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center text-muted py-3">
                    No sales found for selected date range.
                </td>
            </tr>
        `;
    } else {
        table.rows.forEach(r => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${r.bill_no}</td>
                <td>${r.date}</td>
                <td>${r.article}</td>
                <td>${r.category}</td>
                <td>${r.size}</td>
                <td class="text-end">${r.qty}</td>
                <td class="text-end">${formatMoney(r.amount)}</td>
                <td>${r.payment}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    document.getElementById("current_page").innerText = table.page || 1;
    document.getElementById("total_pages").innerText = table.total_pages || 1;

    // Enable/disable pagination buttons
    document.getElementById("btn_prev_page").disabled = (table.page <= 1);
    document.getElementById("btn_next_page").disabled = (table.page >= table.total_pages);
}

function updateMeta(meta) {
    const text = document.getElementById("table_meta_text");
    text.innerText = `Showing sales from ${meta.start_date} to ${meta.end_date}`;
}

// ----------------------- events -----------------------

document.addEventListener("DOMContentLoaded", () => {
    // default rows per page
    const rowsSelect = document.getElementById("rows_per_page");
    currentPageSize = parseInt(rowsSelect.value, 10);

    // filter buttons
    document.getElementById("btn_apply_filter").addEventListener("click", () => {
        currentStartDate = document.getElementById("filter_start").value.trim();
        currentEndDate = document.getElementById("filter_end").value.trim();
        currentPage = 1;
        loadDashboard();
    });

    document.getElementById("btn_clear_filter").addEventListener("click", () => {
        document.getElementById("filter_start").value = "";
        document.getElementById("filter_end").value = "";
        currentStartDate = "";
        currentEndDate = "";
        currentPage = 1;
        loadDashboard();
    });

    // rows per page
    rowsSelect.addEventListener("change", () => {
        currentPageSize = parseInt(rowsSelect.value, 10);
        currentPage = 1;
        loadDashboard();
    });

    // pagination
    document.getElementById("btn_prev_page").addEventListener("click", () => {
        if (currentPage > 1) {
            currentPage -= 1;
            loadDashboard();
        }
    });

    document.getElementById("btn_next_page").addEventListener("click", () => {
        currentPage += 1;
        loadDashboard();
    });

    // search (with small delay)
    const searchBox = document.getElementById("search_box");
    let searchTimeout = null;
    searchBox.addEventListener("input", () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            currentSearch = searchBox.value.trim();
            currentPage = 1;
            loadDashboard();
        }, 400);
    });

    // export button
    document.getElementById("btn_export_excel").addEventListener("click", () => {
        const params = new URLSearchParams({
            start_date: currentStartDate,
            end_date: currentEndDate,
            search: currentSearch,
        });
        window.location.href = `/sales/export/?${params.toString()}`;
    });

    // initial load
    loadDashboard();
});
