fetch("/api/expenses/chart/")
    .then(res => res.json())
    .then(d => {
        new Chart(document.getElementById("expenseChart"), {
            type: "bar",
            data: {
                labels: d.labels,
                datasets: [{
                    label: "Expense Amount",
                    data: d.data,
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false }
                }
            }
        });
    });
