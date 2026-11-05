# Gemelo Digital Clorofila — FASE 4 (PROSPECT-D oficial + ML)

Sistema de gemelo digital simplificado para un sensor espectral AS7341
(ESP32): recibe lecturas (simuladas o hardware), predice qué debería medir
el sensor según el estado de la hoja y visualiza ambas en un dashboard web
en tiempo real, con detección de anomalías.

## Estructura

```text
backend/
  main.py              # FastAPI + WS + REST; gemelo oficial, hoja/gemelo separados, ML
  twin_model.py        # Gemelo heuristico de la demo original (para dataset --fuente heuristico)
  sensor_simulator.py  # Simulador AS7341 con PROSPECT-D oficial (+ estrés relativo)
  validacion/          # Contraste vs paquete R: rejilla, scripts y fixture R
  dataset_sintetico.py # Generador de dataset sintetico (hojas virtuales)
  ridge.py             # Ridge con numpy puro (sin sklearn)
  prospect.py          # PROSPECT-D oficial (adapter de prospect_oficial)
  prospect_oficial/    # Tablas oficiales + matematicas contrastadas (GPLv3)
  entrenar_cab.py      # Entrena regresor base Cab <- canales
  modelo_ml.py         # Inferencia: carga el .npz y estima Cab
  requirements.txt
  data/                # dataset.csv + .meta.json (generado, no versionar)
  modelos/             # cab_ridge.npz + metricas (generado, no versionar)
backend/public/          # Frontend (dentro del paquete para el bundle; ver nota Vercel)
  index.html           # Controles + espectro doble + métricas + indicador
  static/
    style.css
    app.js             # WS con reconexión + fallback a sondeo + POST /api/config
    charts.js          # Espectro superpuesto medido vs. gemelo (Chart.js)
```

## Instalación

```powershell
pip install -r backend/requirements.txt
```

## Ejecución

```powershell
cd backend
python -m uvicorn main:app --reload --port 8000
```

Abrir **http://127.0.0.1:8000**.

- Badge "Conectado" + gráfico que se actualiza cada segundo.
- Sliders Cab (5–80 µg/cm²), Cw (0.005–0.05 cm) y N (1.0–2.5) mueven SOLO
  el gemelo; la hoja simulada es independiente (su Cab verdadero se muestra
  en el panel). "Reajustar gemelo a la hoja" los vuelve a alinear.
- Selector reflectancia/transmitancia, estrés simulado y **Cab estimado por
  ML** (Ridge entrenado en PROSPECT-D; solo en reflectancia).
- Al separar el gemelo de la hoja o al activar el estrés, la tarjeta de
  comparación se marca en rojo y aparece el aviso de anomalía
  (error relativo > 10 %).
- Si se reinicia el backend, el frontend reintenta cada 2 s.

## API

| Método | Ruta                   | Descripción                                      |
|--------|------------------------|--------------------------------------------------|
| GET    | `/`                    | Dashboard                                        |
| GET    | `/api/salud`           | `{"estado":"ok","fase":4,...,"ml_disponible"}`   |
| GET    | `/api/config`          | `{gemelo:{cab,cw,n}, hoja:{...}, modo, estres}`  |
| POST   | `/api/config`          | Todo validado o nada; `sincronizar:true` alinea  |
| GET    | `/api/modelo?cab=&cw=&modo=&n=` | Predicción PROSPECT-D oficial + índice  |
| WS     | `/ws`                  | lectura + predicción + comparación + Cab ML      |

Mensaje WS:

```json
{
  "timestamp": "...", "canales": {...}, "prediccion": {...},
  "comparacion": {"rmse": 12.1, "rmse_rel": 0.023, "sesgo": -2.4, "n_canales": 10},
  "anomalia": false,
  "cab_estimado_ml": 52.4,
  "gemelo": {"cab": 45.0, "cw": 0.015, "n": 1.5, "modo": "reflectancia", "indice_clorofila": 53.3},
  "hoja": {"cab_base": 45.0, "cab_verdadero": 45.8, "cw": 0.015, "n": 1.5},
  "orden_canales": ["F1", "...", "Clear", "NIR"]
}
```

