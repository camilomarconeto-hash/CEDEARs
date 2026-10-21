"""
==============================================================================
  GRÁFICOS — ¡Personalizá este archivo a tu gusto!
==============================================================================
  • Todos los colores, tamaños y fuentes están en el diccionario ESTILO.
  • Cada función recibe una `Figure` de matplotlib y dibuja sobre ella.
  • Después de editar, cerrá y volvé a abrir la app para ver los cambios.

  Funciones disponibles:
    grafico_evolucion_cartera(fig, serie)
    grafico_rendimiento_tickers(fig, rend, colores)
    grafico_detalle_ticker(fig, ticker, precios, compras_t, color)
    grafico_composicion(fig, resumen, colores)
    sin_datos(fig, mensaje)

  Todos los valores están en USD de la acción subyacente (no del CEDEAR).
==============================================================================
"""

import logging

import matplotlib
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import pandas as pd

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

# ===========================================================================
#  ESTILO  ←  cambiá lo que quieras acá
# ===========================================================================
ESTILO = {
    # Fondos
    "fondo":            "#1c1c1c",   # fondo de la figura (igual al tema de la app)
    "fondo_ejes":       "#222222",   # fondo del área del gráfico

    # Textos y grilla
    "texto":            "#e8e8e8",
    "texto_suave":      "#9a9a9a",
    "grilla":           "#333333",

    # Colores principales
    "principal":        "#4aa3ff",   # línea del valor de la cartera
    "invertido":        "#bbbbbb",   # línea del capital invertido
    "positivo":         "#2ecc71",   # ganancias
    "negativo":         "#ff5c5c",   # pérdidas
    "compra":           "#ffd166",   # marcadores de tus compras

    # Colores por acción (se asignan en orden alfabético de ticker)
    "paleta": [
        "#4aa3ff", "#ff7f50", "#2ecc71", "#c77dff", "#ffd166",
        "#00d1d1", "#ff4d8d", "#b5e48c", "#b08968", "#f1f1f1",
        "#7b6cff", "#ff9f1c", "#a0c4ff", "#e5989b", "#52b788",
    ],

    # Tipografía
    "fuente":           "Segoe UI",
    "tam_titulo":       15,
    "tam_subtitulo":    10,
    "tam_texto":        9,

    # Líneas y rellenos
    "grosor_linea":       2.4,       # líneas principales
    "grosor_linea_multi": 1.8,       # cuando hay muchas líneas juntas
    "alpha_relleno":      0.18,      # transparencia de las zonas verde/roja

    # Formato de fechas en el eje X
    "formato_fecha":    "%d/%m",
}

matplotlib.rcParams["font.family"] = [ESTILO["fuente"], "DejaVu Sans"]
# Evita que "US$ ... US$" se interprete como fórmula matemática
if "text.parse_math" in matplotlib.rcParams:
    matplotlib.rcParams["text.parse_math"] = False
E = ESTILO


# ===========================================================================
#  Helpers internos
# ===========================================================================

def colores_tickers(tickers) -> dict:
    """Asigna un color fijo a cada ticker (orden alfabético)."""
    pal = E["paleta"]
    return {t: pal[i % len(pal)] for i, t in enumerate(sorted(tickers))}


def _fmt_usd(valor_max: float):
    """Formateador del eje Y en USD (con decimales si los montos son chicos)."""
    dec = 2 if abs(valor_max) < 1000 else 0
    return mticker.FuncFormatter(lambda y, _: f"US$ {y:,.{dec}f}")


def _base(fig, titulo=None, subtitulo=None, color_sub=None):
    fig.clear()
    fig.set_facecolor(E["fondo"])
    if titulo:
        fig.text(0.05, 0.965, titulo, color=E["texto"], fontsize=E["tam_titulo"],
                 fontweight="bold", va="top")
    if subtitulo:
        fig.text(0.05, 0.915, subtitulo, color=color_sub or E["texto_suave"],
                 fontsize=E["tam_subtitulo"], va="top")


def _ejes(ax):
    ax.set_facecolor(E["fondo_ejes"])
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(E["grilla"])
    ax.tick_params(colors=E["texto_suave"], labelsize=E["tam_texto"])
    ax.grid(True, color=E["grilla"], linewidth=0.6)
    ax.set_axisbelow(True)


def _eje_fechas(ax):
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=10))
    ax.xaxis.set_major_formatter(mdates.DateFormatter(E["formato_fecha"]))


