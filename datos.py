"""
==============================================================================
  DATOS — Manejo de compras, descarga de precios y cálculos de la cartera
==============================================================================
  Todas las compras se guardan en `compras.csv` (una fila por compra).
  Los precios se descargan de Yahoo Finance y SIEMPRE son el precio de la
  ACCIÓN SUBYACENTE EN USD (no el CEDEAR en pesos). Así la evolución de la
  cartera queda independiente del tipo de cambio.

  Columnas de compras.csv:
    id          → identificador único
    fecha       → fecha de compra (YYYY-MM-DD)
    ticker      → símbolo en Yahoo Finance (ej: GOOGL, GLD)
    acciones    → acciones equivalentes (CEDEARs ÷ ratio)
    precio_usd  → precio de la acción en USD al momento de la compra
    nota        → texto libre opcional
==============================================================================
"""

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

BASE_DIR        = Path(__file__).parent
ARCHIVO_COMPRAS = BASE_DIR / "compras.csv"
CAMPOS          = ["id", "fecha", "tipo", "ticker", "acciones", "precio_usd", "nota"]

# Días de historia extra que se descargan antes de la primera compra
# (sirve para dar contexto en el gráfico de detalle de cada acción).
DIAS_CONTEXTO = 45


# ===========================================================================
# Utilidades
# ===========================================================================

def parsear_numero(texto) -> float:
    """
    Convierte texto a float aceptando coma o punto como separador decimal.
      "0,02" → 0.02     "1.234,56" → 1234.56     "1,234.56" → 1234.56
    Lanza ValueError si no es un número válido.
    """
    if isinstance(texto, (int, float)):
        return float(texto)
    s = str(texto).strip().replace(" ", "").replace("US$", "").replace("$", "")
    if not s:
        raise ValueError("Número vacío")
    if "," in s and "." in s:
        # El último separador que aparece es el decimal
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    return float(s)


# ===========================================================================
# Compras (CSV)
# ===========================================================================

def _df_vacio() -> pd.DataFrame:
    return pd.DataFrame({
        "id":         pd.Series(dtype=int),
        "fecha":      pd.Series(dtype=object),
        "tipo":       pd.Series(dtype=str),
        "ticker":     pd.Series(dtype=str),
        "acciones":   pd.Series(dtype=float),
        "precio_usd": pd.Series(dtype=float),
        "nota":       pd.Series(dtype=str),
    })


def cargar_compras() -> pd.DataFrame:
    """Lee compras.csv y devuelve un DataFrame ordenado por fecha e id."""
    if not ARCHIVO_COMPRAS.exists():
        return _df_vacio()

    df = pd.read_csv(ARCHIVO_COMPRAS, dtype={"ticker": str, "nota": str, "tipo": str})
    if df.empty:
        return _df_vacio()

    if "tipo" not in df.columns:
        df["tipo"] = "COMPRA"

    for col in CAMPOS:
        if col not in df.columns:
            df[col] = "" if col == "nota" else np.nan

    df["fecha"]      = pd.to_datetime(df["fecha"]).dt.date
    df["tipo"]       = df["tipo"].fillna("COMPRA").str.strip().str.upper()
    df["ticker"]     = df["ticker"].str.strip().str.upper()
    df["acciones"]   = df["acciones"].astype(float)
    df["precio_usd"] = df["precio_usd"].astype(float)
    df["nota"]       = df["nota"].fillna("")
    df["id"]         = df["id"].astype(int)
    return df[CAMPOS].sort_values(["fecha", "id"]).reset_index(drop=True)


def guardar_compras(df: pd.DataFrame) -> None:
    out = df[CAMPOS].copy()
    out["fecha"] = out["fecha"].apply(lambda d: d.isoformat())
    out.to_csv(ARCHIVO_COMPRAS, index=False, encoding="utf-8")


def agregar_transaccion(fecha: date, tipo: str, ticker: str, acciones: float,
                        precio_usd: float, nota: str = "") -> None:
    df = cargar_compras()
    nuevo_id = int(df["id"].max()) + 1 if not df.empty else 1
    tipo_norm = "VENTA" if str(tipo).strip().upper() == "VENTA" else "COMPRA"
    fila = pd.DataFrame([{
        "id": nuevo_id, "fecha": fecha, "tipo": tipo_norm,
        "ticker": ticker.strip().upper(),
        "acciones": float(acciones), "precio_usd": float(precio_usd),
        "nota": nota.strip(),
    }])
    df = fila if df.empty else pd.concat([df, fila], ignore_index=True)
    guardar_compras(df)


def agregar_compra(fecha: date, ticker: str, acciones: float,
                   precio_usd: float, nota: str = "") -> None:
    agregar_transaccion(fecha, "COMPRA", ticker, acciones, precio_usd, nota)


