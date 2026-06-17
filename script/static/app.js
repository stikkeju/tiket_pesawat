/**
 * app.js — FlightSim Frontend Logic
 * Handles cascading dropdowns, form validation, API calls, and result rendering.
 */

/* ═══════════════════════════════════════════
   STATE
   ═══════════════════════════════════════════ */
const state = {
  n: 5,
  transitValue: '',       // '' = all, '0' = direct, '1' = transit
  isLoading: false,
  swapped: false,
  currentData: null,
  isAdvanced: false,
};

/* ═══════════════════════════════════════════
   DOM REFS
   ═══════════════════════════════════════════ */
const $ = id => document.getElementById(id);

const selOrigin   = $('sel-origin');
const selDest     = $('sel-dest');
const selAirline  = $('sel-airline');
const selClass    = $('sel-class');
const inpDateGo   = $('inp-date-go');
const inpDateRet  = $('inp-date-ret');
const btnSwap     = $('btn-swap');
const btnSearch   = $('btn-search');
const btnSearchTx = $('btn-search-text');
const dispN       = $('disp-n');
const btnNDec     = $('btn-n-dec');
const btnNInc     = $('btn-n-inc');
const resultsSection  = $('results-section');
const resultsContainer = $('results-container');
const loadingState    = $('loading-state');
const tBtns = document.querySelectorAll('.toggle-btn');

// Mode toggle elements
const btnModeBasic = $('btn-mode-basic');
const btnModeAdv   = $('btn-mode-advanced');
const advancedForm = $('advanced-form');
const grpTransit   = $('grp-transit').parentElement;
const grpBasicN    = $('grp-basic-n');

/* ═══════════════════════════════════════════
   INIT
   ═══════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  setMinDate();
  generateParticles();
  loadOrigins();
  bindEvents();
});

function setMinDate() {
  const today = new Date().toISOString().split('T')[0];
  inpDateGo.min  = today;
  inpDateRet.min = today;
  // default: tomorrow
  const tom = new Date(); tom.setDate(tom.getDate() + 1);
  inpDateGo.value = tom.toISOString().split('T')[0];
}

function generateParticles() {
  const container = $('particles');
  for (let i = 0; i < 18; i++) {
    const p = document.createElement('div');
    p.className = 'particle';
    const size = Math.random() * 4 + 2;
    p.style.cssText = `
      width:${size}px; height:${size}px;
      left:${Math.random()*100}%;
      top:${40 + Math.random()*60}%;
      --dur:${6 + Math.random()*8}s;
      --delay:${Math.random()*6}s;
    `;
    container.appendChild(p);
  }
}

/* ═══════════════════════════════════════════
   API HELPERS
   ═══════════════════════════════════════════ */
async function apiFetch(url) {
  const r = await fetch(url);
  const j = await r.json();
  if (j.status !== 'ok') throw new Error(j.message || 'API error');
  return j.data;
}

async function apiPost(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const j = await r.json();
  if (j.status !== 'ok') throw new Error(j.message || 'API error');
  return j.data;
}

/* ═══════════════════════════════════════════
   CASCADING DROPDOWNS
   ═══════════════════════════════════════════ */
async function loadOrigins() {
  const data = await apiFetch('/api/airports/origin');
  populateSelect(selOrigin, data, 'Pilih bandara asal...');
  selOrigin.disabled = false;
}

async function loadDests(origin) {
  selDest.disabled = true;
  selAirline.disabled = true;
  selClass.disabled = true;
  btnSearch.disabled = true;

  resetSelect(selDest,    'Memuat tujuan...');
  resetSelect(selAirline, 'Pilih rute dulu');
  resetSelect(selClass,   'Pilih maskapai dulu');

  const data = await apiFetch(`/api/airports/dest?origin=${encodeURIComponent(origin)}`);
  populateSelect(selDest, data, 'Pilih bandara tujuan...');
  selDest.disabled = false;
}

