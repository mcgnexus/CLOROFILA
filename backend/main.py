"""Backend FastAPI - FASE 3: controles, modos y deteccion de anomalias."""
import asyncio
from pathlib import Path

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sensor_simulator import SimuladorAS7341
from twin_model import (
    CAB_MAX,
    CAB_MIN,
    CW_MAX,
    CW_MIN,
    MODOS_VALIDOS,
    N_MAX,
    N_MIN,
    N_REF,
    comparar_lectura,
    indice_clorofila,
    predecir_canales,
)

# Intervalo de envio de lecturas simuladas (segundos).
INTERVALO_ENVIO = 1.0

# Umbral de error relativo para marcar posible anomalia/estres.
UMBRAL_ANOMALIA = 0.10

# Configuracion global (ajustable via POST /api/config desde el dashboard).
config = {
    "cab": 45.0,
    "cw": 0.015,
    "n": N_REF,
    "modo": "reflectancia",
    "estres": False,
}

app = FastAPI(title="Gemelo Digital Clorofila - Fase 3")

# El frontend se sirve desde ../frontend
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

simulador = SimuladorAS7341(cab_base=config["cab"], cw=config["cw"],
                            modo=config["modo"], n=config["n"])


def _validar_config(datos: dict) -> dict:
    """Valida y aplica una actualizacion parcial de configuracion."""
    if "cab" in datos:
        cab = float(datos["cab"])
        if not (CAB_MIN <= cab <= CAB_MAX):
            raise ValueError(f"cab fuera de rango [{CAB_MIN}, {CAB_MAX}]")
        config["cab"] = cab
    if "cw" in datos:
        cw = float(datos["cw"])
        if not (CW_MIN <= cw <= CW_MAX):
            raise ValueError(f"cw fuera de rango [{CW_MIN}, {CW_MAX}]")
        config["cw"] = cw
    if "modo" in datos:
        if datos["modo"] not in MODOS_VALIDOS:
            raise ValueError(f"modo debe ser uno de {MODOS_VALIDOS}")
        config["modo"] = datos["modo"]
    if "n" in datos:
        n = float(datos["n"])
        if not (N_MIN <= n <= N_MAX):
            raise ValueError(f"n fuera de rango [{N_MIN}, {N_MAX}]")
        config["n"] = n
    if "estres" in datos:
        config["estres"] = bool(datos["estres"])
    simulador.set_estado(cab_base=config["cab"], cw=config["cw"],
                         modo=config["modo"], estres=config["estres"],
                         n=config["n"])
    return dict(config)


@app.get("/api/salud")
async def salud():
    """Health-check simple para comprobar que el backend esta vivo."""
    return {"estado": "ok", "fase": 3, "sensor": "simulado"}


@app.get("/api/config")
async def obtener_config():
    """Devuelve la configuracion actual del gemelo y simulador."""
    return dict(config)


@app.post("/api/config")
async def actualizar_config(datos: dict):
    """Actualiza cab, cw, modo y/o flag de estres (parcial o total)."""
    try:
        return _validar_config(datos)
    except (ValueError, TypeError) as exc:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.get("/api/modelo")
async def modelo(
    cab: float = Query(45.0, ge=CAB_MIN, le=CAB_MAX),
    cw: float = Query(0.015, ge=CW_MIN, le=CW_MAX),
    modo: str = Query("reflectancia"),
    n: float = Query(N_REF, ge=N_MIN, le=N_MAX),
):
    """Prediccion del gemelo para unos parametros dados (util para tests)."""
    if modo not in MODOS_VALIDOS:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400,
                            content={"error": f"modo debe ser uno de {MODOS_VALIDOS}"})
    prediccion = predecir_canales(cab, cw, modo, n)
    return {
        "cab": cab,
        "cw": cw,
        "modo": modo,
        "n": n,
        "indice_clorofila": indice_clorofila(cab),
        "prediccion": prediccion,
    }


@app.websocket("/ws")
async def websocket_datos(websocket: WebSocket):
    """Envia lectura + prediccion + comparacion + flag de anomalia."""
    await websocket.accept()
    try:
        while True:
            lectura = simulador.generar_lectura()
            prediccion = predecir_canales(config["cab"], config["cw"],
                                          config["modo"], config["n"])
            comparacion = comparar_lectura(lectura["canales"], prediccion)
            anomalia = comparacion["rmse_rel"] > UMBRAL_ANOMALIA
            await websocket.send_json({
                "timestamp": lectura["timestamp"],
                "canales": lectura["canales"],
                "prediccion": prediccion,
                "comparacion": comparacion,
                "anomalia": anomalia,
                "gemelo": {
                    "cab": config["cab"],
                    "cw": config["cw"],
                    "n": config["n"],
                    "modo": config["modo"],
                    "indice_clorofila": indice_clorofila(config["cab"]),
                },
                "cab_verdadero": lectura.get("cab_verdadero"),
                "estres_simulado": lectura.get("estres", False),
                "longitudes_onda": lectura["longitudes_onda"],
                "orden_canales": lectura["orden_canales"],
            })
            await asyncio.sleep(INTERVALO_ENVIO)
    except WebSocketDisconnect:
        # Cliente desconectado: salida limpia del bucle.
        pass
    except Exception:
        # Cualquier otro error: cerrar la conexion sin tumbar el servidor.
        try:
            await websocket.close()
        except Exception:
            pass


# Sirve index.html en la raiz.
@app.get("/")
async def raiz():
    return FileResponse(FRONTEND_DIR / "index.html")


# Archivos estaticos (style.css, app.js, charts.js) bajo /static.
# Se monta DESPUES de las rutas para no eclipsar /ws ni /api/*.
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
