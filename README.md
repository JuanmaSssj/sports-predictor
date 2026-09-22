# 🏆 Sports Predictor AI

Sistema de predicción deportiva con IA, sabermétricas avanzadas, sharp money (Kalshi/Polymarket) y auto-entrenamiento.

## Deportes cubiertos
- ⚽ Fútbol (EPL, La Liga, MLS, Liga MX, UCL)
- ⚾ Béisbol (MLB)
- 🏈 NFL
- 🏀 NBA

## Características
- **Top 3 juegos del día** con probabilidades ML, Over/Under, Handicap
- **Picks automáticos**: Apuesta Fuerte, Parlay Ganador, Parlay Ratonero, Props
- **Sharp Money**: Kalshi + Polymarket + VPIN
- **Datos reales**: lesiones ESPN, clima Open-Meteo, stats oficiales
- **Auto-entrenamiento**: la IA analiza, predice y aprende de resultados reales

## Deploy en Railway (5 minutos)

### 1. Ir a railway.app
1. Ve a https://railway.app
2. Click **"New Project"**
3. Selecciona **"Deploy from GitHub/GitLab"**
4. Conecta tu cuenta GitLab
5. Selecciona el repo `juanma-group4/sports-predictor`

### 2. Variables de entorno (OBLIGATORIO)
En Railway → tu proyecto → **Variables**, agrega:

| Variable | Valor |
|----------|-------|
| `ODDS_API_KEY` | `3e9a896dae9dbeab2c980e875398d460` |
| `FLASK_SECRET_KEY` | cualquier texto aleatorio |

### 3. Deploy
Railway detecta el `Procfile` y `railway.json` automáticamente.
En 2-3 minutos tienes una URL pública tipo `https://sports-predictor-xxx.railway.app`

## Fuentes de datos (todas gratuitas)

| Dato | Fuente | API Key |
|------|--------|---------|
| Momios/líneas | The-Odds-API | ✅ Ya configurada |
| MLB stats | statsapi.mlb.com | ❌ No necesita |
| NBA stats | stats.nba.com | ❌ No necesita |
| NFL stats | ESPN API | ❌ No necesita |
| Soccer stats | ESPN API | ❌ No necesita |
| Lesiones | ESPN | ❌ No necesita |
| Clima | Open-Meteo | ❌ No necesita |
| Sharp money | Kalshi + Polymarket | ❌ No necesita |

## Sabermétricas implementadas

### Béisbol
FIP, xFIP, wOBA, wRC+, BABIP, ISO, OPS+, K%, BB%, Pythagorean Expectation, Pitcher Fatigue Factor, Bullpen Usage Index

### Basquetbol
ORtg, DRtg, NetRtg, Pace, eFG%, TS%, Four Factors (Dean Oliver), Back-to-back penalty, Rest advantage

### NFL
DVOA proxy, ANY/A, EPA proxy, Success Rate, Turnover Differential, Red Zone %, 3rd Down %, Home Field Advantage

### Fútbol Soccer
xG, xGA, Dixon-Coles attack/defense strength, Poisson score matrix, Form weight decay, H2H weighted average

## Estructura del proyecto
```
sports-predictor/
├── app.py                    # Servidor Flask
├── config.py                 # Configuración
├── requirements.txt
├── Procfile                  # Para Railway/Render
├── railway.json              # Config Railway
├── scrapers/
│   ├── odds_scraper.py       # The-Odds-API
│   ├── mlb_scraper.py        # MLB Stats API
│   ├── nba_scraper.py        # NBA Stats
│   ├── nfl_scraper.py        # ESPN NFL
│   ├── soccer_scraper.py     # ESPN Soccer
│   ├── injuries_scraper.py   # ESPN Injuries
│   ├── weather_scraper.py    # Open-Meteo
│   └── sharp_money_scraper.py # Kalshi + Polymarket
├── models/
│   ├── sabermetrics.py       # Todas las métricas
│   ├── monte_carlo.py        # Simulación MC
│   ├── edge_calculator.py    # EV+, Kelly, Picks
│   └── trainer.py            # Auto-entrenamiento
├── templates/
│   └── index.html            # UI completa
└── static/
    ├── css/style.css
    └── js/app.js
```