def _leyenda(ax, **kw):
    kw.setdefault("loc", "upper left")
    kw.setdefault("frameon", False)
    kw.setdefault("fontsize", E["tam_texto"])
    leg = ax.legend(**kw)
    for txt in leg.get_texts():
        txt.set_color(E["texto"])
    return leg


def sin_datos(fig, mensaje="Sin datos"):
    fig.clear()
    fig.set_facecolor(E["fondo"])
    fig.text(0.5, 0.5, mensaje, ha="center", va="center",
             color=E["texto_suave"], fontsize=13)


# ===========================================================================
#  1) Evolución de la cartera completa
# ===========================================================================

def grafico_evolucion_cartera(fig, serie: pd.DataFrame):
    if serie is None or serie.empty:
        return sin_datos(fig, "No hay datos para el período seleccionado.")

    ult = serie.iloc[-1]
    color_res = E["positivo"] if ult["ganancia"] >= 0 else E["negativo"]
    _base(
        fig,
        "Evolución de la cartera en USD",
        f"Valor US$ {ult['valor']:,.2f}   ·   Invertido US$ {ult['invertido']:,.2f}   ·   "
        f"Resultado US$ {ult['ganancia']:+,.2f} ({ult['rend_pct']:+.2f}%)",
        color_sub=color_res,
    )

    gs  = fig.add_gridspec(3, 1, hspace=0.12, left=0.09, right=0.88, top=0.84, bottom=0.08)
    ax1 = fig.add_subplot(gs[0:2])
    ax2 = fig.add_subplot(gs[2], sharex=ax1)
    _ejes(ax1)
    _ejes(ax2)

    x   = serie.index
    v   = serie["valor"].values
    inv = serie["invertido"].values
    marcador = "o" if len(x) < 40 else None

    # Panel superior: valor vs invertido
    ax1.fill_between(x, v, inv, where=v >= inv, interpolate=True,
                     color=E["positivo"], alpha=E["alpha_relleno"])
    ax1.fill_between(x, v, inv, where=v < inv, interpolate=True,
                     color=E["negativo"], alpha=E["alpha_relleno"])
    ax1.plot(x, inv, color=E["invertido"], lw=1.3, ls="--", label="Capital invertido")
    ax1.plot(x, v, color=E["principal"], lw=E["grosor_linea"], marker=marcador, ms=4,
             label="Valor de mercado")
    ax1.annotate(f"US$ {v[-1]:,.2f}", xy=(x[-1], v[-1]), xytext=(8, 0),
                 textcoords="offset points", color=E["principal"], fontweight="bold",
                 va="center", fontsize=E["tam_texto"] + 1, annotation_clip=False)
    ax1.yaxis.set_major_formatter(_fmt_usd(max(v.max(), inv.max())))
    ax1.tick_params(labelbottom=False)
    _leyenda(ax1, loc="best")

    # Panel inferior: rendimiento %
    r = serie["rend_pct"].values
    ax2.fill_between(x, r, 0, where=r >= 0, interpolate=True, color=E["positivo"], alpha=0.35)
    ax2.fill_between(x, r, 0, where=r < 0, interpolate=True, color=E["negativo"], alpha=0.35)
    ax2.plot(x, r, color=E["texto"], lw=1.2, marker=marcador, ms=3)
    ax2.axhline(0, color=E["texto_suave"], lw=0.8)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda y, _: f"{y:+.1f}%"))
    ax2.set_ylabel("Rendimiento", color=E["texto_suave"], fontsize=E["tam_texto"])
    _eje_fechas(ax2)


# ===========================================================================
#  2) Rendimiento de cada acción (vs tu precio promedio de compra)
# ===========================================================================

def grafico_rendimiento_tickers(fig, rend: pd.DataFrame, colores: dict):
    if rend is not None:
        rend = rend.dropna(axis=1, how="all")
    if rend is None or rend.empty:
        return sin_datos(fig, "Seleccioná al menos una acción con datos.")

    finales = {t: rend[t].dropna().iloc[-1] for t in rend.columns}
    orden   = sorted(finales, key=finales.get, reverse=True)
    mejor, peor = orden[0], orden[-1]

    _base(
        fig,
        "Rendimiento de cada acción en USD",
        f"Respecto a tu precio promedio de compra   ·   Mejor: {mejor} {finales[mejor]:+.2f}%"
        f"   ·   Peor: {peor} {finales[peor]:+.2f}%",
    )

    ax = fig.add_subplot(111)
    fig.subplots_adjust(left=0.08, right=0.80, top=0.84, bottom=0.08)
    _ejes(ax)
    ax.axhline(0, color=E["texto_suave"], lw=1, ls="--")

    for t in orden:
        s = rend[t].dropna()
        c = colores.get(t, E["principal"])
        ax.plot(s.index, s.values, color=c, lw=E["grosor_linea_multi"],
                label=f"{t:<6}{finales[t]:+7.2f}%")
        ax.scatter([s.index[-1]], [s.values[-1]], color=c, s=24, zorder=5)

    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda y, _: f"{y:+.1f}%"))
    _eje_fechas(ax)
    leg = _leyenda(ax, bbox_to_anchor=(1.02, 1), prop={"family": "monospace", "size": 9})
    for linea in leg.get_lines():
        linea.set_linewidth(3)


