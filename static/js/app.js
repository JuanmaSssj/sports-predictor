/* Sports Predictor AI - Frontend Logic */

let currentSport = 'soccer';
let trainingActive = false;
let trainingInterval = null;
let refreshInterval  = null;

// ============================================================
// INICIALIZACION
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
  loadTop3(currentSport);
  loadPicks();
  // Auto-refresh cada 5 minutos
  refreshInterval = setInterval(() => {
    loadTop3(currentSport);
  }, 5 * 60 * 1000);
});

// ============================================================
// SELECCION DE DEPORTE
// ============================================================
function selectSport(sport, btn) {
  currentSport = sport;
  document.querySelectorAll('.sport-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const titles = {
    soccer:   '&#9917; TOP 3 JUEGOS DEL DIA - FUTBOL',
    baseball: '&#9918; TOP 3 JUEGOS DEL DIA - BEISBOL',
    nfl:      '&#127944; TOP 3 JUEGOS DEL DIA - NFL',
    nba:      '&#127936; TOP 3 JUEGOS DEL DIA - NBA',
  };
  document.getElementById('section-title').innerHTML = titles[sport] || 'TOP 3 JUEGOS';
  loadTop3(sport);
  loadPicks();
}

// ============================================================
// TOP 3 JUEGOS
// ============================================================
async function loadTop3(sport) {
  const container = document.getElementById('games-container');
  container.innerHTML = '<div class="loading">&#8987; Cargando partidos...</div>';
  try {
    const res  = await fetch(`/api/top3/${sport}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    if (!data.games || data.games.length === 0) {
      container.innerHTML = `
        <div class="no-games">
          <div class="icon">&#128683;</div>
          <p>No hay partidos de ${sport.toUpperCase()} hoy</p>
        </div>`;
      return;
    }
    container.innerHTML = data.games.map(renderGameCard).join('');
    if (data.updated) {
      document.getElementById('last-updated').textContent =
        'Actualizado: ' + new Date(data.updated).toLocaleTimeString('es-MX');
    }
  } catch (e) {
    container.innerHTML = `<div class="loading">Error cargando datos: ${e.message}</div>`;
  }
}

function renderGameCard(g) {
  const model  = g.model  || {};
  const edge   = g.edge   || {};
  const sharp  = g.sharp  || {};
  const weather = g.weather || {};
  const homeInj = g.home_injuries || {};
  const awayInj = g.away_injuries || {};
  const mc      = g.totals_mc || {};

  const ph = model.prob_home || 0.5;
  const pd = model.prob_draw;
  const pa = model.prob_away || (1 - ph);

  const sharpActive = sharp.sharp_active;
  const sharpDir    = sharp.combined_direction || 'NEUTRAL';
  const sharpClass  = sharpActive ? (sharpDir.includes('BUY') || sharpDir.includes('YES') ? 'sharp-yes' : 'sharp-no') : '';
  const sharpText   = sharpActive ? `&#128176; Sharp: <span class="${sharpClass}">${sharpDir}</span>` : '&#128176; Sharp: NEUTRAL';

  const signal = edge.signal || 'HOLD';
  const edgeClass = signal === 'BUY' ? 'edge-buy' : (signal === 'SELL' ? 'edge-sell' : 'edge-hold');
  const edgeText  = signal === 'BUY'
    ? `BUY ${edge.adjusted_edge > 0 ? '+' : ''}${((edge.adjusted_edge||0)*100).toFixed(1)}% EV`
    : (signal === 'SELL' ? `SELL ${((edge.adjusted_edge||0)*100).toFixed(1)}% EV` : 'HOLD');

  const gameTime = g.commence
    ? new Date(g.commence).toLocaleString('es-MX', {hour:'2-digit', minute:'2-digit', timeZoneName:'short'})
    : g.game_time || '';

  // Probabilidades ML
  let probHtml = '';
  if (pd !== undefined) {
    // Soccer: 3 resultados
    probHtml = `
      <div class="prob-box">
        <div class="prob-label">LOCAL</div>
        <div class="prob-value ${ph > 0.5 ? 'high' : 'mid'}">${(ph*100).toFixed(0)}%</div>
      </div>
      <div class="prob-box">
        <div class="prob-label">EMPATE</div>
        <div class="prob-value mid">${((pd||0)*100).toFixed(0)}%</div>
      </div>
      <div class="prob-box">
        <div class="prob-label">VISIT.</div>
        <div class="prob-value ${pa > 0.5 ? 'high' : 'mid'}">${(pa*100).toFixed(0)}%</div>
      </div>`;
  } else {
    probHtml = `
      <div class="prob-box">
        <div class="prob-label">LOCAL</div>
        <div class="prob-value ${ph > 0.5 ? 'high' : 'mid'}">${(ph*100).toFixed(0)}%</div>
      </div>
      <div class="prob-box">
        <div class="prob-label">VISIT.</div>
        <div class="prob-value ${pa > 0.5 ? 'high' : 'mid'}">${(pa*100).toFixed(0)}%</div>
      </div>`;
  }

  // Mercados secundarios
  let marketsHtml = '';
  if (mc.over_prob !== undefined) {
    const overClass  = mc.over_prob > 0.55 ? 'over' : 'under';
    const underClass = mc.under_prob > 0.55 ? 'over' : 'under';
    marketsHtml = `
      <div class="market-row">
        <span class="market-pill ${overClass}">Over ${mc.line}: ${(mc.over_prob*100).toFixed(0)}%</span>
        <span class="market-pill ${underClass}">Under: ${(mc.under_prob*100).toFixed(0)}%</span>
        ${mc.expected ? `<span class="market-pill">xTotal: ${mc.expected.toFixed(1)}</span>` : ''}
      </div>`;
  } else if (mc['over_2.5'] !== undefined) {
    const o25 = mc['over_2.5'];
    marketsHtml = `
      <div class="market-row">
        <span class="market-pill ${o25 > 0.5 ? 'over' : 'under'}">Over 2.5: ${(o25*100).toFixed(0)}%</span>
        <span class="market-pill ${mc['over_1.5'] > 0.7 ? 'over' : 'under'}">Over 1.5: ${((mc['over_1.5']||0)*100).toFixed(0)}%</span>
        <span class="market-pill">BTTS: ${((mc.btts||0)*100).toFixed(0)}%</span>
      </div>`;
  }

  // Lesiones
  const injHtml = (homeInj.summary || awayInj.summary)
    ? `<div class="info-row"><span class="icon">&#129304;</span>
        <span>${homeInj.summary || 'OK'} | ${awayInj.summary || 'OK'}</span></div>`
    : '';

  // Clima
  const wxHtml = weather.description
    ? `<div class="info-row"><span class="icon">&#127780;&#65039;</span>
        <span class="${weather.impact === 'UNDER' ? 'sharp-no' : ''}">${weather.description}</span></div>`
    : '';

  return `
  <div class="game-card ${sharpActive ? 'sharp-active' : ''}">
    <div class="game-teams">${g.away_team} @ ${g.home_team}</div>
    <div class="game-time">${gameTime}</div>
    <div class="prob-row">${probHtml}</div>
    ${marketsHtml}
    <div class="info-row"><span class="icon">&#128176;</span><span>${sharpText}</span></div>
    ${injHtml}
    ${wxHtml}
    <span class="edge-badge ${edgeClass}">${edgeText}</span>
    ${g.reasoning ? `<div class="reasoning">${g.reasoning}</div>` : ''}
  </div>`;
}

// ============================================================
// PICKS
// ============================================================
async function loadPicks() {
  const panels = ['fuerte', 'ganador', 'ratonero', 'props'];
  panels.forEach(p => {
    document.getElementById(`pick-${p}`).innerHTML = '<div class="loading">Cargando...</div>';
  });
  try {
    const res  = await fetch(`/api/picks/${currentSport}`);
    const data = await res.json();
    if (data.error || !data.picks) throw new Error(data.error || 'Sin picks');
    renderPicks(data.picks);
  } catch (e) {
    panels.forEach(p => {
      document.getElementById(`pick-${p}`).innerHTML =
        `<div class="loading">${e.message}</div>`;
    });
  }
}

function renderPicks(picks) {
  // Apuesta Fuerte
  const af = picks.apuesta_fuerte;
  document.getElementById('pick-fuerte').innerHTML = af ? `
    <div class="pick-card fuerte">
      <div class="pick-title">&#128170; APUESTA FUERTE</div>
      <div class="pick-main">${af.pick}</div>
      <div class="pick-odds">${af.moneyline > 0 ? '+' : ''}${af.moneyline}</div>
      <div class="pick-meta">
        Partido: ${af.game}<br>
        Prob. Modelo: ${((af.model_prob||0)*100).toFixed(1)}% |
        Edge: +${((af.edge||0)*100).toFixed(1)}% |
        Confianza: ${af.confidence}<br>
        Kelly 1/4: $${af.kelly_usd || 0}<br>
        ${af.reasoning || ''}
      </div>
    </div>` : '<div class="no-games"><p>No hay apuesta fuerte disponible hoy</p></div>';

  // Parlay Ganador
  const pg = picks.parlay_ganador || [];
  document.getElementById('pick-ganador').innerHTML = pg.length >= 2 ? `
    <div class="pick-card ganador">
      <div class="pick-title">&#127919; PARLAY GANADOR (2 PATAS)</div>
      <div class="pick-legs">
        ${pg.slice(0,2).map(p => `
          <div class="pick-leg">
            <span>${p.pick} <small style="color:var(--text2)">${p.game}</small></span>
            <span class="leg-odds">${p.moneyline > 0 ? '+' : ''}${p.moneyline}</span>
          </div>`).join('')}
      </div>
      <div class="combined-odds">
        Momio combinado: <span class="big">${combinedOdds(pg.slice(0,2).map(p=>p.moneyline))}</span>
      </div>
    </div>` : '<div class="no-games"><p>No hay parlay ganador disponible hoy</p></div>';

  // Parlay Ratonero
  const pr = picks.parlay_ratonero || {};
  const prLegs = pr.picks || [];
  document.getElementById('pick-ratonero').innerHTML = prLegs.length >= 4 ? `
    <div class="pick-card ratonero">
      <div class="pick-title">&#128045; PARLAY RATONERO (${prLegs.length} PATAS)</div>
      <div class="pick-legs">
        ${prLegs.map(p => `
          <div class="pick-leg">
            <span>${p.pick} <small style="color:var(--text2)">${p.game}</small></span>
            <span class="leg-odds">${p.moneyline > 0 ? '+' : ''}${p.moneyline}</span>
          </div>`).join('')}
      </div>
      <div class="combined-odds">
        Momio combinado: <span class="big">${pr.combined_odds > 0 ? '+' : ''}${pr.combined_odds}</span>
      </div>
    </div>` : '<div class="no-games"><p>No hay suficientes picks para parlay ratonero hoy</p></div>';

  // Props (placeholder hasta tener endpoint de props)
  document.getElementById('pick-props').innerHTML = `
    <div class="pick-card">
      <div class="pick-title">&#128100; PROPS DE JUGADORES</div>
      <div class="pick-meta" style="padding:20px;text-align:center;color:var(--text2)">
        Props disponibles cuando hay partidos con datos de jugadores.<br>
        Selecciona un deporte con partidos activos.
      </div>
    </div>`;
}

function combinedOdds(oddsList) {
  if (!oddsList || !oddsList.length) return 'N/A';
  let decimal = 1.0;
  for (const o of oddsList) {
    if (!o) continue;
    decimal *= o > 0 ? (o/100 + 1) : (100/Math.abs(o) + 1);
  }
  const american = decimal >= 2
    ? Math.round((decimal-1)*100)
    : Math.round(-100/(decimal-1));
  return (american > 0 ? '+' : '') + american;
}

function showPickTab(tab, btn) {
  document.querySelectorAll('.pick-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.pick-panel').forEach(p => {
    p.classList.remove('active');
    p.style.display = 'none';
  });
  btn.classList.add('active');
  const panel = document.getElementById(`pick-${tab}`);
  panel.style.display = 'block';
  panel.classList.add('active');
}

// ============================================================
// ENTRENAMIENTO
// ============================================================
async function toggleTraining() {
  if (!trainingActive) {
    await fetch('/api/training/start', {method: 'POST'});
    trainingActive = true;
    document.getElementById('btn-train').textContent = '&#9889; ENTRENANDO...';
    document.getElementById('btn-train').classList.add('active');
    document.getElementById('training-badge').className = 'badge badge-on';
    document.getElementById('training-badge').innerHTML = '&#9899; IA ENTRENANDO';
    document.getElementById('training-panel').classList.remove('hidden');
    document.getElementById('history-section').style.display = 'block';
    trainingInterval = setInterval(updateTrainingStatus, 10000);
    updateTrainingStatus();
  } else {
    await fetch('/api/training/stop', {method: 'POST'});
    trainingActive = false;
    document.getElementById('btn-train').innerHTML = '&#9889; ENTRENAR IA';
    document.getElementById('btn-train').classList.remove('active');
    document.getElementById('training-badge').className = 'badge badge-off';
    document.getElementById('training-badge').innerHTML = '&#9899; IA INACTIVA';
    document.getElementById('training-panel').classList.add('hidden');
    clearInterval(trainingInterval);
  }
}

async function updateTrainingStatus() {
  try {
    const res  = await fetch('/api/training/status');
    const data = await res.json();
    document.getElementById('tr-winrate').textContent  = data.win_rate + '%';
    document.getElementById('tr-total').textContent    = data.total_analyzed;
    document.getElementById('tr-correct').textContent  = data.total_correct;
    document.getElementById('tr-last10').textContent   = (data.last_10 || []).join(' ');
    document.getElementById('tr-status').textContent   = data.status || '';
    document.getElementById('tr-game').textContent     = data.current_game || '';
    loadHistory();
  } catch (e) {
    console.error('Training status error:', e);
  }
}

async function loadHistory() {
  try {
    const res  = await fetch('/api/training/history');
    const data = await res.json();
    const container = document.getElementById('history-container');
    if (!data.history || !data.history.length) {
      container.innerHTML = '<div class="loading">Sin historial aun...</div>';
      return;
    }
    container.innerHTML = `
      <table class="history-table">
        <thead>
          <tr>
            <th>DEPORTE</th><th>PARTIDO</th><th>PREDICCION</th>
            <th>PROB.</th><th>RESULTADO</th><th>CORRECTO</th><th>FECHA</th>
          </tr>
        </thead>
        <tbody>
          ${data.history.map(h => `
            <tr>
              <td>${h.sport}</td>
              <td style="font-size:0.75rem">${h.game}</td>
              <td><strong>${h.prediction}</strong></td>
              <td>${h.prob ? (h.prob*100).toFixed(1)+'%' : '-'}</td>
              <td>${h.actual || '<span class="pending">Pendiente</span>'}</td>
              <td>${h.correct === null
                ? '<span class="pending">-</span>'
                : h.correct
                  ? '<span class="win">&#10003; W</span>'
                  : '<span class="loss">&#10007; L</span>'}</td>
              <td style="font-size:0.72rem;color:var(--text2)">${h.timestamp ? new Date(h.timestamp).toLocaleDateString('es-MX') : ''}</td>
            </tr>`).join('')}
        </tbody>
      </table>`;
  } catch (e) {
    console.error('History error:', e);
  }
}
