console.log("sales_dashboard.js loaded (enhanced UI)");

let currentPage = 1;
let currentPageSize = 10;
let currentStartDate = "";
let currentEndDate = "";
let currentSearch = "";

// Chart instances
let paymentChart = null;
let trendChart = null;

// ----------------------- helpers -----------------------

function formatMoney(val) {
    const num = parseFloat(val || 0);
    return num.toFixed(2);
}

function animateNumber(el, target, duration = 400) {
    const start = parseFloat(el.innerText.replace(/[^\d.-]/g, "")) || 0;
    const diff = target - start;
    const startTime = performance.now();

    function step(now) {
        const progress = Math.min(1, (now - startTime) / duration);
        const value = start + diff * progress;
        el.innerText = formatMoney(value);
        if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

// ----------------------- main loader -----------------------

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
            buildChartsFromData(data.payments, data.table.rows);
        })
        .catch(err => {
            console.error("Dashboard load error", err);
        });
}

// ----------------------- KPIs -----------------------

function updateKPIs(kpis) {
    animateNumber(document.getElementById("kpi_today_sales"), kpis.today_sales);
    animateNumber(document.getElementById("kpi_last7_sales"), kpis.last_7_sales);
    animateNumber(document.getElementById("kpi_total_sales"), kpis.total_sales);

    const qtyEl = document.getElementById("kpi_total_qty");
    const startQty = parseInt(qtyEl.innerText || "0", 10);
    const targetQty = kpis.total_qty || 0;
    if (startQty !== targetQty) {
        qtyEl.innerText = targetQty;
    }
}

// ----------------------- Payment summary -----------------------

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
        row.className = "mb-3";

        row.innerHTML = `
            <div class="d-flex justify-content-between">
                <span class="small fw-semibold">${p.mode}</span>
                <span class="small">₹ ${formatMoney(p.amount)}</span>
            </div>
            <div class="progress" style="height:6px;">
                <div class="progress-bar" role="progressbar"
                     style="width:${percent.toFixed(1)}%;" aria-valuenow="${percent}"
                     aria-valuemin="0" aria-valuemax="100"></div>
            </div>
        `;
        container.appendChild(row);
    });
}

// ----------------------- Best selling article -----------------------

function updateBestSelling(best) {
    const container = document.getElementById("best_article_container");
    container.innerHTML = "";

    if (!best) {
        container.innerHTML = `<div class="text-muted small">No sales yet.</div>`;
        return;
    }

    container.innerHTML = `
        <div class="fw-semibold mb-1">${best.name}</div>
        <div class="small text-muted mb-2">Top by quantity sold</div>
        <div class="display-6 mb-1">${best.qty}</div>
        <div class="small text-muted">Revenue: ₹ ${formatMoney(best.amount)}</div>
    `;
}

// ----------------------- Table & Pagination -----------------------

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

    document.getElementById("btn_prev_page").disabled = (table.page <= 1);
    document.getElementById("btn_next_page").disabled = (table.page >= table.total_pages);

    // Summary badge (rows count)
    const badge = document.getElementById("summary_badge");
    if (table.total_rows > 0) {
        badge.classList.remove("d-none");
        badge.innerText = `${table.total_rows} rows`;
    } else {
        badge.classList.add("d-none");
    }
}

function updateMeta(meta) {
    const text = document.getElementById("table_meta_text");
    text.innerText = `Showing sales from ${meta.start_date} to ${meta.end_date}`;
}

// ----------------------- Charts -----------------------

function buildChartsFromData(payments, tableRows) {
    buildPaymentChart(payments);
    buildTrendChart(tableRows);
}

function buildPaymentChart(payments) {
    const ctx = document.getElementById("chart_payment_modes");
    if (!ctx) return;

    const labels = payments && payments.length ? payments.map(p => p.mode) : [];
    const dataVals = payments && payments.length ? payments.map(p => p.amount) : [];

    if (paymentChart) {
        paymentChart.destroy();
    }

    if (!labels.length) {
        // nothing to draw
        return;
    }

    paymentChart = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: labels,
            datasets: [{
                data: dataVals,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "bottom" }
            },
            cutout: "55%"
        }
    });
}

function buildTrendChart(tableRows) {
    const ctx = document.getElementById("chart_sales_trend");
    if (!ctx) return;

    // Group by date
    const map = new Map();
    (tableRows || []).forEach(r => {
        const date = r.date;
        const amt = parseFloat(r.amount || 0);
        map.set(date, (map.get(date) || 0) + amt);
    });

    const labels = Array.from(map.keys()).sort((a, b) => {
        const [da, ma, ya] = a.split("-").map(Number);
        const [db, mb, yb] = b.split("-").map(Number);
        return new Date(ya, ma - 1, da) - new Date(yb, mb - 1, db);
    });

    const dataVals = labels.map(d => map.get(d));

    if (trendChart) {
        trendChart.destroy();
    }

    if (!labels.length) {
        return;
    }

    trendChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [{
                label: "Sales Amount",
                data: dataVals,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
}

// ----------------------- events -----------------------

document.addEventListener("DOMContentLoaded", () => {
    const rowsSelect = document.getElementById("rows_per_page");
    currentPageSize = parseInt(rowsSelect.value, 10);

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
        currentSearch = "";
        document.getElementById("search_box").value = "";
        loadDashboard();
    });

    rowsSelect.addEventListener("change", () => {
        currentPageSize = parseInt(rowsSelect.value, 10);
        currentPage = 1;
        loadDashboard();
    });

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

    document.getElementById("btn_export_excel").addEventListener("click", () => {
        const params = new URLSearchParams({
            start_date: currentStartDate,
            end_date: currentEndDate,
            search: currentSearch,
        });
        window.location.href = `/sales/export/?${params.toString()}`;
    });

    loadDashboard();
});