# ===========================================================================
#  3) Detalle de una acción: precio USD + tus compras + precio promedio
# ===========================================================================

def grafico_detalle_ticker(fig, ticker: str, precios: pd.Series,
                           compras_t: pd.DataFrame, color: str):
    precios = precios.dropna() if precios is not None else None
    if precios is None or precios.empty:
        return sin_datos(fig, f"No hay precios disponibles para {ticker}.")

    df_t = compras_t.sort_values(["fecha", "id"]).copy()
    if "tipo" not in df_t.columns:
        df_t["tipo"] = "COMPRA"

    acc_actual = 0.0
    costo_actual = 0.0
    for tx in df_t.itertuples():
        if tx.tipo == "VENTA":
            if acc_actual > 0:
                frac = min(1.0, tx.acciones / acc_actual)
                costo_actual = max(0.0, costo_actual * (1.0 - frac))
                acc_actual = max(0.0, acc_actual - tx.acciones)
        else:
            acc_actual += tx.acciones
            costo_actual += tx.acciones * tx.precio_usd

    actual = float(precios.iloc[-1])
    ppc = (costo_actual / acc_actual) if acc_actual > 1e-9 else 0.0
    rend = ((actual / ppc - 1) * 100) if ppc > 1e-9 else 0.0
    gan = (acc_actual * actual - costo_actual) if acc_actual > 1e-9 else 0.0

    sub_txt = (
        f"Posición: {acc_actual:.4g} acc   ·   Actual US$ {actual:,.2f}   ·   "
        f"Precio prom. US$ {ppc:,.2f}   ·   Rend. {rend:+.2f}%   ·   Resultado US$ {gan:+,.2f}"
    ) if acc_actual > 1e-9 else (
        f"Posición cerrada (0 acc)   ·   Actual US$ {actual:,.2f}"
    )

    _base(
        fig,
        f"{ticker}  ·  precio de la acción en USD",
        sub_txt,
        color_sub=E["positivo"] if gan >= 0 else E["negativo"],
    )

    ax = fig.add_subplot(111)
    fig.subplots_adjust(left=0.09, right=0.90, top=0.84, bottom=0.08)
    _ejes(ax)

    x, y = precios.index, precios.values
    if ppc > 1e-9:
        ax.fill_between(x, y, ppc, where=y >= ppc, interpolate=True,
                        color=E["positivo"], alpha=E["alpha_relleno"])
        ax.fill_between(x, y, ppc, where=y < ppc, interpolate=True,
                        color=E["negativo"], alpha=E["alpha_relleno"])
    ax.plot(x, y, color=color, lw=E["grosor_linea"], label=f"Precio {ticker} (USD)")

    if ppc > 1e-9:
        ax.axhline(ppc, color=E["texto_suave"], ls="--", lw=1.1,
                   label=f"Tu precio promedio: US$ {ppc:,.2f}")

    # Marcadores de Compras (▲) y Ventas (▼)
    compras_solo = df_t[df_t["tipo"] == "COMPRA"]
    ventas_solo = df_t[df_t["tipo"] == "VENTA"]

    if not compras_solo.empty:
        fechas_c = [pd.Timestamp(f) for f in compras_solo["fecha"]]
        ax.scatter(fechas_c, compras_solo["precio_usd"], marker="^", s=110, color=E["compra"],
                   edgecolor="white", linewidth=1, zorder=6, label="Compras")
        for f, p, a in zip(fechas_c, compras_solo["precio_usd"], compras_solo["acciones"]):
            ax.annotate(f"+{a:.4g} acc\nUS$ {p:,.2f}", xy=(f, p), xytext=(0, 14),
                        textcoords="offset points", ha="center", color=E["texto"],
                        fontsize=E["tam_texto"] - 1)

    if not ventas_solo.empty:
        fechas_v = [pd.Timestamp(f) for f in ventas_solo["fecha"]]
        ax.scatter(fechas_v, ventas_solo["precio_usd"], marker="v", s=110, color="#ff4d4d",
                   edgecolor="white", linewidth=1, zorder=6, label="Ventas")
        for f, p, a in zip(fechas_v, ventas_solo["precio_usd"], ventas_solo["acciones"]):
            ax.annotate(f"-{a:.4g} acc\nUS$ {p:,.2f}", xy=(f, p), xytext=(0, -22),
                        textcoords="offset points", ha="center", color="#ff7b7b",
                        fontsize=E["tam_texto"] - 1)

    ax.annotate(f"US$ {actual:,.2f}", xy=(x[-1], actual), xytext=(8, 0),
                textcoords="offset points", color=color, fontweight="bold",
                va="center", fontsize=E["tam_texto"] + 1, annotation_clip=False)

    max_val = max(y.max(), ppc if ppc > 1e-9 else y.max())
    ax.yaxis.set_major_formatter(_fmt_usd(max_val))
    _eje_fechas(ax)
    _leyenda(ax)


