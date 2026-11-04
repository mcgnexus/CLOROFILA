# Gemelo Digital Clorofila — FASE 3 (Final)

Sistema de gemelo digital simplificado para un sensor espectral AS7341
(ESP32): recibe lecturas (simuladas o hardware), predice qué debería medir
el sensor según el estado de la hoja y visualiza ambas en un dashboard web
en tiempo real, con detección de anomalías.

## Estructura

```text
backend/
  main.py              # FastAPI + WebSocket /ws + API REST + sirve el frontend
  twin_model.py        # Gemelo: R/T(λ; Cab, Cw) -> 10 canales + comparacion
  sensor_simulator.py  # Simulador AS7341 basado en el gemelo (+ modo estrés)
  dataset_sintetico.py # Generador de dataset sintetico (hojas virtuales)
  ridge.py             # Ridge con numpy puro (sin sklearn)
  prospect.py          # PROSPECT-D: formalismo real (E1, Fresnel, Stokes)
  prospect_datos.py    # Coeficientes de trabajo aproximados (sustituibles)
  entrenar_cab.py      # Entrena regresor base Cab <- canales
  modelo_ml.py         # Inferencia: carga el .npz y estima Cab
  requirements.txt
  data/                # dataset.csv + .meta.json (generado, no versionar)
  modelos/             # cab_ridge.npz + metricas (generado, no versionar)
frontend/
  index.html           # Controles + espectro doble + métricas + indicador
  style.css
  app.js               # WS con reconexión + controles via POST /api/config
  charts.js            # Espectro superpuesto medido vs. gemelo (Chart.js)
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
- Sliders Cab (5–80 µg/cm²), Cw (0.005–0.05 cm) y N (1.0–2.5), selector
  reflectancia/transmitancia e interruptor de estrés simulado.
- Al activar el estrés, la tarjeta de comparación se marca en rojo y
  aparece el aviso de anomalía (error relativo > 10 %).
- Si se reinicia el backend, el frontend reintenta cada 2 s.

## API

| Método | Ruta                   | Descripción                                      |
|--------|------------------------|--------------------------------------------------|
| GET    | `/`                    | Dashboard                                        |
| GET    | `/api/salud`           | `{"estado":"ok","fase":3,...}`                   |
| GET    | `/api/config`          | Configuración actual `{cab, cw, n, modo, estres}` |
| POST   | `/api/config`          | Actualiza (parcial o total) cab/cw/n/modo/estres |
| GET    | `/api/modelo?cab=&cw=&modo=&n=` | Predicción del gemelo + índice          |
| WS     | `/ws`                  | 1 msg/s: lectura + predicción + comparación      |

Mensaje WS:

```json
{
  "timestamp": "...", "canales": {...}, "prediccion": {...},
  "comparacion": {"rmse": 39.4, "rmse_rel": 0.039, "sesgo": -11.8, "n_canales": 10},
  "anomalia": false,
  "gemelo": {"cab": 45.0, "cw": 0.015, "n": 1.5, "modo": "reflectancia", "indice_clorofila": 53.3},
  "orden_canales": ["F1", "...", "Clear", "NIR"]
}
```

## Modelo de gemelo digital

1. **Absorción de clorofila** `A(λ)`: gaussianas en 445 y 680 nm + fondo verde.
2. **Reflectancia y transmitancia base** (N neutro = 1.5): `R` con meseta NIR
   `0.48·exp(−Cw·8)`; `T` con niveles más bajos y caída NIR más fuerte
   `0.42·exp(−Cw·10)`.
3. **Estructura N** (1.0 fina → 2.5 gruesa): la luz dispersada se reparte con
   más reflectancia y menos transmitancia al aumentar N; se garantiza
   `R + T ≤ 1` en todo el espectro (conservación de la energía).
4. **Convolución** numérica con la respuesta gaussiana de cada canal.
5. **Calibración compartida** `cuentas = R·5000`: simulador y gemelo usan la
   misma escala; el RMSE típico es ~40 cuentas (~4 %), dominado por ruido.
6. **Comparación**: error por canal, RMSE, RMSE relativo, sesgo; anomalía si
   `rmse_rel > 0.10`.
7. **Índice 0–100**: normalización lineal de Cab (5→0, 80→100).

## Modelo PROSPECT-D (`prospect.py` + `prospect_datos.py`)

Implementación propia del formalismo real de PROSPECT (Jacquemoud &
Baret 1990; Féret et al. 2017): hoja como apilamiento de N capas,
interfaces con Fresnel promediado para luz difusa (r12 ≈ 0.093 para
n = 1.5, verificado), transmitancia interna exacta de la capa
`τ = (1−k)e^(−k) + k²·E1(k)` (E1 propia, sin scipy) y apilado con las
ecuaciones de Stokes (N fraccionario por interpolación).

Parámetros: N, Cab, Car, Cant, Cbrown, Cw, Cm. Verificado: `máx(R+T) =
0.84 ≤ 1` en 200 hojas aleatorias; Cab↑ ⇒ R↓ en azul/rojo; N↑ ⇒ R↑ y
T↓; ~3 ms por hoja (10.000 hojas en ~35 s).

**Límite clave:** los coeficientes de absorción son **aproximados de
trabajo** (picos documentados en literatura), no las tablas oficiales
de Féret et al. 2017. Están aislados en `prospect_datos.py` para
sustituirlos sin tocar las matemáticas.

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
| PROSPECT-D  | 18.81        | 7.76      | 9.54       | 0.01  |

El dataset PROSPECT es más difícil porque 6 parámetros varían y
confunden a Cab (p. ej. carotenoides en el azul, N en todo el espectro):
es el efecto físico esperado, no un error. Detalle en `modelos/*.metricas.json`.

**Límites:** evaluado en datos del mismo simulador (optimista frente a
campo); el bandpass por sí solo no reproduce el hardware real (falta
iluminación, ganancia e integración); Cw y N actúan como variabilidad,
no como magnitudes recuperables con este sensor. Hacen falta muestras
reales con Cab de referencia para validar.

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
- El gemelo heurístico del dashboard sigue siendo un modelo simplificado
  (no PROSPECT-D); PROSPECT-D vive en `prospect.py` para el dataset ML.
  Ninguno implica recuperar Cab, Cw y N de forma única con estos canales.
- Umbral de anomalía (10 %) arbitrario para la demo.
- Sin persistencia: no hay base de datos ni históricos (trabajo futuro).