async function loadAirlines() {
  selAirline.disabled = true;
  selClass.disabled = true;
  btnSearch.disabled = true;

  resetSelect(selAirline, 'Memuat maskapai...');
  resetSelect(selClass,   'Pilih maskapai dulu');

  const origin = selOrigin.value;
  const dest = selDest.value;

  const data = await apiFetch(`/api/airlines?origin=${encodeURIComponent(origin)}&dest=${encodeURIComponent(dest)}`);
  
  selAirline.innerHTML = '';
  const existingGroup = document.createElement('optgroup');
  existingGroup.label = 'Maskapai Rute Ini (Historis)';
  const otherGroup = document.createElement('optgroup');
  otherGroup.label = 'Maskapai Lain (Simulasi)';
  
  data.forEach(item => {
    // Skip ALL option if in Advanced Mode
    if (state.isAdvanced && item.code === 'ALL') return;

    const opt = document.createElement('option');
    opt.value = item.code;
    opt.textContent = item.name || item.code;
    
    if (item.code === 'ALL') {
      selAirline.appendChild(opt);
    } else if (item.existing) {
      existingGroup.appendChild(opt);
    } else {
      otherGroup.appendChild(opt);
    }
  });
  
  if (existingGroup.children.length > 0) selAirline.appendChild(existingGroup);
  if (otherGroup.children.length > 0) selAirline.appendChild(otherGroup);
  
  if (data.length > 0) selAirline.value = data[0].code;

  selAirline.disabled = false;
}

async function loadClasses(airline) {
  if (state.isAdvanced) {
    populateSelect(selClass, [
      {code: "ECONOMY", name: "Economy"},
      {code: "PREMIUM_ECONOMY", name: "Premium Economy"},
      {code: "BUSINESS", name: "Business"},
      {code: "FIRST", name: "First"}
    ], null);
    selClass.disabled = false;
    checkSearchReady();
    return;
  }

  selClass.disabled = true;
  btnSearch.disabled = true;

  resetSelect(selClass, 'Memuat kelas...');

  const data = await apiFetch(`/api/classes?airline=${encodeURIComponent(airline)}`);
  populateSelect(selClass, data, null);
  selClass.disabled = false;
  checkSearchReady();
}

function populateSelect(sel, items, placeholder) {
  sel.innerHTML = '';
  if (placeholder) {
    const opt = document.createElement('option');
    opt.value = ''; opt.textContent = placeholder; opt.disabled = true; opt.selected = true;
    sel.appendChild(opt);
  }
  items.forEach(({ code, name }) => {
    const opt = document.createElement('option');
    opt.value = code;
    opt.textContent = name || code;
    sel.appendChild(opt);
  });
  // Auto-select if only one real option (or first)
  if (!placeholder && items.length > 0) sel.value = items[0].code;
}

function resetSelect(sel, text) {
  sel.innerHTML = `<option value="">${text}</option>`;
  sel.value = '';
}

function checkSearchReady() {
  const ok = selOrigin.value && selDest.value && selAirline.value && selClass.value && inpDateGo.value;
  btnSearch.disabled = !ok;
}

/* ═══════════════════════════════════════════
   ROUTE INFO PANEL
   ═══════════════════════════════════════════ */

function createRouteInfoPanel() {
  const panel = document.createElement('div');
  panel.id = 'route-info-panel';
  panel.style.cssText = `
    display:none; align-items:center; gap:10px;
    padding:10px 14px; border-radius:10px; margin-bottom:4px;
    font-size:0.82rem; font-weight:500; transition:all 0.25s;
  `;
  // Insert after form-row-route
  const routeRow = document.querySelector('.form-row-route');
  routeRow.insertAdjacentElement('afterend', panel);
}

