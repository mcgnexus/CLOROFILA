"""Generador de dataset sintetico para entrenar la inversion Cab <- AS7341.

Dos fuentes de espectros (--fuente):
  heuristico: gemelo digital propio (twin_model), rapido y calibrado
    a la demo del dashboard (parametros: Cab, Cw, N).
  prospect: modelo PROSPECT-D implementado en prospect.py (parametros
    Cab, Car, Cant, Cbrown, Cw, Cm, N), formalismo real de transferencia
    radiativa con coeficientes de trabajo aproximados.

La particion train/val/test se asigna ANTES de anadir ruido, de modo
que ninguna hoja aparece en dos conjuntos.

Uso:
    python dataset_sintetico.py --n 100 --semilla 42 --salida data/prueba.csv
    python dataset_sintetico.py --n 10000 --semilla 42 --salida data/dataset.csv
    python dataset_sintetico.py --fuente prospect --n 10000 --salida data/dataset_prospect.csv
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sensor_simulator import RUIDO
from twin_model import CAB_MAX, CAB_MIN, CW_MAX, CW_MIN, N_MAX, N_MIN, ORDEN_CANALES

VERSION_GENERADOR = "sintetico-v2/{fuente}"

# Rangos de muestreo de los parametros extra de PROSPECT-D (hoja verde
# tipica con variabilidad; Cbrown fijo a 0 salvo senescencia simulada).
CAR_RANGO = (2.0, 16.0)    # µg/cm2
CANT_RANGO = (0.0, 2.0)    # µg/cm2
CBROWN_RANGO = (0.0, 0.0)  # sin senescencia por defecto
CM_RANGO = (0.003, 0.012)  # g/cm2

COLUMNAS_PARAM = ["cab", "cw", "n", "car", "cant", "cbrown", "cm"]


def espectro_hoja(cab: float, cw: float, n: float, modo: str,
                  fuente: str = "heuristico", extra: dict | None = None) -> dict:
    """Simula la lectura limpia del AS7341 para una hoja virtual.

    Args:
        cab: clorofila (µg/cm2). cw: agua (cm). n: estructura.
        modo: "reflectancia" o "transmitancia".
        fuente: "heuristico" (twin_model) o "prospect" (PROSPECT-D).
        extra: parametros PROSPECT-D adicionales (car, cant, cbrown, cm).

    Returns:
        dict {canal: cuentas} sin ruido.
    """
    if fuente == "prospect":
        from prospect import predecir_canales_prospect
        e = extra or {}
        return predecir_canales_prospect(
            cab, cw, n, modo,
            car=e.get("car", 8.0), cant=e.get("cant", 1.0),
            cbrown=e.get("cbrown", 0.0), cm=e.get("cm", 0.005))
    from twin_model import predecir_canales  # import tardio, evita ciclos
    return predecir_canales(cab, cw, modo, n)


def generar_dataset(n_muestras: int, semilla: int, modo: str,
                    fuente: str = "heuristico",
                    desv_ruido: dict | None = None) -> tuple[np.ndarray, np.ndarray, list]:
    """Genera parametros y lecturas ruidosas.

    Returns:
        (parametros [n,7] con columnas COLUMNAS_PARAM, lecturas [n,10],
        splits lista de str).
    """
    rng = np.random.default_rng(semilla)
    cab = rng.uniform(CAB_MIN, CAB_MAX, n_muestras)
    cw = rng.uniform(CW_MIN, CW_MAX, n_muestras)
    n_est = rng.uniform(N_MIN, N_MAX, n_muestras)
    car = rng.uniform(*CAR_RANGO, n_muestras)
    cant = rng.uniform(*CANT_RANGO, n_muestras)
    cbrown = rng.uniform(*CBROWN_RANGO, n_muestras)
    cm = rng.uniform(*CM_RANGO, n_muestras)

    # Particion ANTES del ruido: 70 % train / 15 % val / 15 % test.
    perm = rng.permutation(n_muestras)
    n_train = int(0.70 * n_muestras)
    n_val = int(0.15 * n_muestras)
    splits = np.empty(n_muestras, dtype=object)
    splits[perm[:n_train]] = "train"
    splits[perm[n_train:n_train + n_val]] = "val"
    splits[perm[n_train + n_val:]] = "test"

    if desv_ruido is None:
        desv_ruido = {c: RUIDO[c] for c in ORDEN_CANALES}
    sigmas = np.array([desv_ruido[c] for c in ORDEN_CANALES])

    lecturas = np.zeros((n_muestras, len(ORDEN_CANALES)))
    for i in range(n_muestras):
        extra = {"car": float(car[i]), "cant": float(cant[i]),
                 "cbrown": float(cbrown[i]), "cm": float(cm[i])}
        limpio = espectro_hoja(float(cab[i]), float(cw[i]), float(n_est[i]),
                               modo, fuente, extra)
        base = np.array([limpio[c] for c in ORDEN_CANALES], dtype=float)
        ruido = rng.normal(0.0, sigmas)
        lecturas[i] = np.maximum(0, np.round(base + ruido))
        if (i + 1) % 2000 == 0:
            print(f"  ... {i + 1}/{n_muestras}")

    params = np.column_stack([cab, cw, n_est, car, cant, cbrown, cm])
    return params, lecturas, list(splits)


def guardar_csv(ruta: Path, params: np.ndarray, lecturas: np.ndarray,
                splits: list, modo: str):
    """Guarda el dataset en CSV con cabecera."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["split"] + COLUMNAS_PARAM + ["modo"] + ORDEN_CANALES)
        for i in range(len(splits)):
            w.writerow([splits[i]]
                       + [f"{v:.5g}" for v in params[i]]
                       + [modo] + [int(v) for v in lecturas[i]])


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera dataset sintetico AS7341.")
    ap.add_argument("--n", type=int, default=10000, help="Nº de hojas virtuales")
    ap.add_argument("--semilla", type=int, default=42)
    ap.add_argument("--modo", default="reflectancia",
                    choices=["reflectancia", "transmitancia"])
    ap.add_argument("--fuente", default="heuristico",
                    choices=["heuristico", "prospect"],
                    help="generador de espectros")
    ap.add_argument("--salida", default="data/dataset.csv")
    args = ap.parse_args()

    print(f"Generando {args.n} espectros ({args.fuente}, modo={args.modo}, "
          f"semilla={args.semilla})...")
    params, lecturas, splits = generar_dataset(args.n, args.semilla,
                                               args.modo, args.fuente)

    ruta = Path(args.salida)
    guardar_csv(ruta, params, lecturas, splits, args.modo)
    meta = {
        "version": VERSION_GENERADOR.format(fuente=args.fuente),
        "fuente": args.fuente,
        "n_muestras": args.n,
        "semilla": args.semilla,
        "modo": args.modo,
        "columnas_param": COLUMNAS_PARAM,
        "columnas_canales": ORDEN_CANALES,
        "ruido": "gaussiano, desv. tipica por canal = RUIDO de sensor_simulator",
        "splits": {"train": splits.count("train"), "val": splits.count("val"),
                   "test": splits.count("test")},
    }
    with open(ruta.with_suffix(".meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"OK: {ruta} + {ruta.with_suffix('.meta.json')}")


if __name__ == "__main__":
    main()
