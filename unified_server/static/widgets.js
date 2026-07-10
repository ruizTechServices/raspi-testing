// World Snapshot widgets — free public APIs proxied through /api/integrations/*.
// All endpoints are public reads; no API key required.

const weatherLocationPillEl = document.getElementById('weatherLocationPill');
const weatherTempEl = document.getElementById('weatherTemp');
const weatherMetaEl = document.getElementById('weatherMeta');
const weatherForecastEl = document.getElementById('weatherForecast');

const publicIpRefreshBtnEl = document.getElementById('publicIpRefreshBtn');
const publicIpValueEl = document.getElementById('publicIpValue');
const publicIpMetaEl = document.getElementById('publicIpMeta');

const cryptoListEl = document.getElementById('cryptoList');
const cryptoMetaEl = document.getElementById('cryptoMeta');

const currencyFormEl = document.getElementById('currencyForm');
const currencyAmountEl = document.getElementById('currencyAmount');
const currencyFromEl = document.getElementById('currencyFrom');
const currencyToEl = document.getElementById('currencyTo');
const currencyConvertBtnEl = document.getElementById('currencyConvertBtn');
const currencyResultEl = document.getElementById('currencyResult');
const currencyMetaEl = document.getElementById('currencyMeta');

const apodDatePillEl = document.getElementById('apodDatePill');
const apodLinkEl = document.getElementById('apodLink');
const apodImageEl = document.getElementById('apodImage');
const apodTitleEl = document.getElementById('apodTitle');
const apodMetaEl = document.getElementById('apodMeta');

const widgetsRefreshBtnEl = document.getElementById('widgetsRefreshBtn');

function escapeWidgetHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

async function fetchWidgetJson(url) {
  const response = await fetch(url);
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(data?.error || `Request failed (${response.status}).`);
  }
  return data;
}

async function loadWeather() {
  try {
    const data = await fetchWidgetJson('/api/integrations/weather');
    weatherLocationPillEl.textContent = data.location || '--';
    const current = data.current || {};
    weatherTempEl.textContent = current.temperature_f != null ? `${Math.round(current.temperature_f)}°F` : '--';
    const bits = [];
    if (current.conditions) bits.push(current.conditions);
    if (current.feels_like_f != null) bits.push(`feels ${Math.round(current.feels_like_f)}°F`);
    if (current.humidity_percent != null) bits.push(`${current.humidity_percent}% humidity`);
    if (current.wind_mph != null) bits.push(`${Math.round(current.wind_mph)} mph wind`);
    weatherMetaEl.textContent = bits.join(' · ') || 'No current conditions.';
    weatherForecastEl.innerHTML = (data.daily || []).map((day) => `
      <div class="dashboard-list-item dashboard-list-item-soft">
        <div class="dashboard-list-main">
          <div class="dashboard-list-title">${escapeWidgetHtml(day.date)}</div>
          <div class="dashboard-item-meta">${escapeWidgetHtml(day.conditions)} · ${day.precipitation_chance ?? 0}% rain</div>
        </div>
        <div class="dashboard-list-time">${day.high_f != null ? Math.round(day.high_f) : '--'}° / ${day.low_f != null ? Math.round(day.low_f) : '--'}°</div>
      </div>
    `).join('');
  } catch (error) {
    weatherTempEl.textContent = '--';
    weatherMetaEl.textContent = error.message;
    weatherForecastEl.innerHTML = '';
  }
}

async function loadPublicIp() {
  publicIpValueEl.textContent = '...';
  try {
    const data = await fetchWidgetJson('/api/integrations/network/public-ip');
    publicIpValueEl.textContent = data.ip || 'Unknown';
    publicIpMetaEl.textContent = `Public WAN address via ${data.source || 'ipify'}.`;
  } catch (error) {
    publicIpValueEl.textContent = 'Unavailable';
    publicIpMetaEl.textContent = error.message;
  }
}

function formatUsd(value) {
  if (value == null) return '--';
  return value.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}

async function loadCrypto() {
  try {
    const data = await fetchWidgetJson('/api/integrations/crypto/prices');
    const prices = data.prices || [];
    if (!prices.length) {
      cryptoListEl.innerHTML = '<div class="empty-state">No prices returned.</div>';
      return;
    }
    cryptoListEl.innerHTML = prices.map((entry) => {
      const change = entry.change_24h_percent;
      const tone = change == null ? 'neutral' : change >= 0 ? 'ok' : 'error';
      const changeText = change == null ? '--' : `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
      return `
        <div class="dashboard-list-item dashboard-list-item-soft">
          <div class="dashboard-list-main">
            <div class="dashboard-list-title">${escapeWidgetHtml(entry.coin)}</div>
            <div class="dashboard-item-meta">${escapeWidgetHtml(formatUsd(entry.usd))}</div>
          </div>
          <div class="dashboard-status-pill ${tone}">${escapeWidgetHtml(changeText)}</div>
        </div>
      `;
    }).join('');
    cryptoMetaEl.textContent = `Spot prices via ${data.source || 'CoinGecko'} · 24h change.`;
  } catch (error) {
    cryptoListEl.innerHTML = `<div class="empty-state">${escapeWidgetHtml(error.message)}</div>`;
  }
}

async function convertCurrency(event) {
  if (event) event.preventDefault();
  const amount = Number(currencyAmountEl.value);
  const from = currencyFromEl.value;
  const to = currencyToEl.value;
  currencyConvertBtnEl.disabled = true;
  currencyResultEl.textContent = '...';
  try {
    const params = new URLSearchParams({ amount: String(amount), from, to });
    const data = await fetchWidgetJson(`/api/integrations/currency/convert?${params}`);
    const converted = data.converted != null ? data.converted.toLocaleString('en-US', { maximumFractionDigits: 2 }) : '--';
    currencyResultEl.textContent = `${converted} ${data.to}`;
    currencyMetaEl.textContent = `${data.amount} ${data.from} → ${data.to}, rates from ${data.rate_date}.`;
  } catch (error) {
    currencyResultEl.textContent = '--';
    currencyMetaEl.textContent = error.message;
  } finally {
    currencyConvertBtnEl.disabled = false;
  }
}

async function loadApod() {
  try {
    const data = await fetchWidgetJson('/api/integrations/apod');
    apodDatePillEl.textContent = data.date || '--';
    apodTitleEl.textContent = data.title || 'Untitled';
    const imageUrl = data.media_type === 'image' ? data.url : data.thumbnail_url;
    if (imageUrl) {
      apodImageEl.src = imageUrl;
      apodImageEl.hidden = false;
      apodLinkEl.href = data.hd_url || data.url || imageUrl;
    } else {
      apodImageEl.hidden = true;
      apodLinkEl.href = data.url || '#';
    }
    apodMetaEl.textContent = data.copyright ? `© ${data.copyright}` : 'Public domain / NASA.';
  } catch (error) {
    apodTitleEl.textContent = 'Unavailable';
    apodMetaEl.textContent = error.message;
    apodImageEl.hidden = true;
  }
}

function refreshWidgets() {
  loadWeather();
  loadPublicIp();
  loadCrypto();
  loadApod();
}

if (currencyFormEl) currencyFormEl.addEventListener('submit', convertCurrency);
if (publicIpRefreshBtnEl) publicIpRefreshBtnEl.addEventListener('click', loadPublicIp);
if (widgetsRefreshBtnEl) widgetsRefreshBtnEl.addEventListener('click', refreshWidgets);

refreshWidgets();