async function checkRouteInfo(origin, dest) {
  const panel = $('route-info-panel');
  if (!panel || !origin || !dest) return;

  try {
    const data = await apiFetch(`/api/route/check?origin=${encodeURIComponent(origin)}&dest=${encodeURIComponent(dest)}`);
    const { exists, jarak_km } = data;
    const distStr = jarak_km ? ` · ${jarak_km.toLocaleString('id-ID')} km` : '';

    if (exists) {
      panel.style.cssText += `background:rgba(41,217,142,0.07);border:1px solid rgba(41,217,142,0.2);color:#29d98e;display:flex;`;
      panel.innerHTML = `<span>✓</span><span>Rute ada dalam data historis${distStr}</span>`;
    } else {
      panel.style.cssText += `background:rgba(245,197,24,0.07);border:1px solid rgba(245,197,24,0.2);color:#f5c518;display:flex;`;
      panel.innerHTML = `<span>⚠</span><span>Rute baru — prediksi menggunakan profil maskapai/kelas terdekat${distStr}</span>`;
    }
    panel.style.display = 'flex';
  } catch (e) {
    panel.style.display = 'none';
  }
}

/* ═══════════════════════════════════════════
   EVENT BINDINGS
   ═══════════════════════════════════════════ */
function bindEvents() {
  // Origin change
  selOrigin.addEventListener('change', () => {
    if (selOrigin.value) loadDests(selOrigin.value);
  });

  // Dest change
  selDest.addEventListener('change', () => {
    if (selDest.value && selOrigin.value) {
      loadAirlines();
      checkRouteInfo(selOrigin.value, selDest.value);
    }
  });

  // Airline change
  selAirline.addEventListener('change', () => {
    if (selAirline.value) loadClasses(selAirline.value);
  });

  // Class change
  selClass.addEventListener('change', checkSearchReady);

  // Date change
  inpDateGo.addEventListener('change', () => {
    // Update return date minimum
    if (inpDateGo.value) {
      inpDateRet.min = inpDateGo.value;
      if (inpDateRet.value && inpDateRet.value <= inpDateGo.value) inpDateRet.value = '';
    }
    checkSearchReady();
  });

  // Swap button
  btnSwap.addEventListener('click', () => {
    const origVal  = selOrigin.value;
    const destVal  = selDest.value;
    if (!origVal || !destVal) return;

    state.swapped = !state.swapped;
    btnSwap.classList.toggle('swapped', state.swapped);

    selOrigin.value = destVal;
    loadDests(destVal).then(() => {
      selDest.value = origVal;
      selDest.dispatchEvent(new Event('change'));
    });
  });

  // Route info panel init
  createRouteInfoPanel();

  // Transit toggle
  tBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.transitValue = btn.dataset.value;
    });
  });

  // N spinner
  btnNDec.addEventListener('click', () => {
    if (state.n > 1) { state.n--; dispN.textContent = state.n; }
  });
  btnNInc.addEventListener('click', () => {
    if (state.n < 10) { state.n++; dispN.textContent = state.n; }
  });

  // Search
  btnSearch.addEventListener('click', handleSearch);

  // Popular destinations click
  document.querySelectorAll('.dest-card').forEach(card => {
    card.addEventListener('click', () => {
      const code = card.dataset.code;
      if (!selOrigin.value) {
        selOrigin.value = 'CGK';
        loadDests('CGK').then(() => {
          selDest.value = code;
          selDest.dispatchEvent(new Event('change'));
        });
      } else {
        selDest.value = code;
        selDest.dispatchEvent(new Event('change'));
      }
      window.scrollTo({top: 0, behavior: 'smooth'});
    });
  });

  // Sidebar filters
  document.querySelectorAll('input[name="sort"], .cb-transit').forEach(el => {
    el.addEventListener('change', () => {
      if (state.currentData) applyFilters();
    });
  });

  // Mode Toggle
  btnModeBasic.addEventListener('click', () => setMode(false));
  btnModeAdv.addEventListener('click', () => setMode(true));
}

