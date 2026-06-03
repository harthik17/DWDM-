const chartPalette = {
    blue: "#2563eb",
    teal: "#0f766e",
    orange: "#ea580c",
    red: "#dc2626",
    gray: "#64748b",
    sky: "rgba(37, 99, 235, 0.16)",
    mint: "rgba(15, 118, 110, 0.16)",
    amber: "rgba(234, 88, 12, 0.16)"
};

function chartElement(id) {
    return document.getElementById(id);
}

function shortLabel(label, length = 28) {
    if (!label) {
        return "";
    }
    return label.length > length ? `${label.slice(0, length)}...` : label;
}

function createChart(id, config) {
    const element = chartElement(id);
    if (!element || !window.Chart) {
        return null;
    }
    return new Chart(element, config);
}

async function loadDashboardCharts() {
    if (!chartElement("monthlySalesChart")) {
        return;
    }

    const analyticsResponse = await fetch("/api/analytics");
    const analytics = await analyticsResponse.json();

    createChart("monthlySalesChart", {
        type: "line",
        data: {
            labels: analytics.monthly_sales.labels,
            datasets: [
                {
                    label: "Sales",
                    data: analytics.monthly_sales.values,
                    borderColor: chartPalette.blue,
                    backgroundColor: chartPalette.sky,
                    fill: true,
                    tension: 0.32,
                    pointRadius: 3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: true } },
            scales: { x: { ticks: { maxRotation: 45, minRotation: 45 } } }
        }
    });

    createChart("profitChart", {
        type: "bar",
        data: {
            labels: analytics.monthly_profit.labels,
            datasets: [
                {
                    label: "Profit",
                    data: analytics.monthly_profit.values,
                    backgroundColor: analytics.monthly_profit.values.map(value =>
                        value >= 0 ? chartPalette.teal : chartPalette.red
                    )
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { x: { ticks: { maxRotation: 45, minRotation: 45 } } }
        }
    });

    createChart("regionSalesChart", {
        type: "doughnut",
        data: {
            labels: analytics.region_sales.labels,
            datasets: [
                {
                    data: analytics.region_sales.values,
                    backgroundColor: [
                        chartPalette.blue,
                        chartPalette.teal,
                        chartPalette.orange,
                        chartPalette.gray
                    ]
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } }
        }
    });

    createChart("categorySalesChart", {
        type: "bar",
        data: {
            labels: analytics.category_performance.labels,
            datasets: [
                {
                    label: "Sales",
                    data: analytics.category_performance.sales,
                    backgroundColor: chartPalette.blue
                },
                {
                    label: "Profit",
                    data: analytics.category_performance.profit,
                    backgroundColor: chartPalette.teal
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { x: { stacked: false }, y: { beginAtZero: true } }
        }
    });

    createChart("topProductsChart", {
        type: "bar",
        data: {
            labels: analytics.top_products.labels,
            datasets: [
                {
                    label: "Sales",
                    data: analytics.top_products.values,
                    backgroundColor: chartPalette.orange
                }
            ]
        },
        options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: {
                    ticks: {
                        callback: function(value) {
                            return shortLabel(this.getLabelForValue(value), 36);
                        }
                    }
                }
            }
        }
    });

    const metricsResponse = await fetch("/api/model-metrics");
    const metrics = await metricsResponse.json();

    createChart("modelAccuracyChart", {
        type: "bar",
        data: {
            labels: metrics.map(item => item.model_name),
            datasets: [
                {
                    label: "Accuracy %",
                    data: metrics.map(item => item.accuracy_percentage),
                    backgroundColor: [chartPalette.blue, chartPalette.teal, chartPalette.orange]
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: {
                    beginAtZero: true,
                    suggestedMax: 100
                }
            }
        }
    });
}

function bindPredictionForm() {
    const form = document.getElementById("predictionForm");
    if (!form) {
        return;
    }

    form.addEventListener("submit", async event => {
        event.preventDefault();

        const payload = {
            quantity: document.getElementById("quantity").value,
            discount: document.getElementById("discount").value,
            profit: document.getElementById("profit").value,
            model_name: document.getElementById("model_name").value
        };

        const response = await fetch("/api/predict", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            document.getElementById("predictionModel").textContent = "Prediction failed. Check values and try again.";
            return;
        }

        const result = await response.json();
        document.getElementById("predictionValue").textContent = `$${Number(result.predicted_sales).toFixed(2)}`;
        document.getElementById("predictionModel").textContent = `Model used: ${result.model_name}`;

        const historyBody = document.getElementById("predictionHistoryBody");
        if (historyBody) {
            const emptyRow = historyBody.querySelector(".empty-cell");
            if (emptyRow) {
                historyBody.innerHTML = "";
            }

            const row = document.createElement("tr");
            row.innerHTML = `
                <td>${result.quantity}</td>
                <td>${result.discount}</td>
                <td>$${Number(result.profit).toFixed(2)}</td>
                <td>${result.model_name}</td>
                <td><strong>$${Number(result.predicted_sales).toFixed(2)}</strong></td>
                <td>Just now</td>
            `;
            historyBody.prepend(row);
        }
    });
}

document.addEventListener("DOMContentLoaded", () => {
    loadDashboardCharts().catch(() => {});
    bindPredictionForm();
});
