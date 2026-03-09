/**
 * TaxAssistant Portal Dashboard
 * Fetches metrics from the portal API and renders charts.
 */

const API_BASE = '/portal/api';
let growthChart = null;
let activityChart = null;
let segmentationChart = null;

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function apiFetch(path) {
    const resp = await fetch(`${API_BASE}${path}`, { credentials: 'same-origin' });
    if (resp.status === 401) {
        window.location.href = '/portal/';
        return null;
    }
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    return resp.json();
}

function getDateRange() {
    const start = document.getElementById('startDate').value;
    const end = document.getElementById('endDate').value;
    const params = new URLSearchParams();
    if (start) params.set('start', start);
    if (end) params.set('end', end);
    const qs = params.toString();
    return qs ? `?${qs}` : '';
}

// ---------------------------------------------------------------------------
// Load summary cards
// ---------------------------------------------------------------------------

async function loadSummary() {
    const data = await apiFetch('/metrics/summary');
    if (!data) return;
    document.getElementById('totalUsers').textContent = data.total_users.toLocaleString();
    document.getElementById('newUsersToday').textContent = data.new_users_today.toLocaleString();
    document.getElementById('dauValue').textContent = data.dau.toLocaleString();
    document.getElementById('mauValue').textContent = data.mau.toLocaleString();
}

// ---------------------------------------------------------------------------
// Charts
// ---------------------------------------------------------------------------

function renderLineChart(canvasId, label, items, color, existingChart) {
    if (existingChart) existingChart.destroy();
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: items.map(d => d.date),
            datasets: [{
                label: label,
                data: items.map(d => d.count),
                borderColor: color,
                backgroundColor: color + '22',
                fill: true,
                tension: 0.3,
                pointRadius: 3,
            }],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { maxTicksLimit: 10, font: { size: 11 } } },
                y: { beginAtZero: true, ticks: { font: { size: 11 } } },
            },
        },
    });
}

const SEGMENT_LABELS = {
    'sme': 'Doanh nghiep',
    'household': 'Ho gia dinh',
    'individual': 'Ca the kinh doanh',
    'unknown': 'Chua xac dinh',
};

const SEGMENT_COLORS = ['#2563eb', '#f59e0b', '#10b981', '#94a3b8'];

function renderSegmentationChart(items) {
    if (segmentationChart) segmentationChart.destroy();
    const ctx = document.getElementById('segmentationChart').getContext('2d');
    segmentationChart = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: items.map(d => SEGMENT_LABELS[d.customer_type] || d.customer_type),
            datasets: [{
                data: items.map(d => d.count),
                backgroundColor: SEGMENT_COLORS.slice(0, items.length),
            }],
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom', labels: { font: { size: 12 } } },
            },
        },
    });
}

async function loadCharts() {
    const range = getDateRange();
    const [growth, activity, seg] = await Promise.all([
        apiFetch(`/metrics/growth-trends${range}`),
        apiFetch(`/metrics/activity-trends${range}`),
        apiFetch('/metrics/segmentation'),
    ]);

    if (growth) growthChart = renderLineChart('growthChart', 'New Users', growth.data, '#2563eb', growthChart);
    if (activity) activityChart = renderLineChart('activityChart', 'Active Users', activity.data, '#10b981', activityChart);
    if (seg) renderSegmentationChart(seg.data);
}

// ---------------------------------------------------------------------------
// Export CSV
// ---------------------------------------------------------------------------

function exportCsv() {
    const range = getDateRange();
    window.location.href = `/portal/api/export/users${range}`;
}

// ---------------------------------------------------------------------------
// Logout
// ---------------------------------------------------------------------------

async function logout() {
    await fetch('/portal/logout', { method: 'POST', credentials: 'same-origin' });
    window.location.href = '/portal/';
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
    // Set default date range (last 30 days)
    const today = new Date();
    const thirtyDaysAgo = new Date(today);
    thirtyDaysAgo.setDate(today.getDate() - 30);
    document.getElementById('endDate').value = today.toISOString().split('T')[0];
    document.getElementById('startDate').value = thirtyDaysAgo.toISOString().split('T')[0];

    // Load data
    loadSummary();
    loadCharts();

    // Event listeners
    document.getElementById('applyFilter').addEventListener('click', () => {
        loadSummary();
        loadCharts();
    });
    document.getElementById('exportCsv').addEventListener('click', exportCsv);
    document.getElementById('logoutBtn').addEventListener('click', logout);
});