function setMode(isAdvanced) {
  state.isAdvanced = isAdvanced;
  if (isAdvanced) {
    btnModeBasic.classList.remove('active');
    btnModeAdv.classList.add('active');
    advancedForm.style.display = 'grid';
    grpTransit.style.display = 'none';
    grpBasicN.style.display = 'none';
  } else {
    btnModeAdv.classList.remove('active');
    btnModeBasic.classList.add('active');
    advancedForm.style.display = 'none';
    grpTransit.style.display = 'flex';
    grpBasicN.style.display = 'flex';
  }
  
  // Reload airlines to add/remove "ALL" option based on mode
  if (selOrigin.value && selDest.value) {
    const prevAirline = selAirline.value;
    loadAirlines().then(() => {
        // Try to restore the previous airline selection if it still exists
        // (e.g. if previous was 'ALL', it won't exist in Advanced mode, so it falls back to first)
        let found = false;
        for (let i = 0; i < selAirline.options.length; i++) {
           if (selAirline.options[i].value === prevAirline) {
               selAirline.value = prevAirline;
               found = true;
               break;
           }
        }
        
        // After airline is set, reload classes
        if (selAirline.value) {
          const prevClass = selClass.value;
          loadClasses(selAirline.value).then(() => {
              if (prevClass) {
                 for(let i = 0; i < selClass.options.length; i++) {
                     if(selClass.options[i].value === prevClass) {
                         selClass.value = prevClass;
                         break;
                     }
                 }
              }
          });
        }
    });
  }
}

/* ═══════════════════════════════════════════
   SEARCH
   ═══════════════════════════════════════════ */
async function handleSearch() {
  if (state.isLoading) return;

  const origin = selOrigin.value;
  const dest   = selDest.value;
  const dateGo = inpDateGo.value;
  if (!origin || !dest || !dateGo) return;

  const body = {
    origin,
    dest,
    tanggal_berangkat: dateGo,
    tanggal_pulang: inpDateRet.value || null,
    airline: selAirline.value,
    kelas:   selClass.value,
    is_transit: state.transitValue === '' ? null : parseInt(state.transitValue),
    n: state.n,
  };

  if (state.isAdvanced) {
    body.is_advanced = true;
    body.advanced_features = {
      waktu_berangkat_kategori: $('adv-waktu-berangkat').value,
      transit: parseInt($('adv-transit').value),
      model_pesawat: $('adv-model-pesawat').value,
      seat_type: $('adv-seat-type').value,
      seat_layout: $('adv-seat-layout').value,
      seat_pitch_inch: parseFloat($('adv-seat-pitch').value),
      wifi_status: $('adv-wifi').value,
      bagasi_kg: parseFloat($('adv-bagasi').value),
      cabin_baggage_kg: parseFloat($('adv-kabin').value),
      meal: $('adv-meal').checked,
      entertainment: $('adv-entertainment').checked,
      usb: $('adv-usb').checked,
      power: $('adv-power').checked,
      refundable: $('adv-refundable').checked,
      reschedulable: $('adv-reschedulable').checked,
      visa_required: $('adv-visa').checked
    };
    
    // Kirim durasi_menit jika user memasukkannya
    const durasiVal = $('adv-durasi').value;
    if (durasiVal && !isNaN(durasiVal)) {
      body.advanced_features.durasi_menit = parseInt(durasiVal, 10);
    }
  }

  setLoading(true);
  resultsSection.style.display = 'block';
  resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
  resultsContainer.innerHTML = '';

  try {
    const data = await apiPost('/api/predict', body);
    state.currentData = data;
    applyFilters();
  } catch (e) {
    renderError(e.message);
  } finally {
    setLoading(false);
  }
}

function applyFilters() {
  if (!state.currentData) return;
  const data = JSON.parse(JSON.stringify(state.currentData)); // deep clone
  
  const sortVal = document.querySelector('input[name="sort"]:checked').value;
  const transitCb = Array.from(document.querySelectorAll('.cb-transit:checked')).map(cb => cb.value);

  const doFilter = (arr) => {
    let res = arr.filter(t => {
      if (t.is_transit && !transitCb.includes('transit')) return false;
      if (!t.is_transit && !transitCb.includes('direct')) return false;
      return true;
    });
    if (sortVal === 'price') {
      res.sort((a, b) => a.harga_idr - b.harga_idr);
    } else if (sortVal === 'duration') {
      res.sort((a, b) => a.durasi_menit - b.durasi_menit);
    }
    return res;
  };

  if (data.berangkat) {
     data.berangkat.tickets = doFilter(data.berangkat.tickets);
  }
  if (data.pulang) {
     data.pulang.tickets = doFilter(data.pulang.tickets);
  }

  renderResults(data);
}

