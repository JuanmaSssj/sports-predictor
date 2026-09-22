/* Sports Predictor AI */
let currentSport  = 'soccer';
let trainingActive = true;  // arranca activo
let trainingInterval = null;

const SPORT_TITLES = {
  soccer:   '&#9917; TOP 3 JUEGOS DE HOY - FUTBOL',
  baseball: '&#9918; TOP 3 JUEGOS DE HOY - BEISBOL',
  nfl:      '&#127944; TOP 3 JUEGOS DE HOY - NFL',
  nba:      '&#127936; TOP 3 JUEGOS DE HOY - NBA',
};

document.addEventListener('DOMContentLoaded', () => {
  updateClock();
  setInterval(updateClock, 60000);
  loadTop3(currentSport);
  loadUpcoming(currentSport);
  loadPicks();
  // Polling entrenamiento cada 10s
  trainingInterval = setInterval(updateTrainingStatus, 10000);
  updateTrainingStatus();
  loadHistory();
  // Refresh top3 cada 5 min
  setInterval(() => { loadTop3(currentSport); loadUpcoming(currentSport); }, 300000);
});

function updateClock() {
  const el = document.getElementById('time-mx');
  if (!el) return;
  const now = new Date();
  const mx  = now.toLocaleString('es-MX', {
    timeZone: 'America/Mexico_City',
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: true
  });
  el.textContent = mx + ' CT';
}