`cab_estimado_ml` es null en transmitancia o sin modelo entrenado.

## Modelo de gemelo digital (dashboard: PROSPECT-D oficial)

1. **PROSPECT-D oficial** (`prospect_oficial/`): R(λ) y T(λ) para
   (Cab, Cw, N) más extras fijos (car=8, cant=1, cbrown=0, cm=0.005).
2. **Convolución** con la respuesta gaussiana de cada canal del AS7341.
3. **Calibración compartida** `cuentas = R·5000`: simulador y gemelo usan
   la misma escala; el RMSE basal es ~2-3 % (ruido + deriva leve).
4. **Hoja y gemelo separados**: la hoja simulada deriva ±2 µg/cm² y no
   cambia con los sliders; el gemelo sí. La discrepancia entre ambos
   dispara la anomalía (`rmse_rel > 0.10`), igual que el estrés.
5. **Cab estimado por ML** (Ridge entrenado en dataset oficial, solo
   reflectancia) junto al Cab supuesto del gemelo.
6. **Índice 0–100**: normalización lineal de Cab (5→0, 80→100).

## Modelo PROSPECT-D oficial (`prospect_oficial/`)

Matemáticas de PROSPECT-D (Jacquemoud & Baret 1990; Féret et al. 2017)
con las **tablas oficiales** (`prospect_d_spectra.txt` de prosail 2.0.5,
SHA256 verificado al cargar; ver `PROCEDENCIA.md`): `calctav`
(Stern 1964, Allen 1973), capa de Allen et al. (1969) y apilado exacto
de N fraccionario con Stokes (1862).

**Contraste ejecutado** contra el código real de prosail 2.0.5
(descargado de PyPI/GitHub, ejecutado sin instalar): 60 hojas aleatorias
con N fraccionario + 4 casos borde ⇒ **diferencia bit a bit 0.00e+00**
en R y T (400–2500 nm). Los avisos numéricos en regímenes extremos son
idénticos en ambas implementaciones.

Distancia con el antiguo modelo heurístico (canales AS7341): MAE de
330–623 cuentas según Cab (p. ej. Cab=40: F5 1378→612, F8 305→379).
El heurístico **no** era equivalente a PROSPECT-D y solo se conserva
para generar el dataset `--fuente heuristico` (`twin_model.py`).

Parámetros: N, Cab, Car, Cant, Cbrown, Cw, Cm. Verificado además:
`máx(R+T) ≤ 1` en 200 hojas aleatorias; Cab↑ ⇒ R↓ en azul/rojo;
N↑ ⇒ R↑ y T↓.

## Dataset sintético y modelo ML (inversión Cab <- AS7341)

Genera 10.000 hojas virtuales y entrena un regresor base, todo con numpy
(sin sklearn/pandas). Dos fuentes (`--fuente`): `heuristico` (gemelo
propio) y `prospect` (PROSPECT-D, con Car/Cant/Cbrown/Cm variables).

```powershell
cd backend
python dataset_sintetico.py --n 10000 --semilla 42 --salida data/dataset.csv
python dataset_sintetico.py --fuente prospect --n 10000 --semilla 42 --salida data/dataset_prospect.csv
python entrenar_cab.py --datos data/dataset.csv --salida modelos/cab_ridge
python entrenar_cab.py --datos data/dataset_prospect.csv --salida modelos/cab_ridge_prospect
```

- Muestreo: Cab ∼ U(5,80), Cw ∼ U(0.005,0.05), N ∼ U(1.0,2.5);
  en PROSPECT además Car ∼ U(2,16), Cant ∼ U(0,2), Cm ∼ U(0.003,0.012).