function setLoading(on) {
  state.isLoading = on;
  loadingState.classList.toggle('visible', on);
  btnSearch.disabled = on;
  btnSearchTx.textContent = on ? 'Mencari...' : 'Cari Tiket';
}

/* ═══════════════════════════════════════════
   RENDER RESULTS
   ═══════════════════════════════════════════ */
function renderResults(data) {
  resultsContainer.innerHTML = '';

  const { berangkat, pulang } = data;

  if (berangkat) {
    const label = pulang ? 'Berangkat' : null;
    renderBlock(berangkat, label, 0);
  }

  if (pulang) {
    renderBlock(pulang, 'Pulang', 1);
  }
}

function renderBlock(result, label, idx) {
  const tmpl = document.getElementById('tmpl-result-block');
  const block = tmpl.content.cloneNode(true).querySelector('.result-block');
  block.style.setProperty('--i', idx);

  // Header
  block.querySelector('[data-bind="origin"]').textContent = result.params.origin || '';
  block.querySelector('[data-bind="dest"]').textContent   = result.params.dest   || '';

  const dateStr  = formatDate(result.params.tanggal_terbang);
  const kelasStr = result.params.kelas ? result.params.kelas.replace('_', ' ') : '';
  const nFound   = `${result.params.n_found} tiket ditemukan`;
  const jarakStr = result.params.jarak_km ? ` · ${result.params.jarak_km.toLocaleString('id-ID')} km` : '';
  block.querySelector('[data-bind="date"]').textContent    = dateStr;
  block.querySelector('[data-bind="kelas"]').textContent   = kelasStr;
  block.querySelector('[data-bind="n_found"]').textContent = nFound + jarakStr;

  // Badge rute baru
  if (result.params.route_exists === false) {
    const badge = document.createElement('span');
    badge.style.cssText = 'font-size:0.7rem;padding:2px 8px;border-radius:8px;background:rgba(245,197,24,0.1);color:#f5c518;border:1px solid rgba(245,197,24,0.25);font-weight:600;';
    badge.textContent = 'Rute Baru';
    block.querySelector('.result-block-meta').prepend(badge);
  }

  // Direction label (if round-trip)
  if (label) {
    const lbl = document.createElement('div');
    lbl.className = 'direction-label';
    lbl.textContent = label === 'Berangkat' ? 'Penerbangan Berangkat' : 'Penerbangan Pulang';
    block.prepend(lbl);
  }

  // Warnings
  const warningsWrap = block.querySelector('[data-bind="warnings"]');
  (result.warnings || []).forEach(w => {
    const banner = document.createElement('div');
    banner.className = 'warning-banner';
    banner.innerHTML = `<span>Peringatan: </span><span>${w}</span>`;
    warningsWrap.appendChild(banner);
  });

  // Tickets
  const grid = block.querySelector('[data-bind="tickets"]');
  if (!result.tickets || result.tickets.length === 0) {
    grid.innerHTML = `<p style="color:var(--clr-muted);grid-column:1/-1;padding:20px 0;">Tidak ada tiket ditemukan untuk parameter ini.</p>`;
  } else {
    result.tickets.forEach((ticket, i) => {
      grid.appendChild(renderTicketCard(ticket, i + 1, result.params.tanggal_terbang));
    });
  }

  resultsContainer.appendChild(block);
}