def editar_transaccion(id_tx: int, fecha: date, tipo: str, ticker: str,
                       acciones: float, precio_usd: float, nota: str = "") -> None:
    df = cargar_compras()
    idx = df[df["id"] == int(id_tx)].index
    if not idx.empty:
        df.loc[idx, "fecha"] = fecha
        df.loc[idx, "tipo"] = "VENTA" if str(tipo).strip().upper() == "VENTA" else "COMPRA"
        df.loc[idx, "ticker"] = ticker.strip().upper()
        df.loc[idx, "acciones"] = float(acciones)
        df.loc[idx, "precio_usd"] = float(precio_usd)
        df.loc[idx, "nota"] = nota.strip()
        guardar_compras(df)


def eliminar_compra(id_compra: int) -> None:
    df = cargar_compras()
    df = df[df["id"] != int(id_compra)]
    guardar_compras(df)


# ===========================================================================
# Precios (Yahoo Finance)
# ===========================================================================

def descargar_precios(tickers, desde: date) -> pd.DataFrame:
    """
    Descarga precios de cierre diarios (USD, sin ajustar) desde `desde` hasta hoy.
    Devuelve un DataFrame: índice = fechas, columnas = tickers.
    """
    tickers = sorted(set(tickers))
    if not tickers:
        return pd.DataFrame()

    datos = yf.download(
        tickers,
        start=desde.isoformat(),
        end=(date.today() + timedelta(days=1)).isoformat(),
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    if datos is None or datos.empty:
        return pd.DataFrame()

    close = datos["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])

    idx = pd.DatetimeIndex(close.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    close.index = idx.normalize()

    close = close.sort_index()
    close = close[~close.index.duplicated(keep="last")]
    close = close.dropna(how="all").ffill()
    close = close.dropna(axis=1, how="all")
    return close


def precio_cierre(ticker: str, fecha: date):
    """Precio de cierre en USD de `ticker` en `fecha` (o el último día hábil anterior)."""
    d = yf.download(
        ticker.strip().upper(),
        start=(fecha - timedelta(days=7)).isoformat(),
        end=(fecha + timedelta(days=1)).isoformat(),
        auto_adjust=False,
        progress=False,
    )
    if d is None or d.empty:
        return None
    c = d["Close"]
    if isinstance(c, pd.DataFrame):
        c = c.iloc[:, 0]
    c = c.dropna()
    return float(c.iloc[-1]) if len(c) else None


# ===========================================================================
# Cálculos de la cartera
# ===========================================================================

def serie_cartera(compras: pd.DataFrame, precios: pd.DataFrame) -> pd.DataFrame:
    """
    Evolución diaria de la cartera completa desde la primera operación.
    Soporta compras y ventas.
    Columnas: valor, invertido, ganancia, rend_pct (en USD)
    """
    if compras.empty or precios.empty:
        return pd.DataFrame()

    inicio = pd.Timestamp(compras["fecha"].min())
    p = precios.loc[precios.index >= inicio]
    if p.empty:
        return pd.DataFrame()

    df_tx = compras.sort_values(["fecha", "id"]).copy()
    if "tipo" not in df_tx.columns:
        df_tx["tipo"] = "COMPRA"

    # Diccionario de fechas a transacciones
    tx_por_fecha = {}
    for c in df_tx.itertuples():
        f = pd.Timestamp(c.fecha)
        tx_por_fecha.setdefault(f, []).append(c)

    fechas = p.index
    valores = np.zeros(len(fechas), dtype=float)
    invertidos = np.zeros(len(fechas), dtype=float)

    # Estado acumulado: {ticker: {"acciones": float, "costo": float}}
    posiciones = {}
    tx_fechas_keys = sorted(tx_por_fecha.keys())
    tx_idx = 0

    for i, fecha in enumerate(fechas):
        # Procesar transacciones ocurridas hasta esta fecha
        while tx_idx < len(tx_fechas_keys) and tx_fechas_keys[tx_idx] <= fecha:
            f_actual = tx_fechas_keys[tx_idx]
            for tx in tx_por_fecha[f_actual]:
                t = tx.ticker
                if t not in posiciones:
                    posiciones[t] = {"acciones": 0.0, "costo": 0.0}
                pos = posiciones[t]
                if tx.tipo == "VENTA":
                    acc_actual = pos["acciones"]
                    if acc_actual > 0:
                        frac_vendida = min(1.0, tx.acciones / acc_actual)
                        pos["costo"] = max(0.0, pos["costo"] * (1.0 - frac_vendida))
                        pos["acciones"] = max(0.0, pos["acciones"] - tx.acciones)
                else: # COMPRA
                    pos["acciones"] += tx.acciones
                    pos["costo"] += tx.acciones * tx.precio_usd
            tx_idx += 1

        # Calcular valor total e invertido total en la fecha i
        val_dia = 0.0
        inv_dia = 0.0
        for t, pos in posiciones.items():
            acc = pos["acciones"]
            if acc > 1e-9:
                inv_dia += pos["costo"]
                if t in p.columns:
                    val_precio = p.at[fecha, t]
                    val_dia += acc * (val_precio if not pd.isna(val_precio) else (pos["costo"] / acc))
                else:
                    val_dia += pos["costo"]
        valores[i] = val_dia
        invertidos[i] = inv_dia

    df = pd.DataFrame({"valor": valores, "invertido": invertidos}, index=fechas)
    df["ganancia"] = df["valor"] - df["invertido"]
    df["rend_pct"] = np.where(df["invertido"] > 1e-9, df["ganancia"] / df["invertido"] * 100, 0.0)
    return df


def rendimiento_por_ticker(compras: pd.DataFrame, precios: pd.DataFrame) -> pd.DataFrame:
    """
    % de rendimiento diario de cada acción respecto a su precio promedio de compra ponderado.
    """
    salida = {}
    if compras.empty or precios.empty:
        return pd.DataFrame()

    df_tx = compras.sort_values(["fecha", "id"]).copy()
    if "tipo" not in df_tx.columns:
        df_tx["tipo"] = "COMPRA"

    for t, g in df_tx.groupby("ticker"):
        if t not in precios.columns:
            continue
        s = precios[t].dropna()
        f_min = pd.Timestamp(g["fecha"].min())
        s = s[s.index >= f_min]
        if s.empty:
            continue

        serie_rend = pd.Series(np.nan, index=s.index)
        tx_list = list(g.itertuples())
        tx_idx = 0
        acc_actual = 0.0
        costo_actual = 0.0

        for fecha in s.index:
            while tx_idx < len(tx_list) and pd.Timestamp(tx_list[tx_idx].fecha) <= fecha:
                tx = tx_list[tx_idx]
                if tx.tipo == "VENTA":
                    if acc_actual > 0:
                        frac = min(1.0, tx.acciones / acc_actual)
                        costo_actual = max(0.0, costo_actual * (1.0 - frac))
                        acc_actual = max(0.0, acc_actual - tx.acciones)
                else:
                    acc_actual += tx.acciones
                    costo_actual += tx.acciones * tx.precio_usd
                tx_idx += 1

            if acc_actual > 1e-9 and costo_actual > 1e-9:
                ppc = costo_actual / acc_actual
                pr = s.at[fecha]
                if not pd.isna(pr):
                    serie_rend.at[fecha] = (pr / ppc - 1) * 100

        salida[t] = serie_rend

    return pd.DataFrame(salida)


def resumen_posiciones(compras: pd.DataFrame, precios: pd.DataFrame) -> pd.DataFrame:
    """Una fila por ticker con la situación actual (todo en USD), considerando compras y ventas."""
    filas = []
    if compras.empty:
        return pd.DataFrame()

    df_tx = compras.sort_values(["fecha", "id"]).copy()
    if "tipo" not in df_tx.columns:
        df_tx["tipo"] = "COMPRA"

    for t, g in df_tx.groupby("ticker"):
        acc_actual = 0.0
        costo_actual = 0.0
        for tx in g.itertuples():
            if tx.tipo == "VENTA":
                if acc_actual > 0:
                    frac = min(1.0, tx.acciones / acc_actual)
                    costo_actual = max(0.0, costo_actual * (1.0 - frac))
                    acc_actual = max(0.0, acc_actual - tx.acciones)
            else:
                acc_actual += tx.acciones
                costo_actual += tx.acciones * tx.precio_usd

        # Si ya se vendió todo (o casi nada queda), podemos mantenerlo o mostrar 0
        ppc = (costo_actual / acc_actual) if acc_actual > 1e-9 else 0.0

        s = precios[t].dropna() if t in precios.columns else pd.Series(dtype=float)
        precio = float(s.iloc[-1]) if len(s) else np.nan
        previo = float(s.iloc[-2]) if len(s) > 1 else np.nan
        valor  = acc_actual * precio if not np.isnan(precio) else costo_actual

        filas.append({
            "ticker":         t,
            "acciones":       acc_actual,
            "ppc":            ppc,
            "precio":         precio,
            "var_dia":        ((precio / previo - 1) * 100) if (not np.isnan(precio) and not np.isnan(previo) and previo > 0) else np.nan,
            "cambio_dia_usd": acc_actual * (precio - previo) if (not np.isnan(precio) and not np.isnan(previo)) else 0.0,
            "invertido":      costo_actual,
            "valor":          valor,
            "ganancia":       (valor - costo_actual) if acc_actual > 1e-9 else 0.0,
            "rend":           ((valor / costo_actual - 1) * 100) if costo_actual > 1e-9 else 0.0,
            "primera_compra": g["fecha"].min(),
            "n_compras":      len(g),
        })

    df = pd.DataFrame(filas)
    if df.empty:
        return df
    total = df["valor"].sum()
    df["peso"] = (df["valor"] / total * 100) if total > 1e-9 else 0.0
    return df.sort_values("valor", ascending=False).reset_index(drop=True)

