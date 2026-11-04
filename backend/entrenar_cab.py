"""Entrena un regresor base Cab <- canales AS7341 (Ridge + numpy).

Solo usa los canales como predictores: las columnas de parametros
verdaderos (cab, cw, n, car, ...) nunca entran como features.

Uso:
    python entrenar_cab.py --datos data/dataset.csv --salida modelos/cab_ridge
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from ridge import ajustar_ridge, con_sesgo, mae, predecir, rmse

LAMBDA_GRID = [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]


def cargar_csv(ruta: Path):
    """Carga el dataset y devuelve (splits, params, X, columnas).

    Las features son SOLO los canales; ningun parametro verdadero entra
    como predictor (evita fuga de informacion).
    """
    excluir = {"split", "cab", "cw", "n", "modo",
               "car", "cant", "cbrown", "cm"}
    with open(ruta, encoding="utf-8") as f:
        lector = csv.DictReader(f)
        columnas = [c for c in lector.fieldnames if c not in excluir]
        filas = list(lector)
    splits = np.array([r["split"] for r in filas])
    cab = np.array([float(r["cab"]) for r in filas])
    X = np.array([[float(r[c]) for c in columnas] for r in filas])
    return splits, cab, X, columnas


def main() -> None:
    ap = argparse.ArgumentParser(description="Entrena regresor base de Cab.")
    ap.add_argument("--datos", default="data/dataset.csv")
    ap.add_argument("--salida", default="modelos/cab_ridge",
                    help="Prefijo de salida (sin extension)")
    args = ap.parse_args()

    splits, cab, X, columnas = cargar_csv(Path(args.datos))
    tr, va, te = splits == "train", splits == "val", splits == "test"
    print(f"Muestras: train={tr.sum()} val={va.sum()} test={te.sum()}")

    # Estandarizacion con estadisticos SOLO de train.
    media = X[tr].mean(axis=0)
    desv = X[tr].std(axis=0)
    desv[desv == 0] = 1.0
    Xs = (X - media) / desv

    # Baseline ingenuo: predecir siempre la media de train.
    base_mae = mae(cab[te], np.full(te.sum(), cab[tr].mean()))
    print(f"Baseline (media train): MAE test = {base_mae:.2f} µg/cm²")

    # Seleccion de lambda en validacion.
    mejor, mejor_lam = None, None
    for lam in LAMBDA_GRID:
        coef = ajustar_ridge(con_sesgo(Xs[tr]), cab[tr], lam)
        r = rmse(cab[va], predecir(con_sesgo(Xs[va]), coef))
        print(f"  lambda={lam:<8} RMSE val = {r:.3f}")
        if mejor is None or r < mejor[0]:
            mejor, mejor_lam = (r, coef), lam

    # Reajuste final con train+val y metricas en test (conjunto intacto).
    trva = tr | va
    coef_f = ajustar_ridge(con_sesgo(Xs[trva]), cab[trva], mejor_lam)
    metricas = {}
    for nombre, m in [("train", tr), ("val", va), ("test", te)]:
        p = predecir(con_sesgo(Xs[m]), coef_f)
        metricas[nombre] = {"mae": round(mae(cab[m], p), 3),
                            "rmse": round(rmse(cab[m], p), 3),
                            "n": int(m.sum())}
    print(f"Elegido lambda={mejor_lam}")
    for k, v in metricas.items():
        print(f"  {k}: MAE={v['mae']} RMSE={v['rmse']} (n={v['n']})")

    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    np.savez(salida.with_suffix(".npz"), sesgo=coef_f[0], pesos=coef_f[1:],
             media=media, desv=desv, columnas=np.array(columnas),
             lam=mejor_lam, modo="reflectancia")
    with open(salida.parent / (salida.name + ".metricas.json"), "w",
              encoding="utf-8") as f:
        json.dump({"lambda": mejor_lam, "columnas": columnas,
                   "baseline_mae_test": round(base_mae, 3),
                   "metricas": metricas,
                   "unidades": "µg/cm²",
                   "advertencia": "Evaluado en datos del mismo simulador; "
                   "optimista frente a campo real."}, f, indent=2,
                  ensure_ascii=False)
    print(f"OK: {salida.with_suffix('.npz')}")


if __name__ == "__main__":
    main()
