"""Backend FastAPI - Fase 4: gemelo PROSPECT-D oficial + estimacion ML.

- Prediccion con PROSPECT-D oficial (`prospect.py`).
- Hoja simulada y gemelo SEPARADOS: mover los sliders del gemelo no
  cambia la muestra; `sincronizar` los vuelve a alinear.
- Estimacion de Cab por Ridge (`modelos/cab_ridge_prospect.npz`) solo
  en modo reflectancia (el modelo se entreno en ese modo).
"""
import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from modelo_ml import cargar_modelo, predecir_cab
from prospect import (
    EXTRAS_POR_DEFECTO,
    MODOS_VALIDOS,
    predecir_canales_prospect,
)
from sensor_simulator import SimuladorAS7341
from twin_model import (
    CAB_MAX,
    CAB_MIN,
    CW_MAX,
    CW_MIN,
    N_MAX,
    N_MIN,
    N_REF,
    comparar_lectura,
    indice_clorofila,
)

log = logging.getLogger("gemelo")

# Intervalo de envio de lecturas simuladas (segundos).
INTERVALO_ENVIO = 1.0

# Umbral de error relativo para marcar posible anomalia/estres.
UMBRAL_ANOMALIA = 0.10

# Hoja verdadera (simulador) y supuesto del gemelo: independientes.
# Los sliders del dashboard mueven SOLO el gemelo.
HOJA_INICIAL = {"cab_base": 45.0, "cw": 0.015, "n": N_REF}
GEMELO_INICIAL = {"cab": 45.0, "cw": 0.015, "n": N_REF}

config = {
    "gemelo": dict(GEMELO_INICIAL),
    "hoja": dict(HOJA_INICIAL),
    "modo": "reflectancia",
    "estres": False,
}

app = FastAPI(title="Gemelo Digital Clorofila - Fase 4 (PROSPECT-D)")

# El frontend vive en backend/public (dentro del paquete, para que Vercel
# lo incluya en el bundle de la funcion). En local lo sirve FastAPI.
BASE_DIR = Path(__file__).resolve().parent


def _resolver_frontend() -> Path:
    """Localiza el directorio del frontend en cualquier layout."""
    candidatos = [
        BASE_DIR / "public",
        BASE_DIR.parent / "public",
        Path.cwd() / "public",
        Path.cwd() / "backend" / "public",
        Path("/var/task/public"),
        Path("/var/task/backend/public"),
    ]
    for c in candidatos:
        if (c / "index.html").is_file():
            return c
    log.warning("frontend no encontrado en %s", candidatos)
    return candidatos[0]


FRONTEND_DIR = _resolver_frontend()
log.info("FRONTEND_DIR=%s index.html=%s", FRONTEND_DIR,
         (FRONTEND_DIR / "index.html").is_file())

simulador = SimuladorAS7341(cab_base=config["hoja"]["cab_base"],
                            cw=config["hoja"]["cw"],
                            modo=config["modo"], n=config["hoja"]["n"])

# Modelo ML (opcional): Ridge entrenado en dataset PROSPECT-D oficial.
MODELO_ML_RUTA = BASE_DIR / "modelos" / "cab_ridge_prospect.npz"
try:
    modelo_ml = cargar_modelo(MODELO_ML_RUTA)
    log.info("Modelo ML cargado: %s", MODELO_ML_RUTA)
except Exception as exc:
    modelo_ml = None
    log.warning("Sin modelo ML (%s): cab_estimado_ml sera null", exc)


def _validar_numero(valor, lo: float, hi: float, nombre: str) -> float:
    """Convierte y valida un parametro numerico (lanza ValueError)."""
    try:
        x = float(valor)
    except (TypeError, ValueError):
        raise ValueError(f"{nombre} debe ser un numero")
    if not (lo <= x <= hi):
        raise ValueError(f"{nombre} fuera de rango [{lo}, {hi}]")
    return x


def _validar_config(datos: dict) -> dict:
    """Valida TODO antes de aplicar nada (sin cambios parciales)."""
    gemelo = dict(config["gemelo"])
    hoja = dict(config["hoja"])
    modo = config["modo"]
    estres = config["estres"]

    if "cab" in datos:
        gemelo["cab"] = _validar_numero(datos["cab"], CAB_MIN, CAB_MAX, "cab")
    if "cw" in datos:
        gemelo["cw"] = _validar_numero(datos["cw"], CW_MIN, CW_MAX, "cw")
    if "n" in datos:
        gemelo["n"] = _validar_numero(datos["n"], N_MIN, N_MAX, "n")
    if "hoja_cab" in datos:
        hoja["cab_base"] = _validar_numero(datos["hoja_cab"], CAB_MIN,
                                           CAB_MAX, "hoja_cab")
    if "hoja_cw" in datos:
        hoja["cw"] = _validar_numero(datos["hoja_cw"], CW_MIN, CW_MAX,
                                     "hoja_cw")
    if "hoja_n" in datos:
        hoja["n"] = _validar_numero(datos["hoja_n"], N_MIN, N_MAX, "hoja_n")
    if "modo" in datos:
        if datos["modo"] not in MODOS_VALIDOS:
            raise ValueError(f"modo debe ser uno de {MODOS_VALIDOS}")
        modo = datos["modo"]
    if "estres" in datos:
        estres = bool(datos["estres"])

    # Todo valido: aplicar de golpe.
    if datos.get("sincronizar"):
        gemelo = {"cab": hoja["cab_base"], "cw": hoja["cw"], "n": hoja["n"]}
    config["gemelo"] = gemelo
    config["hoja"] = hoja
    config["modo"] = modo
    config["estres"] = estres
    simulador.set_estado(cab_base=hoja["cab_base"], cw=hoja["cw"],
                         modo=modo, estres=estres, n=hoja["n"])
    return {"gemelo": dict(gemelo), "hoja": dict(hoja),
            "modo": modo, "estres": estres}