- 10 canales (F1–F8, Clear, NIR); `Clear` es banda ancha aproximada.
- Partición 70/15/15 asignada **antes** del ruido gaussiano (desv. por canal
  = `RUIDO` del simulador); ninguna hoja aparece en dos conjuntos.
- Modelo: Ridge sobre canales estandarizados (λ elegida en validación);
  solo los canales entran como predictores.

Resultados (test intacto, n=1500):

| Fuente      | Baseline MAE | Ridge MAE | Ridge RMSE | λ     |
|-------------|--------------|-----------|------------|-------|
| heurístico  | 18.81        | 3.71      | 4.59       | 0.01  |
| PROSPECT-D oficial | 18.81 | 6.54      | 8.09       | 10.0  |

El dataset PROSPECT es más difícil porque 6 parámetros varían y
confunden a Cab (p. ej. carotenoides en el azul, N en todo el espectro):
es el efecto físico esperado, no un error. Detalle en `modelos/*.metricas.json`.

**Límites:** evaluado en datos del mismo simulador (optimista frente a
campo); el bandpass por sí solo no reproduce el hardware real (falta
iluminación, ganancia e integración); Cw y N actúan como variabilidad,
no como magnitudes recuperables con este sensor. Hacen falta muestras
reales con Cab de referencia para validar. El contraste contra el
paquete R de los autores **está ejecutado**: coincidencia a 2.15e-15
en 12 casos (ver `backend/validacion/` y `PROCEDENCIA.md`).

## Despliegue en Vercel

Vercel serverless **no admite WebSockets**, por eso el frontend usa
`/ws` en local y pasa solo a sondeo `GET /api/lectura` (cada 2 s)
cuando el WebSocket no abre. El modelo ML viaja en el repo
(`backend/modelos/cab_ridge_prospect.npz`, 2 KB) para que el
despliegue tenga estimación de Cab sin regenerar nada.

```powershell
vercel login
vercel deploy
```

Notas:

- `vercel.json` dirige todo el tráfico a `backend/main.py` (sirve el
  frontend y la API desde el mismo proceso).
- Las dependencias salen de `backend/requirements.txt` (incluye scipy).
- `backend/data/*.csv` no se versiona; el simulador genera al vuelo.
- Límites del plan hobby: arranque en frío de 1-2 s (numpy/scipy) y
  cadencia de sondeo de 2 s; es una demo, no telemetría crítica.

## Modo hardware (ESP32 real)

El simulador es intercambiable: basta con sustituir `generar_lectura()` por
lecturas serie/MQTT del ESP32 con el mismo formato `{canales, timestamp}`.
La comparación y el dashboard funcionan sin cambios siempre que el ESP32
respete la misma escala de cuentas (mismo tiempo de integración y ganancia
que el `FACTOR_CALIBRACION` supuesto).

## Notas y limitaciones

- Valores en **cuentas ADC sintéticas**; el índice es una **estimación
  demostrativa**, no un diagnóstico agronómico calibrado.
- `Clear` es banda ancha aproximada (media × 1.8), `NIR2` no se duplica.
- `Cw` apenas influye fuera del NIR: estos canales no estiman agua con
  fiabilidad; el control de Cw tiene efecto demostrativo limitado.
  La sensibilidad al agua cerca de 910 nm es limitada frente a bandas
  como 1450/1940 nm, fuera del alcance del AS7341.
- Dashboard, simulador y dataset ML usan PROSPECT-D oficial; `twin_model.py`
  (heurístico) solo genera el dataset `--fuente heuristico`. Ningún modelo
  implica recuperar Cab, Cw y N de forma única con estos canales.
- Umbral de anomalía (10 %) arbitrario para la demo.
- `prospect_oficial/` se distribuye bajo **GPLv3** (tablas y estructura
  de `prosail`, Copyright J Gomez-Dans 2017-2018); ver `PROCEDENCIA.md`.
- Sin persistencia: no hay base de datos ni históricos (trabajo futuro).