function renderTicketCard(t, rank, rawDate) {
  const tmpl = document.getElementById('tmpl-ticket-card');
  const card = tmpl.content.cloneNode(true).querySelector('.ticket-card');

  // Dates
  const dGo = new Date(rawDate + 'T00:00:00');
  const dGoStr = dGo.toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' });
  const dArr = new Date(dGo);
  if (t.tiba_besok) dArr.setDate(dArr.getDate() + 1);
  const dArrStr = dArr.toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' });

  const dateBerangkatEl = card.querySelector('[data-bind="tgl_berangkat"]');
  if (dateBerangkatEl) dateBerangkatEl.textContent = dGoStr;
  
  const dateTibaEl = card.querySelector('[data-bind="tgl_tiba"]');
  if (dateTibaEl) dateTibaEl.textContent = dArrStr;

  // Rank
  const rankEl = card.querySelector('[data-bind="rank"]');
  if (rankEl) {
    rankEl.textContent = '';
  }

  // Airline
  card.querySelector('[data-bind="maskapai"]').textContent     = t.maskapai;
  card.querySelector('[data-bind="maskapai_nama"]').textContent = shortAirlineName(t.maskapai_nama);

  // Class badge
  const classBadge = card.querySelector('[data-bind="kelas_label"]');
  if (classBadge) {
    classBadge.textContent = t.kelas_label;
    if (t.kelas === 'BUSINESS')        classBadge.classList.add('class-business');
    else if (t.kelas === 'FIRST')      classBadge.classList.add('class-first');
    else if (t.kelas === 'PREMIUM_ECONOMY') classBadge.classList.add('class-premium');
  }

  // Time & Route
  card.querySelector('[data-bind="jam_berangkat"]').textContent = t.jam_berangkat;
  card.querySelector('[data-bind="jam_tiba"]').textContent      = t.jam_tiba;
  card.querySelector('[data-bind="bandara_asal"]').textContent  = t.bandara_asal;
  card.querySelector('[data-bind="bandara_tujuan"]').textContent = t.bandara_tujuan;

  // Duration
  card.querySelector('[data-bind="durasi"]').textContent = formatDurasi(t.durasi_menit);

  // Transit label
  const transitLbl = card.querySelector('[data-bind="transit_label"]');
  if (t.is_transit) {
    const via = t.bandara_transit && t.bandara_transit !== '-' ? ` via ${t.bandara_transit}` : '';
    transitLbl.textContent = `Transit ${t.transit}x${via}`;
    transitLbl.classList.add('transit');
  } else {
    transitLbl.textContent = 'Langsung';
    transitLbl.classList.add('direct');
  }

  // Aircraft & Baggage chips
  card.querySelector('[data-bind="model_pesawat"]').textContent = t.model_pesawat;
  card.querySelector('[data-bind="bagasi_text"]').textContent = `Bagasi: ${t.bagasi_kg}kg / Kabin: ${t.cabin_baggage_kg}kg`;

  // Facilities
  const facWrap = card.querySelector('[data-bind="fac_icons"]');
  facWrap.innerHTML = `
    <span class="fac-icon ${t.meal ? 'yes' : 'no'}">Meal</span>
    <span class="fac-icon ${t.entertainment ? 'yes' : 'no'}">Entertainment</span>
    <span class="fac-icon ${t.usb ? 'yes' : 'no'}">USB</span>
    <span class="fac-icon ${t.power ? 'yes' : 'no'}">Power</span>
    <span class="fac-icon ${t.wifi_status !== 'no_wifi' ? 'yes' : 'no'}">WiFi</span>
  `;

  // Price
  card.querySelector('[data-bind="harga"]').textContent = t.harga_idr_formatted;

  // Kursi / Seat Features
  const seatWrap = card.querySelector('[data-bind="seat_features"]');
  const seatFeats = [];
  seatFeats.push(`<span class="group-item">${formatSeatType(t.seat_type)}</span>`);
  if (t.seat_pitch_inch && t.seat_pitch_inch > 0) {
    seatFeats.push(`<span class="group-item">Pitch: ${t.seat_pitch_inch}"</span>`);
  }
  if (t.seat_layout && t.seat_layout !== 'Unknown') {
    seatFeats.push(`<span class="group-item">Layout: ${t.seat_layout}</span>`);
  }
  if (seatWrap) seatWrap.innerHTML = seatFeats.join('');

  // Kebijakan & Info
  const extraWrap = card.querySelector('[data-bind="extra_features"]');
  const feats = [];
  feats.push(`<span class="group-item ${t.refundable ? 'yes' : 'no'}">Refundable</span>`);
  feats.push(`<span class="group-item ${t.reschedulable ? 'yes' : 'no'}">Reschedulable</span>`);
  if (t.visa_required) {
    feats.push(`<span class="group-item text-red">Visa Required</span>`);
  }
  if (t.waktu_berangkat_kategori) {
    feats.push(`<span class="group-item">Bgt: ${t.waktu_berangkat_kategori}</span>`);
  }
  if (t.waktu_tiba_kategori) {
    feats.push(`<span class="group-item">Tiba: ${t.waktu_tiba_kategori}</span>`);
  }
  if (t.flight_speed_kmh) {
    feats.push(`<span class="group-item">Speed: ${t.flight_speed_kmh} km/h</span>`);
  }
  
  if (extraWrap) {
    extraWrap.innerHTML = feats.join('');
  }

  return card;
}