@app.get("/api/salud")
async def salud():
    """Health-check simple para comprobar que el backend esta vivo."""
    return {"estado": "ok", "fase": 4, "sensor": "simulado",
            "modelo": "prospect-d-oficial",
            "ml_disponible": modelo_ml is not None}


@app.get("/api/config")
async def obtener_config():
    """Devuelve gemelo, hoja verdadera, modo y estres."""
    return {"gemelo": dict(config["gemelo"]), "hoja": dict(config["hoja"]),
            "modo": config["modo"], "estres": config["estres"]}


@app.post("/api/config")
async def actualizar_config(datos: dict):
    """Actualiza gemelo / hoja / modo / estres (todo validado o nada)."""
    try:
        return _validar_config(datos)
    except (ValueError, TypeError) as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.get("/api/modelo")
async def modelo(
    cab: float = Query(45.0, ge=CAB_MIN, le=CAB_MAX),
    cw: float = Query(0.015, ge=CW_MIN, le=CW_MAX),
    modo: str = Query("reflectancia"),
    n: float = Query(N_REF, ge=N_MIN, le=N_MAX),
):
    """Prediccion PROSPECT-D oficial para unos parametros dados."""
    if modo not in MODOS_VALIDOS:
        return JSONResponse(status_code=400,
                            content={"error": f"modo debe ser uno de {MODOS_VALIDOS}"})
    try:
        prediccion = predecir_canales_prospect(cab, cw, n, modo,
                                               **EXTRAS_POR_DEFECTO)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    return {
        "cab": cab,
        "cw": cw,
        "modo": modo,
        "n": n,
        "indice_clorofila": indice_clorofila(cab),
        "prediccion": prediccion,
    }


def _estimar_cab_ml(canales: dict, modo: str) -> float | None:
    """Estima Cab con Ridge; None si no hay modelo o el modo no es valido.

    El modelo se entreno SOLO en reflectancia: en transmitancia no se
    ofrece estimacion (devolver un numero seria enganoso).
    """
    if modelo_ml is None or modo != "reflectancia":
        return None
    try:
        return round(predecir_cab(modelo_ml, canales), 1)
    except Exception as exc:
        log.warning("Fallo estimacion ML: %s", exc)
        return None


def _construir_mensaje() -> dict:
    """Construye un mensaje completo lectura+prediccion+ML.

    Misma forma para el WebSocket (/ws, cada segundo) y el sondeo
    REST (/api/lectura, para plataformas sin WebSocket como Vercel).
    Lanza ValueError si la prediccion no es finita.
    """
    lectura = simulador.generar_lectura()
    g = config["gemelo"]
    prediccion = predecir_canales_prospect(
        g["cab"], g["cw"], g["n"], config["modo"], **EXTRAS_POR_DEFECTO)
    comparacion = comparar_lectura(lectura["canales"], prediccion)
    anomalia = comparacion["rmse_rel"] > UMBRAL_ANOMALIA
    return {
        "timestamp": lectura["timestamp"],
        "canales": lectura["canales"],
        "prediccion": prediccion,
        "comparacion": comparacion,
        "anomalia": anomalia,
        "cab_estimado_ml": _estimar_cab_ml(lectura["canales"],
                                          config["modo"]),
        "gemelo": {
            "cab": g["cab"],
            "cw": g["cw"],
            "n": g["n"],
            "modo": config["modo"],
            "indice_clorofila": indice_clorofila(g["cab"]),
        },
        "hoja": {
            "cab_base": config["hoja"]["cab_base"],
            "cab_verdadero": lectura.get("cab_verdadero"),
            "cw": config["hoja"]["cw"],
            "n": config["hoja"]["n"],
        },
        # Compatibilidad: cab_verdadero tambien en la raiz.
        "cab_verdadero": lectura.get("cab_verdadero"),
        "estres_simulado": lectura.get("estres", False),
        "longitudes_onda": lectura["longitudes_onda"],
        "orden_canales": lectura["orden_canales"],
    }


@app.get("/api/lectura")
async def lectura_unica():
    """Una lectura completa (igual forma que cada mensaje de /ws).

    Pensado para sondeo donde no hay WebSocket (p. ej. Vercel
    serverless). El frontend lo usa como reserva automatica.
    """
    try:
        return _construir_mensaje()
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@app.websocket("/ws")
async def websocket_datos(websocket: WebSocket):
    """Envia lectura + prediccion oficial + comparacion + Cab ML."""
    await websocket.accept()
    try:
        while True:
            try:
                await websocket.send_json(_construir_mensaje())
            except ValueError as exc:
                log.error("Prediccion invalida (gemelo=%s): %s",
                          config["gemelo"], exc)
            await asyncio.sleep(INTERVALO_ENVIO)
    except WebSocketDisconnect:
        # Cliente desconectado: salida limpia del bucle.
        pass
    except Exception as exc:
        # Error inesperado: registrarlo (antes se ocultaba) y cerrar.
        log.exception("Error en WebSocket: %s", exc)
        try:
            await websocket.close()
        except Exception:
            pass


# Sirve index.html en la raiz.
@app.get("/")
async def raiz():
    return FileResponse(FRONTEND_DIR / "index.html")


# Tutorial de uso, accesible con el boton "Ayuda" del dashboard.
@app.get("/tutorial")
async def tutorial():
    return FileResponse(FRONTEND_DIR / "tutorial.html")


# Archivos estaticos (style.css, app.js, charts.js) bajo /static.
# Se monta DESPUES de las rutas para no eclipsar /ws ni /api/*.
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
