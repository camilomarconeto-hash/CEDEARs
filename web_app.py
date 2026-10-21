"""
==============================================================================
  MI CARTERA — App Web (Streamlit)
==============================================================================
  Acceso web desde cualquier dispositivo (PC, móvil, tablet).
  Calcula siempre la evolución en USD de la acción subyacente.
==============================================================================
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
import streamlit as st

# Módulos propios del proyecto
import datos
import graficos

# -----------------------------------------------------------------------------
# Configuración general de la página Streamlit
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Mi Cartera · CEDEARs en USD",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilos CSS personalizados para mejorar el diseño oscuro y las tarjetas
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #1c1c1c;
        border: 1px solid #2a2a2a;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 10px;
    }
    .metric-title {
        color: #9a9a9a;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #ffffff;
        margin-top: 2px;
    }
    .metric-sub-pos { color: #2ecc71; font-weight: 600; font-size: 0.95rem; }
    .metric-sub-neg { color: #ff5c5c; font-weight: 600; font-size: 0.95rem; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Funciones auxiliares y caché de precios
# -----------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def obtener_precios_cached(tickers_tuple, desde_str):
    """Descarga de precios con caché de 10 minutos para que la web sea ultra rápida."""
    desde = date.fromisoformat(desde_str)
    return datos.descargar_precios(list(tickers_tuple), desde)


def fmt_usd(x, signo=False) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"US$ {x:+,.2f}" if signo else f"US$ {x:,.2f}"


def fmt_pct(x) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x:+.2f}%"


def fmt_acc(x) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x:.6f}".rstrip("0").rstrip(".")


# -----------------------------------------------------------------------------
# Carga de datos principales
# -----------------------------------------------------------------------------
df_compras = datos.cargar_compras()

# Sidebar: estado y controles rápidos
with st.sidebar:
    st.title("📈 Mi Cartera")
    st.caption("Seguimiento de CEDEARs en **USD** (acción subyacente)")
    st.divider()

    btn_refrescar = st.button("🔄 Actualizar precios ahora", use_container_width=True)
    if btn_refrescar:
        st.cache_data.clear()
        st.rerun()

    st.write("")
    st.caption(f"📅 Fecha actual: **{datetime.now().strftime('%d/%m/%Y')}**")
    st.caption("💡 Valores independientes de las fluctuaciones del tipo de cambio.")
    st.divider()
    st.markdown("### 🎨 Opciones de visualización")
    periodo_seleccionado = st.selectbox(
        "Rango de tiempo en gráficos:",
        options=["Todo", "1 semana", "1 mes", "3 meses", "6 meses", "1 año"],
        index=0,
    )

# Descargar precios si hay operaciones
precios = pd.DataFrame()
if not df_compras.empty:
    tickers = tuple(sorted(df_compras["ticker"].unique()))
    fecha_min = df_compras["fecha"].min() - timedelta(days=datos.DIAS_CONTEXTO)
    with st.spinner("Descargando precios de Yahoo Finance..."):
        try:
            precios = obtener_precios_cached(tickers, fecha_min.isoformat())
        except Exception as e:
            st.error(f"Error al descargar precios: {e}")

# Cálculos principales
resumen = pd.DataFrame()
serie_cartera = pd.DataFrame()
rend_tickers = pd.DataFrame()
colores = {}

if not df_compras.empty and not precios.empty:
    resumen = datos.resumen_posiciones(df_compras, precios)
    serie_cartera = datos.serie_cartera(df_compras, precios)
    rend_tickers = datos.rendimiento_por_ticker(df_compras, precios)
    colores = graficos.colores_tickers(df_compras["ticker"].unique())

# -----------------------------------------------------------------------------
# Tarjetas métricas superiores (Header)
# -----------------------------------------------------------------------------
if not resumen.empty:
    val_total = resumen["valor"].sum()
    inv_total = resumen["invertido"].sum()
    gan_total = val_total - inv_total
    rend_total = (gan_total / inv_total * 100) if inv_total > 1e-9 else 0.0
    cambio_dia = resumen["cambio_dia_usd"].sum()
    previo_total = val_total - cambio_dia
    pct_dia = (cambio_dia / previo_total * 100) if previo_total > 1e-9 else 0.0

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("VALOR ACTUAL", fmt_usd(val_total))
    with col2:
        st.metric("CAPITAL INVERTIDO", fmt_usd(inv_total))
    with col3:
        st.metric("GANANCIA / PÉRDIDA", fmt_usd(gan_total, signo=True), delta=f"{fmt_usd(gan_total, signo=True)}")
    with col4:
        st.metric("RENDIMIENTO TOTAL", fmt_pct(rend_total), delta=fmt_pct(rend_total))
    with col5:
        st.metric("VARIACIÓN DEL DÍA", fmt_usd(cambio_dia, signo=True), delta=fmt_pct(pct_dia))
else:
    st.info("👋 Todavía no tenés operaciones cargadas o no hay datos de precios.")

st.write("")

# -----------------------------------------------------------------------------
# Función para recortar series según el período seleccionado
# -----------------------------------------------------------------------------
def recortar_periodo(df_o_serie):
    if df_o_serie is None or len(df_o_serie) == 0:
        return df_o_serie
    dias_dict = {"1 semana": 7, "1 mes": 30, "3 meses": 91, "6 meses": 182, "1 año": 365}
    dias = dias_dict.get(periodo_seleccionado)
    if not dias:
        return df_o_serie
    desde = pd.Timestamp(date.today() - timedelta(days=dias))
    return df_o_serie[df_o_serie.index >= desde]


# -----------------------------------------------------------------------------
# Pestañas principales
# -----------------------------------------------------------------------------
tab_cartera, tab_graficos, tab_operaciones = st.tabs([
    "📊 Cartera actual",
    "📈 Gráficos interactivos",
    "📝 Gestión de Operaciones",
])

# =============================================================================
# PESTAÑA 1: CARTERA
# =============================================================================
with tab_cartera:
    st.subheader("Posiciones en Cartera")
    if resumen.empty:
        st.write("Sin posiciones registradas.")
    else:
        # Preparamos una tabla visualmente limpia
        tabla_mostrar = resumen.copy()
        tabla_mostrar["P. Prom. Compra"] = tabla_mostrar["ppc"].apply(lambda x: fmt_usd(x))
        tabla_mostrar["Precio Actual"] = tabla_mostrar["precio"].apply(lambda x: fmt_usd(x))
        tabla_mostrar["Var. Día"] = tabla_mostrar["var_dia"].apply(fmt_pct)
        tabla_mostrar["Invertido"] = tabla_mostrar["invertido"].apply(lambda x: fmt_usd(x))
        tabla_mostrar["Valor Total"] = tabla_mostrar["valor"].apply(lambda x: fmt_usd(x))
        tabla_mostrar["Ganancia US$"] = tabla_mostrar["ganancia"].apply(lambda x: fmt_usd(x, signo=True))
        tabla_mostrar["Rendimiento"] = tabla_mostrar["rend"].apply(fmt_pct)
        tabla_mostrar["Peso"] = tabla_mostrar["peso"].apply(lambda x: f"{x:.1f}%")
        tabla_mostrar["Acciones"] = tabla_mostrar["acciones"].apply(fmt_acc)

        cols_orden = [
            "ticker", "Acciones", "P. Prom. Compra", "Precio Actual",
            "Var. Día", "Invertido", "Valor Total", "Ganancia US$",
            "Rendimiento", "Peso"
        ]
        st.dataframe(
            tabla_mostrar[cols_orden].rename(columns={"ticker": "Ticker"}),
            use_container_width=True,
            hide_index=True,
        )

# =============================================================================
# PESTAÑA 2: GRÁFICOS
# =============================================================================
with tab_graficos:
    st.subheader("Evolución y Rendimiento")

    tipo_grafico = st.radio(
        "Seleccioná el gráfico a visualizar:",
        [
            "Evolución de la cartera (Valor vs. Invertido)",
            "Rendimiento comparativo por acción (%)",
            "Detalle individual por acción (con compras y ventas)",
            "Composición de la cartera (Dona y P&L)",
        ],
        horizontal=True,
    )

    if serie_cartera.empty or precios.empty:
        st.warning("No hay suficientes datos históricos para graficar.")
    else:
        fig = Figure(figsize=(12, 6.2), dpi=100)
        fig.set_facecolor(graficos.ESTILO["fondo"])

        if tipo_grafico == "Evolución de la cartera (Valor vs. Invertido)":
            graficos.grafico_evolucion_cartera(fig, recortar_periodo(serie_cartera))
            st.pyplot(fig, use_container_width=True)

        elif tipo_grafico == "Rendimiento comparativo por acción (%)":
            tickers_disponibles = sorted(rend_tickers.columns.tolist())
            tickers_sel = st.multiselect(
                "Filtrar acciones visibles:",
                options=tickers_disponibles,
                default=tickers_disponibles,
            )
            if tickers_sel:
                rend_filtrado = rend_tickers[tickers_sel]
                graficos.grafico_rendimiento_tickers(fig, recortar_periodo(rend_filtrado), colores)
                st.pyplot(fig, use_container_width=True)
            else:
                st.info("Seleccioná al menos una acción para mostrar.")

        elif tipo_grafico == "Detalle individual por acción (con compras y ventas)":
            tickers_disponibles = sorted(df_compras["ticker"].unique())
            ticker_elegido = st.selectbox("Elegí el ticker:", options=tickers_disponibles)
            if ticker_elegido in precios.columns:
                compras_t = df_compras[df_compras["ticker"] == ticker_elegido]
                desde = pd.Timestamp(compras_t["fecha"].min()) - timedelta(days=30)
                s = precios[ticker_elegido].dropna()
                s = recortar_periodo(s[s.index >= desde])
                col = colores.get(ticker_elegido, "#4aa3ff")
                graficos.grafico_detalle_ticker(fig, ticker_elegido, s, compras_t, col)
                st.pyplot(fig, use_container_width=True)
            else:
                st.warning(f"No hay precios disponibles para {ticker_elegido}.")

        elif tipo_grafico == "Composición de la cartera (Dona y P&L)":
            graficos.grafico_composicion(fig, resumen, colores)
            st.pyplot(fig, use_container_width=True)

# =============================================================================
# PESTAÑA 3: GESTIÓN DE OPERACIONES
# =============================================================================
with tab_operaciones:
    st.subheader("Registro y Modificación de Operaciones")

    col_form, col_tabla = st.columns([1, 1.4], gap="large")

    with col_form:
        st.markdown("#### ➕ Nueva Operación")
        with st.form("form_nueva_operacion", clear_on_submit=True):
            tipo_op = st.radio("Tipo:", ["🟢 COMPRA", "🔴 VENTA"], horizontal=True)
            fecha_op = st.date_input("Fecha de la operación:", value=date.today())
            ticker_op = st.text_input("Ticker (símbolo en Yahoo Finance):", placeholder="Ej: AAPL, NVDA, GLD").strip().upper()

            modo_cantidad = st.radio(
                "Modo de ingreso de cantidad:",
                ["CEDEARs nominales + ratio", "Acciones equivalentes directas"],
                horizontal=True,
            )

            col_c1, col_c2 = st.columns(2)
            if modo_cantidad == "CEDEARs nominales + ratio":
                with col_c1:
                    cedears_input = st.number_input("CEDEARs:", min_value=0.000001, step=1.0, format="%.4f")
                with col_c2:
                    ratio_input = st.number_input("Ratio (CEDEARs por acción):", min_value=0.0001, value=1.0, step=1.0)
                acciones_final = cedears_input / ratio_input if ratio_input > 0 else 0.0
            else:
                acciones_final = st.number_input("Acciones equivalentes:", min_value=0.000001, step=0.01, format="%.6f")

            precio_input = st.number_input("Precio de la acción en USD:", min_value=0.01, step=0.5, format="%.2f")
            nota_input = st.text_input("Nota (opcional):", placeholder="Ej: Compra mensual, ajuste")

            btn_submit = st.form_submit_button("💾 Guardar operación", use_container_width=True)

            if btn_submit:
                if not ticker_op:
                    st.error("Por favor ingresá un Ticker válido.")
                elif acciones_final <= 0:
                    st.error("La cantidad de acciones debe ser mayor a 0.")
                elif precio_input <= 0:
                    st.error("El precio debe ser mayor a 0.")
                else:
                    tipo_limpio = "VENTA" if "VENTA" in tipo_op else "COMPRA"
                    datos.agregar_transaccion(fecha_op, tipo_limpio, ticker_op, acciones_final, precio_input, nota_input)
                    st.cache_data.clear()
                    st.success(f"Operación registrada: {tipo_limpio} {acciones_final:.4g} {ticker_op} a US$ {precio_input:.2f}")
                    st.rerun()

    with col_tabla:
        st.markdown("#### 📋 Historial de Operaciones")
        if df_compras.empty:
            st.info("No hay operaciones registradas.")
        else:
            # Mostrar tabla formateada
            df_mostrar_ops = df_compras.sort_values(["fecha", "id"], ascending=False).copy()
            df_mostrar_ops["Total USD"] = (df_mostrar_ops["acciones"] * df_mostrar_ops["precio_usd"]).apply(lambda x: fmt_usd(x))
            df_mostrar_ops["Precio USD"] = df_mostrar_ops["precio_usd"].apply(lambda x: fmt_usd(x))
            df_mostrar_ops["Acciones"] = df_mostrar_ops["acciones"].apply(fmt_acc)

            st.dataframe(
                df_mostrar_ops[["id", "fecha", "tipo", "ticker", "Acciones", "Precio USD", "Total USD", "nota"]].rename(
                    columns={"id": "ID", "fecha": "Fecha", "tipo": "Tipo", "ticker": "Ticker", "nota": "Nota"}
                ),
                use_container_width=True,
                hide_index=True,
            )

            st.write("")
            st.markdown("#### ✏️ Modificar o Eliminar Operación existente")
            ids_lista = df_compras["id"].tolist()
            id_seleccionado = st.selectbox("Elegí el ID de la operación a editar/borrar:", options=ids_lista)

            if id_seleccionado:
                fila_sel = df_compras[df_compras["id"] == id_seleccionado].iloc[0]

                with st.expander(f"Editar datos de la Operación #{id_seleccionado} ({fila_sel['ticker']})", expanded=False):
                    with st.form("form_editar_operacion"):
                        tipo_edit = st.radio("Tipo:", ["COMPRA", "VENTA"], index=0 if fila_sel.get("tipo", "COMPRA") == "COMPRA" else 1, horizontal=True)
                        fecha_edit = st.date_input("Fecha:", value=fila_sel["fecha"])
                        ticker_edit = st.text_input("Ticker:", value=fila_sel["ticker"]).strip().upper()
                        acc_edit = st.number_input("Acciones equivalentes:", value=float(fila_sel["acciones"]), min_value=0.000001, format="%.6f")
                        precio_edit = st.number_input("Precio en USD:", value=float(fila_sel["precio_usd"]), min_value=0.01, format="%.2f")
                        nota_edit = st.text_input("Nota:", value=str(fila_sel.get("nota", "")))

                        col_ed1, col_ed2 = st.columns(2)
                        with col_ed1:
                            btn_guardar_edit = st.form_submit_button("✔ Guardar cambios", use_container_width=True)
                        with col_ed2:
                            pass

                        if btn_guardar_edit:
                            datos.editar_transaccion(id_seleccionado, fecha_edit, tipo_edit, ticker_edit, acc_edit, precio_edit, nota_edit)
                            st.cache_data.clear()
                            st.success(f"Operación #{id_seleccionado} actualizada correctamente.")
                            st.rerun()

                # Botón de eliminación
                if st.button("🗑 Eliminar esta operación", key="btn_eliminar_op"):
                    datos.eliminar_compra(id_seleccionado)
                    st.cache_data.clear()
                    st.success(f"Operación #{id_seleccionado} eliminada.")
                    st.rerun()