function selectSport(sport, btn) {
  currentSport = sport;
  document.querySelectorAll('.sport-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('section-title').innerHTML = SPORT_TITLES[sport] || 'TOP 3';
  loadTop3(sport);
  loadUpcoming(sport);
  loadPicks();
}

// ---- TOP 3 ----
async function loadTop3(sport) {
  const c = document.getElementById('games-container');
  c.innerHTML = '<div class="loading">&#8987; Cargando partidos de hoy...</div>';
  try {
    const res  = await fetch(`/api/top3/${sport}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    if (!data.games || !data.games.length) {
      c.innerHTML = `<div class="no-games"><div class="icon">&#128683;</div><p>${data.message || 'No hay partidos hoy'}</p></div>`;
      return;
    }
    c.innerHTML = data.games.map(renderGameCard).join('');
    if (data.updated) document.getElementById('last-updated').textContent = 'Act: ' + data.updated;
  } catch(e) {
    c.innerHTML = `<div class="loading">Error: ${e.message}</div>`;
  }
}

// ---- PROXIMOS ----
async function loadUpcoming(sport) {
  const c = document.getElementById('upcoming-container');
  c.innerHTML = '<div class="loading">&#8987; Cargando proximos...</div>';
  try {
    const res  = await fetch(`/api/upcoming/${sport}`);
    const data = await res.json();
    if (!data.games || !data.games.length) {
      c.innerHTML = '<div class="loading">No hay proximos partidos en los siguientes 3 dias</div>';
      return;
    }
    c.innerHTML = data.games.map(g => `
      <div class="upcoming-card">
        <div class="upcoming-teams">${g.away_team} <span>@</span> ${g.home_team}</div>
        <div class="upcoming-meta">
          <span class="upcoming-time">&#128197; ${g.time_mx || g.commence}</span>
          <span class="upcoming-league">${formatLeague(g.sport)}</span>
          ${g.total_line ? `<span class="upcoming-total">Total: ${g.total_line}</span>` : ''}
          ${g.ml_home ? `<span class="upcoming-ml">ML: ${g.ml_home > 0 ? '+' : ''}${g.ml_home}</span>` : ''}
        </div>
      </div>`).join('');
  } catch(e) {
    c.innerHTML = `<div class="loading">Error: ${e.message}</div>`;
  }
}

function formatLeague(sport) {
  const map = {
    'baseball_mlb': 'MLB', 'baseball_kbo': 'KBO', 'baseball_npb': 'NPB',
    'soccer_mexico_ligamx': 'Liga MX', 'soccer_epl': 'Premier League',
    'soccer_spain_la_liga': 'La Liga', 'soccer_germany_bundesliga': 'Bundesliga',
    'soccer_italy_serie_a': 'Serie A', 'soccer_france_ligue_one': 'Ligue 1',
    'soccer_uefa_champs_league': 'UCL', 'soccer_uefa_europa_league': 'Europa League',
    'soccer_usa_mls': 'MLS', 'americanfootball_nfl': 'NFL',
    'americanfootball_ncaaf': 'NCAAF', 'basketball_nba': 'NBA',
    'basketball_wnba': 'WNBA', 'basketball_nbl': 'NBL',
  };
  return map[sport] || sport;
}

// ---- GAME CARD ----
function renderGameCard(g) {
  const model  = g.model  || {};
  const edge   = g.edge   || {};
  const sharp  = g.sharp  || {};
  const weather = g.weather || {};
  const mc     = g.totals_mc || {};
  const ph = model.prob_home || 0.5;
  const pd = model.prob_draw;
  const pa = model.prob_away || (1 - ph);
  const sharpActive = sharp.sharp_active;
  const sharpDir    = sharp.combined_direction || 'NEUTRAL';
  const signal = edge.signal || 'HOLD';
  const edgeClass = signal === 'BUY' ? 'edge-buy' : (signal === 'SELL' ? 'edge-sell' : 'edge-hold');
  const adj = edge.adjusted_edge || 0;
  const edgeText = signal === 'BUY'
    ? `BUY +${(adj*100).toFixed(1)}% EV`
    : signal === 'SELL' ? `SELL ${(adj*100).toFixed(1)}% EV` : 'HOLD';

  let probHtml = '';
  if (pd !== undefined) {
    probHtml = `
      <div class="prob-box"><div class="prob-label">LOCAL</div><div class="prob-value ${ph>0.5?'high':'mid'}">${(ph*100).toFixed(0)}%</div></div>
      <div class="prob-box"><div class="prob-label">EMPATE</div><div class="prob-value mid">${((pd||0)*100).toFixed(0)}%</div></div>
      <div class="prob-box"><div class="prob-label">VISIT.</div><div class="prob-value ${pa>0.5?'high':'mid'}">${(pa*100).toFixed(0)}%</div></div>`;
  } else {
    probHtml = `
      <div class="prob-box"><div class="prob-label">LOCAL</div><div class="prob-value ${ph>0.5?'high':'mid'}">${(ph*100).toFixed(0)}%</div></div>
      <div class="prob-box"><div class="prob-label">VISIT.</div><div class="prob-value ${pa>0.5?'high':'mid'}">${(pa*100).toFixed(0)}%</div></div>`;
  }

  let marketsHtml = '';
  if (mc.over_prob !== undefined) {
    marketsHtml = `<div class="market-row">
      <span class="market-pill ${mc.over_prob>0.55?'over':'under'}">Over ${mc.line}: ${(mc.over_prob*100).toFixed(0)}%</span>
      <span class="market-pill ${mc.under_prob>0.55?'over':'under'}">Under: ${(mc.under_prob*100).toFixed(0)}%</span>
      ${mc.expected?`<span class="market-pill">xTotal: ${parseFloat(mc.expected).toFixed(1)}</span>`:''}
    </div>`;
  } else if (mc['over_2.5'] !== undefined) {
    marketsHtml = `<div class="market-row">
      <span class="market-pill ${mc['over_2.5']>0.5?'over':'under'}">Over 2.5: ${(mc['over_2.5']*100).toFixed(0)}%</span>
      <span class="market-pill ${mc['over_1.5']>0.7?'over':'under'}">Over 1.5: ${((mc['over_1.5']||0)*100).toFixed(0)}%</span>
      <span class="market-pill">BTTS: ${((mc.btts||0)*100).toFixed(0)}%</span>
    </div>`;
  }

  const sharpClass = sharpActive ? (sharpDir.includes('BUY')||sharpDir.includes('YES') ? 'sharp-yes' : 'sharp-no') : '';
  const homeInj = g.home_injuries || {};
  const awayInj = g.away_injuries || {};

  return `
  <div class="game-card ${sharpActive?'sharp-active':''}">
    <div class="game-league">${formatLeague(g.sport)}</div>
    <div class="game-teams">${g.away_team} @ ${g.home_team}</div>
    <div class="game-time">&#128336; ${g.time_mx || ''}</div>
    <div class="prob-row">${probHtml}</div>
    ${marketsHtml}
    ${g.spread_line!=null?`<div class="info-row"><span class="icon">&#9878;</span><span>Handicap: ${g.home_team} ${g.spread_line>0?'+':''}${g.spread_line}</span></div>`:''}
    <div class="info-row"><span class="icon">&#128176;</span><span class="${sharpClass}">Sharp: ${sharpActive?sharpDir:'NEUTRAL'}</span></div>
    ${homeInj.summary||awayInj.summary?`<div class="info-row"><span class="icon">&#129304;</span><span>${homeInj.summary||''} ${awayInj.summary?'| '+awayInj.summary:''}</span></div>`:''}
    ${weather.description?`<div class="info-row"><span class="icon">&#127780;</span><span class="${weather.impact==='UNDER'?'sharp-no':''}">${weather.description}</span></div>`:''}
    <span class="edge-badge ${edgeClass}">${edgeText}</span>
    ${g.reasoning?`<div class="reasoning">${g.reasoning}</div>`:''}
  </div>`;
}

// ---- PICKS ----
async function loadPicks() {
  ['fuerte','ganador','ratonero','props'].forEach(p => {
    const el = document.getElementById(`pick-${p}`);
    if (el) el.innerHTML = '<div class="loading">Cargando...</div>';
  });
  try {
    const res  = await fetch(`/api/picks/${currentSport}`);
    const data = await res.json();
    if (!data.picks) throw new Error(data.message || 'Sin picks');
    renderPicks(data.picks);
  } catch(e) {
    ['fuerte','ganador','ratonero','props'].forEach(p => {
      const el = document.getElementById(`pick-${p}`);
      if (el) el.innerHTML = `<div class="loading">${e.message}</div>`;
    });
  }
}

function renderPicks(picks) {
  const af = picks.apuesta_fuerte;
  document.getElementById('pick-fuerte').innerHTML = af ? `
    <div class="pick-card fuerte">
      <div class="pick-title">&#128170; APUESTA FUERTE</div>
      <div class="pick-main">${af.pick}</div>
      <div class="pick-odds">${af.moneyline>0?'+':''}${af.moneyline}</div>
      <div class="pick-meta">Partido: ${af.game}<br>Prob: ${((af.model_prob||0)*100).toFixed(1)}% | Edge: +${((af.edge||0)*100).toFixed(1)}% | Confianza: ${af.confidence}<br>Kelly 1/4: $${af.kelly_usd||0}<br>${af.reasoning||''}</div>
    </div>` : '<div class="no-games"><p>No hay apuesta fuerte hoy</p></div>';

  const pg = picks.parlay_ganador || [];
  document.getElementById('pick-ganador').innerHTML = pg.length >= 2 ? `
    <div class="pick-card ganador">
      <div class="pick-title">&#127919; PARLAY GANADOR</div>
      <div class="pick-legs">${pg.slice(0,2).map(p=>`
        <div class="pick-leg"><span>${p.pick} <small>${p.game}</small></span><span class="leg-odds">${p.moneyline>0?'+':''}${p.moneyline}</span></div>`).join('')}
      </div>
      <div class="combined-odds">Combinado: <span class="big">${combinedOdds(pg.slice(0,2).map(p=>p.moneyline))}</span></div>
    </div>` : '<div class="no-games"><p>No hay parlay ganador hoy</p></div>';

  const pr = picks.parlay_ratonero || {};
  const prLegs = pr.picks || [];
  document.getElementById('pick-ratonero').innerHTML = prLegs.length >= 4 ? `
    <div class="pick-card ratonero">
      <div class="pick-title">&#128045; PARLAY RATONERO (${prLegs.length} PATAS)</div>
      <div class="pick-legs">${prLegs.map(p=>`
        <div class="pick-leg"><span>${p.pick} <small>${p.game}</small></span><span class="leg-odds">${p.moneyline>0?'+':''}${p.moneyline}</span></div>`).join('')}
      </div>
      <div class="combined-odds">Combinado: <span class="big">${pr.combined_odds>0?'+':''}${pr.combined_odds}</span></div>
    </div>` : '<div class="no-games"><p>No hay suficientes picks para parlay ratonero</p></div>';

  document.getElementById('pick-props').innerHTML = `
    <div class="pick-card"><div class="pick-title">&#128100; PROPS DE JUGADORES</div>
    <div class="pick-meta" style="padding:20px;text-align:center;color:var(--text2)">Props disponibles con partidos activos del deporte seleccionado.</div></div>`;
}

function combinedOdds(list) {
  if (!list || !list.length) return 'N/A';
  let d = 1.0;
  for (const o of list) { if (!o) continue; d *= o > 0 ? o/100+1 : 100/Math.abs(o)+1; }
  const a = d >= 2 ? Math.round((d-1)*100) : Math.round(-100/(d-1));
  return (a > 0 ? '+' : '') + a;
}

function showPickTab(tab, btn) {
  document.querySelectorAll('.pick-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.pick-panel').forEach(p => p.style.display = 'none');
  btn.classList.add('active');
  document.getElementById(`pick-${tab}`).style.display = 'block';
}

// ---- ENTRENAMIENTO ----
async function toggleTraining() {
  if (trainingActive) {
    await fetch('/api/training/stop', {method:'POST'});
    trainingActive = false;
    document.getElementById('btn-train').innerHTML = '&#9889; ENTRENAR IA';
    document.getElementById('btn-train').classList.remove('active');
    document.getElementById('training-badge').className = 'badge badge-off';
    document.getElementById('training-badge').innerHTML = '&#9899; IA INACTIVA';
    document.getElementById('training-panel').style.display = 'none';
    clearInterval(trainingInterval);
  } else {
    await fetch('/api/training/start', {method:'POST'});
    trainingActive = true;
    document.getElementById('btn-train').innerHTML = '&#9632; DETENER IA';
    document.getElementById('btn-train').classList.add('active');
    document.getElementById('training-badge').className = 'badge badge-on';
    document.getElementById('training-badge').innerHTML = '&#9899; IA ENTRENANDO';
    document.getElementById('training-panel').style.display = 'block';
    trainingInterval = setInterval(updateTrainingStatus, 10000);
    updateTrainingStatus();
  }
}

async function updateTrainingStatus() {
  try {
    const res  = await fetch('/api/training/status');
    const data = await res.json();
    document.getElementById('tr-winrate').textContent  = data.win_rate + '%';
    document.getElementById('tr-total').textContent    = data.total_analyzed;
    document.getElementById('tr-correct').textContent  = data.total_correct;
    document.getElementById('tr-last10').textContent   = (data.last_10||[]).join(' ');
    document.getElementById('tr-status').textContent   = data.status || '';
    document.getElementById('tr-game').textContent     = data.current_game || '';
    loadHistory();
  } catch(e) { console.error('Training status error:', e); }
}

async function loadHistory() {
  try {
    const res  = await fetch('/api/training/history');
    const data = await res.json();
    const c    = document.getElementById('history-container');
    if (!data.history || !data.history.length) {
      c.innerHTML = '<div class="loading">La IA aun no tiene predicciones registradas...</div>';
      return;
    }
    c.innerHTML = `<table class="history-table">
      <thead><tr><th>DEPORTE</th><th>PARTIDO</th><th>PRED.</th><th>PROB.</th><th>RESULTADO</th><th>OK</th><th>FECHA</th></tr></thead>
      <tbody>${data.history.map(h=>`
        <tr>
          <td>${h.sport}</td>
          <td style="font-size:.75rem">${h.game}</td>
          <td><strong>${h.prediction}</strong></td>
          <td>${h.prob?(h.prob*100).toFixed(1)+'%':'-'}</td>
          <td>${h.actual||'<span class="pending">Pendiente</span>'}</td>
          <td>${h.correct===null?'<span class="pending">-</span>':h.correct?'<span class="win">&#10003; W</span>':'<span class="loss">&#10007; L</span>'}</td>
          <td style="font-size:.72rem">${h.timestamp?new Date(h.timestamp).toLocaleDateString('es-MX'):''}</td>
        </tr>`).join('')}
      </tbody></table>`;
  } catch(e) { console.error('History error:', e); }
}