# ===========================================================================
#  4) Composición (dona) + Ganancia/Pérdida por posición (barras)
# ===========================================================================

def grafico_composicion(fig, resumen: pd.DataFrame, colores: dict):
    df = resumen.dropna(subset=["valor"]) if resumen is not None and not resumen.empty else None
    if df is None or df.empty:
        return sin_datos(fig, "Sin posiciones con precio disponible.")

    total = df["valor"].sum()
    gan   = df["ganancia"].sum()
    _base(
        fig,
        "Composición y resultado por posición",
        f"Total US$ {total:,.2f}   ·   Resultado US$ {gan:+,.2f}",
        color_sub=E["positivo"] if gan >= 0 else E["negativo"],
    )

    # --- Dona de composición ---
    ax1 = fig.add_axes([0.02, 0.05, 0.44, 0.78])
    ax1.set_facecolor(E["fondo"])
    dp = df.sort_values("valor", ascending=False)
    _, _, autotextos = ax1.pie(
        dp["valor"],
        labels=dp["ticker"],
        colors=[colores.get(t, E["principal"]) for t in dp["ticker"]],
        startangle=90, counterclock=False,
        autopct=lambda p: f"{p:.1f}%" if p >= 3 else "",
        pctdistance=0.81, labeldistance=1.08,
        wedgeprops=dict(width=0.38, edgecolor=E["fondo"], linewidth=2),
        textprops=dict(color=E["texto"], fontsize=E["tam_texto"]),
    )
    for t in autotextos:
        t.set_fontsize(E["tam_texto"] - 1)
        t.set_color("#111111")
        t.set_fontweight("bold")
    ax1.text(0, 0.10, "Total", ha="center", color=E["texto_suave"], fontsize=E["tam_texto"])
    ax1.text(0, -0.10, f"US$ {total:,.2f}", ha="center", color=E["texto"],
             fontsize=13, fontweight="bold")

    # --- Barras de ganancia / pérdida ---
    ax2 = fig.add_axes([0.58, 0.08, 0.38, 0.72])
    _ejes(ax2)
    ax2.grid(axis="y", visible=False)
    db = df.sort_values("ganancia")
    cols = [E["positivo"] if g >= 0 else E["negativo"] for g in db["ganancia"]]
    barras = ax2.barh(db["ticker"], db["ganancia"], color=cols, height=0.62)
    ax2.axvline(0, color=E["texto_suave"], lw=0.8)

    span = max(db["ganancia"].abs().max(), 1e-9)
    for b, g, r in zip(barras, db["ganancia"], db["rend"]):
        ax2.text(g + (span * 0.04 if g >= 0 else -span * 0.04),
                 b.get_y() + b.get_height() / 2,
                 f"{g:+.2f} ({r:+.1f}%)",
                 va="center", ha="left" if g >= 0 else "right",
                 color=E["positivo"] if g >= 0 else E["negativo"],
                 fontsize=E["tam_texto"] - 1, fontweight="bold")
    ax2.set_xlim(-span * 1.8, span * 1.8)
    ax2.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:+.2f}"))
    ax2.set_title("Ganancia / pérdida (US$)", color=E["texto"],
                  fontsize=E["tam_texto"] + 2, loc="left", pad=10)
