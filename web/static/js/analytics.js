/**
 * GeoShield – Analytics Controller
 * Renders Chart.js visualisations using real NASA VIIRS aggregated data.
 */

let trendsChart = null;
let cityChart = null;
let monthlyChart = null;

document.addEventListener('DOMContentLoaded', () => {
  initAnalytics();
});

async function initAnalytics() {
  await Promise.all([
    renderYearlyTrends(),
    renderCityBreakdown(),
    renderMonthlyDistribution(2024)
  ]);

  const yearSelect = document.getElementById('monthly-year-select');
  if (yearSelect) {
    yearSelect.addEventListener('change', (e) => {
      renderMonthlyDistribution(e.target.value);
    });
  }
}

async function renderYearlyTrends() {
  const ctx = document.getElementById('chart-yearly-trends')?.getContext('2d');
  if (!ctx) return;

  try {
    const res = await fetch('/api/analytics/trends');
    const data = await res.json();
    const trends = data.trends || [];

    const labels = trends.map(t => t.year);
    const fireData = trends.map(t => t.fire);
    const floodData = trends.map(t => t.flood);

    if (trendsChart) trendsChart.destroy();

    trendsChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Fire Detections',
            data: fireData,
            backgroundColor: 'rgba(239, 68, 68, 0.75)',
            borderColor: '#EF4444',
            borderWidth: 1
          },
          {
            label: 'Flood Proxy Detections',
            data: floodData,
            backgroundColor: 'rgba(56, 189, 248, 0.75)',
            borderColor: '#38BDF8',
            borderWidth: 1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#94A3B8' } }
        },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94A3B8' } },
          y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94A3B8' } }
        }
      }
    });
  } catch (err) {
    console.error('Trends chart error', err);
  }
}

async function renderCityBreakdown() {
  const ctx = document.getElementById('chart-city-breakdown')?.getContext('2d');
  if (!ctx) return;

  try {
    const res = await fetch('/api/analytics/cities');
    const data = await res.json();
    const topCities = (data.cities || []).slice(0, 8);

    if (cityChart) cityChart.destroy();

    cityChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: topCities.map(c => c.city),
        datasets: [{
          label: 'Total Fire Detections',
          data: topCities.map(c => c.fire),
          backgroundColor: 'rgba(245, 158, 11, 0.75)',
          borderColor: '#F59E0B',
          borderWidth: 1
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#94A3B8' } }
        },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94A3B8' } },
          y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94A3B8' } }
        }
      }
    });
  } catch (err) {
    console.error('City chart error', err);
  }
}

async function renderMonthlyDistribution(year = 2024) {
  const ctx = document.getElementById('chart-monthly-season')?.getContext('2d');
  if (!ctx) return;

  try {
    const res = await fetch(`/api/analytics/monthly?year=${year}`);
    const data = await res.json();
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const monthlyData = data.monthly || [];

    const fireSeries = months.map((_, i) => {
      const match = monthlyData.find(m => m.month === (i + 1));
      return match ? match.fire : 0;
    });

    const floodSeries = months.map((_, i) => {
      const match = monthlyData.find(m => m.month === (i + 1));
      return match ? match.flood : 0;
    });

    if (monthlyChart) monthlyChart.destroy();

    monthlyChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: months,
        datasets: [
          {
            label: 'Fire Seasonality',
            data: fireSeries,
            borderColor: '#EF4444',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            fill: true,
            tension: 0.3
          },
          {
            label: 'Monsoon / Flood Seasonality',
            data: floodSeries,
            borderColor: '#38BDF8',
            backgroundColor: 'rgba(56, 189, 248, 0.1)',
            fill: true,
            tension: 0.3
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#94A3B8' } }
        },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94A3B8' } },
          y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94A3B8' } }
        }
      }
    });
  } catch (err) {
    console.error('Monthly chart error', err);
  }
}