function renderError(msg) {
  resultsContainer.innerHTML = `
    <div style="text-align:center;padding:40px 20px;color:var(--clr-muted);">
      <div style="font-size:2rem;margin-bottom:12px;">⚠️</div>
      <p style="color:var(--clr-red);font-weight:600;margin-bottom:8px;">Terjadi Kesalahan</p>
      <p>${msg}</p>
    </div>`;
}

/* ═══════════════════════════════════════════
   HELPER BUILDERS
   ═══════════════════════════════════════════ */
function facChip(icon, label, active) {
  const el = document.createElement('span');
  el.className = `fac-chip ${active ? 'yes' : 'no'}`;
  el.textContent = `${icon} ${label}`;
  return el;
}

function wifiChip(status) {
  const el = document.createElement('span');
  const map = {
    free:    ['WiFi Gratis', 'wifi-free'],
    paid:    ['WiFi Berbayar', 'wifi-paid'],
    no_wifi: ['No WiFi', 'wifi-no'],
  };
  const [label, cls] = map[status] || ['No WiFi', 'wifi-no'];
  el.className = `fac-chip ${cls}`;
  el.textContent = `${label}`;
  return el;
}

function policyTag(yes, no, value) {
  const el = document.createElement('span');
  el.className = `policy-tag ${value ? 'yes' : 'no'}`;
  el.textContent = value ? yes : no;
  return el;
}

/* ═══════════════════════════════════════════
   FORMATTERS
   ═══════════════════════════════════════════ */
function formatDurasi(menit) {
  const h = Math.floor(menit / 60);
  const m = menit % 60;
  if (h > 0 && m > 0) return `${h}j ${m}m`;
  if (h > 0) return `${h}j`;
  return `${m}m`;
}

function formatDate(str) {
  if (!str) return '';
  const d = new Date(str + 'T00:00:00');
  return d.toLocaleDateString('id-ID', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
}

function formatSeatType(raw) {
  if (!raw || raw === 'Unknown') return 'N/A';
  const map = {
    STANDARD_LEGROOM:       'Standard',
    ABOVE_AVERAGE_LEGROOM:  'Above Avg',
    BELOW_AVERAGE_LEGROOM:  'Below Avg',
    ANGLE_FLAT_SEAT:        'Angle Flat',
    CRADLE_RECLINER:        'Cradle',
    FULL_FLAT_POD:          'Full Flat Pod',
    FULL_FLAT_SEAT:         'Full Flat',
    PRIVATE_SUITE:          'Suite',
    RECLINER_SEAT:          'Recliner',
  };
  return map[raw] || `${raw}`;
}

function shortAirlineName(full) {
  // Remove the code in parentheses e.g. "Garuda Indonesia (GA)" → "Garuda Indonesia"
  return full.replace(/\s*\([A-Z0-9]+\)\s*$/, '').trim();
}
