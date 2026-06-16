"""
CTR por anuncio y formato — Hofmann Meta Ads
Página integrada en el dashboard Hofmann Ads
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import os
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Hofmann | CTR Anuncios",
    page_icon="📈",
    layout="wide",
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] [data-baseweb="tag"] {
    background-color: #1877F2 !important;
    color: #ffffff !important;
}
h1, h2, h3 { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ─── Credenciales ─────────────────────────────────────────────────────────────
def _s(key, default=""):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

META_TOKEN      = _s("META_ACCESS_TOKEN")
META_ACCOUNT_ID = _s("META_AD_ACCOUNT_ID", "2649358358505616")

# ─── Detección de formato ──────────────────────────────────────────────────────
FORMAT_ORDER = ["Video", "Single Image", "Carrusel", "Colección", "Otro"]

def detect_format(ad_name: str) -> str:
    n = ad_name.lower()
    if "video" in n:
        return "Video"
    if "carousel" in n or "carrusel" in n:
        return "Carrusel"
    if "collection" in n or "coleccion" in n or "colección" in n:
        return "Colección"
    if "singleimage" in n or "single image" in n or "single_image" in n:
        return "Single Image"
    return "Single Image"

# ─── Conector Meta Ads — nivel anuncio, semanal ───────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_meta_ctr_data(start: str, end: str) -> pd.DataFrame:
    if not META_TOKEN:
        return pd.DataFrame()

    base_url = f"https://graph.facebook.com/v25.0/act_{META_ACCOUNT_ID}/insights"
    params = {
        "access_token": META_TOKEN,
        "level": "ad",
        "fields": "campaign_name,adset_name,ad_name,impressions,clicks,ctr,spend",
        "time_range": f'{{"since":"{start}","until":"{end}"}}',
        "time_increment": "7",
        "limit": "500",
    }

    rows, url = [], base_url
    while url:
        resp = requests.get(url, params=params if url == base_url else {})
        data = resp.json()
        if "error" in data:
            st.error(f"Error Meta API: {data['error'].get('message', data['error'])}")
            return pd.DataFrame()
        rows.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "campaign_name": "campaña",
        "adset_name":    "conjunto",
        "ad_name":       "anuncio",
        "date_start":    "semana_inicio",
    })
    for col in ["impressions", "clicks", "spend"]:
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0).astype(int)
    df["ctr"]   = pd.to_numeric(df.get("ctr", 0), errors="coerce").fillna(0).round(2)
    df["spend"] = pd.to_numeric(df.get("spend", 0), errors="coerce").fillna(0).round(0)
    df["semana_inicio"] = pd.to_datetime(df["semana_inicio"])
    df["semana_label"]  = df["semana_inicio"].dt.strftime("%-d %b")
    df["formato"]  = df["anuncio"].apply(detect_format)
    df["mercado"]  = df["campaña"].apply(lambda n: (
        "LATAM" if "LAT" in n.upper() else
        "NAC"   if "NAC" in n.upper() else
        "CAT"   if "CAT" in n.upper() else "Otro"
    ))
    return df.sort_values("semana_inicio")


# ─── Helpers CTR heatmap ───────────────────────────────────────────────────────
def ctr_bg(val):
    if pd.isna(val):
        return "background-color: #f5f5f5; color: #ccc"
    if val < 0.01:
        return "background-color: #f5f5f5; color: #bbb"
    if val < 0.70:
        return "background-color: #c0392b; color: #fff"
    if val < 0.90:
        return "background-color: #e67e22; color: #fff"
    if val < 1.10:
        return "background-color: #f1c40f; color: #555"
    if val < 1.50:
        return "background-color: #a9d18e; color: #1a4020"
    if val < 2.50:
        return "background-color: #27ae60; color: #fff"
    return "background-color: #1a5e38; color: #fff"


def build_pivot(df: pd.DataFrame, index_col: str) -> pd.DataFrame:
    semanas = sorted(df["semana_inicio"].unique())
    labels  = {s: df.loc[df["semana_inicio"] == s, "semana_label"].iloc[0] for s in semanas}
    pivot = (
        df.groupby([index_col, "semana_inicio"])["ctr"]
        .mean()
        .unstack("semana_inicio")
    )
    pivot.columns = [labels[c] for c in pivot.columns]
    return pivot.round(2)


# ─── Sidebar — filtros ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📈 CTR Anuncios")
    st.markdown("---")
    st.markdown("### Filtros")

    col1, col2 = st.columns(2)
    with col1:
        start_d = st.date_input("Desde", value=date(2026, 1, 1), min_value=date(2025, 1, 1))
    with col2:
        end_d = st.date_input("Hasta", value=date.today())

    st.markdown("---")

with st.spinner("Cargando datos Meta Ads..."):
    df_raw = get_meta_ctr_data(str(start_d), str(end_d))

if df_raw.empty:
    st.error("No hay datos disponibles. Verifica el token META_ACCESS_TOKEN en secrets.")
    st.stop()

# Filtros dinámicos tras carga
with st.sidebar:
    mercados = ["Todos"] + sorted(df_raw["mercado"].unique().tolist())
    sel_mercado = st.selectbox("Mercado", mercados)

    campañas_lista = sorted(df_raw["campaña"].unique().tolist())
    if sel_mercado != "Todos":
        campañas_lista = sorted(df_raw[df_raw["mercado"] == sel_mercado]["campaña"].unique().tolist())
    sel_campañas = st.multiselect("Campañas", campañas_lista, default=[])

    formatos_lista = sorted(df_raw["formato"].unique().tolist())
    sel_formatos = st.multiselect("Formatos", formatos_lista, default=[])

    st.markdown("---")
    st.caption("🔄 Datos actualizados cada hora")

# Aplicar filtros
df = df_raw.copy()
if sel_mercado != "Todos":
    df = df[df["mercado"] == sel_mercado]
if sel_campañas:
    df = df[df["campaña"].isin(sel_campañas)]
if sel_formatos:
    df = df[df["formato"].isin(sel_formatos)]

# ─── Header ───────────────────────────────────────────────────────────────────
st.title("📈 CTR por anuncio y formato")
st.caption(f"Meta Ads · Cuenta {META_ACCOUNT_ID} · {start_d.strftime('%-d %b %Y')} → {end_d.strftime('%-d %b %Y')}")

# ─── KPIs ─────────────────────────────────────────────────────────────────────
total_impr  = df["impressions"].sum()
total_clics = df["clicks"].sum()
ctr_global  = (total_clics / total_impr * 100) if total_impr > 0 else 0
n_anuncios  = df["anuncio"].nunique()
n_camps     = df["campaña"].nunique()

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Impresiones", f"{total_impr:,.0f}")
k2.metric("Clics", f"{total_clics:,.0f}")
k3.metric("CTR global", f"{ctr_global:.2f}%")
k4.metric("Anuncios activos", n_anuncios)
k5.metric("Campañas", n_camps)

st.markdown("---")

# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab_heat, tab_camp, tab_formato, tab_evol = st.tabs([
    "🟩 Heatmap CTR",
    "📂 Por campaña → anuncio",
    "🎨 Por formato",
    "📅 Evolución semanal",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Heatmap CTR (semanas × anuncios)
# ══════════════════════════════════════════════════════════════════════════════
with tab_heat:
    st.subheader("CTR % por anuncio · semana a semana")
    st.caption("Formato condicional: 🔴 < 0.7% · 🟠 0.7-0.9% · 🟡 0.9-1.1% · 🟢 1.1-1.5% · 🟩 1.5-2.5% · ⬛ > 2.5%")

    pivot = build_pivot(df, "anuncio")

    styled = pivot.style.map(ctr_bg).format(lambda v: f"{v:.2f}%" if pd.notna(v) else "—")
    st.dataframe(styled, use_container_width=True, height=min(60 + len(pivot) * 36, 700))

    st.download_button(
        "⬇ Descargar CSV",
        data=pivot.to_csv().encode("utf-8"),
        file_name=f"ctr_anuncios_{start_d}_{end_d}.csv",
        mime="text/csv",
    )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Por campaña → anuncio → formato
# ══════════════════════════════════════════════════════════════════════════════
with tab_camp:
    st.subheader("Explorar por campaña")

    campañas_disp = sorted(df["campaña"].unique().tolist())
    camp_sel = st.selectbox("Selecciona campaña", campañas_disp)

    df_camp = df[df["campaña"] == camp_sel]

    col_a, col_b = st.columns([3, 2])

    with col_a:
        st.markdown(f"**Heatmap CTR · {camp_sel}**")
        pivot_camp = build_pivot(df_camp, "anuncio")
        styled_camp = pivot_camp.style.map(ctr_bg).format(
            lambda v: f"{v:.2f}%" if pd.notna(v) else "—"
        )
        st.dataframe(styled_camp, use_container_width=True, height=min(100 + len(pivot_camp) * 36, 500))

    with col_b:
        st.markdown(f"**Totales acumulados · {camp_sel}**")
        resumen = (
            df_camp.groupby("anuncio")
            .agg(
                Formato=("formato", "first"),
                Impresiones=("impressions", "sum"),
                Clics=("clicks", "sum"),
                Inversión=("spend", "sum"),
            )
            .assign(CTR=lambda x: (x["Clics"] / x["Impresiones"] * 100).round(2))
            .sort_values("CTR", ascending=False)
        )
        resumen["Inversión"] = resumen["Inversión"].apply(lambda v: f"€{v:,.0f}")
        resumen["CTR"] = resumen["CTR"].apply(lambda v: f"{v:.2f}%")
        resumen["Impresiones"] = resumen["Impresiones"].apply(lambda v: f"{v:,}")
        st.dataframe(resumen, use_container_width=True)

    st.markdown("---")
    st.markdown(f"**Evolución semanal de CTR · {camp_sel}**")
    df_camp_weekly = (
        df_camp.groupby(["semana_inicio", "semana_label", "anuncio"])
        .agg(impressions=("impressions", "sum"), clicks=("clicks", "sum"))
        .reset_index()
    )
    df_camp_weekly["ctr"] = (df_camp_weekly["clicks"] / df_camp_weekly["impressions"] * 100).round(2)
    df_camp_weekly = df_camp_weekly[df_camp_weekly["impressions"] > 100]

    if not df_camp_weekly.empty:
        fig = px.line(
            df_camp_weekly,
            x="semana_label", y="ctr", color="anuncio",
            markers=True,
            labels={"ctr": "CTR %", "semana_label": "Semana", "anuncio": "Anuncio"},
            height=380,
        )
        fig.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            legend=dict(orientation="v", x=1.01, y=1),
            yaxis=dict(ticksuffix="%", gridcolor="#efefef"),
            xaxis=dict(gridcolor="#efefef"),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Tabla completa: semanas × todas las campañas y anuncios ───────────────
    st.markdown("---")
    st.markdown("### Tabla completa — todas las campañas y anuncios")
    st.caption("Filas = semanas · Columnas = campaña / anuncio · Formato condicional por CTR %")

    # Filtros de la tabla completa
    ft_col1, ft_col2 = st.columns(2)
    with ft_col1:
        sel_mercado_t = st.radio(
            "Mercado", ["Todos", "Nacional", "LATAM"],
            horizontal=True, key="tabla_mercado"
        )
    with ft_col2:
        sel_modalidad_t = st.radio(
            "Modalidad", ["Todas", "Online", "Presencial"],
            horizontal=True, key="tabla_modalidad"
        )

    # Construir pivot con columnas multinivel campaña → anuncio
    df_full = df.copy()

    # Clasificar mercado y modalidad
    df_full["_mercado_t"] = df_full["campaña"].apply(
        lambda n: "Nacional" if n.upper().startswith("NAC_") else "LATAM"
    )
    df_full["_modalidad_t"] = df_full["campaña"].apply(
        lambda n: "Online" if "online" in n.lower() else "Presencial"
    )

    if sel_mercado_t != "Todos":
        df_full = df_full[df_full["_mercado_t"] == sel_mercado_t]
    if sel_modalidad_t != "Todas":
        df_full = df_full[df_full["_modalidad_t"] == sel_modalidad_t]

    n_camps_filtradas = df_full["campaña"].nunique()
    st.caption(f"{n_camps_filtradas} campaña(s) · {df_full['anuncio'].nunique()} anuncio(s)")
    semanas_order = sorted(df_full["semana_inicio"].unique())
    semana_labels = {s: df_full.loc[df_full["semana_inicio"] == s, "semana_label"].iloc[0] for s in semanas_order}

    pivot_full = (
        df_full.groupby(["semana_inicio", "campaña", "anuncio"])["ctr"]
        .mean()
        .reset_index()
    )
    pivot_full["semana"] = pivot_full["semana_inicio"].map(semana_labels)
    pivot_full = pivot_full.pivot_table(
        index="semana",
        columns=["campaña", "anuncio"],
        values="ctr",
        aggfunc="mean",
    ).round(2)

    # Reordenar filas por fecha
    label_to_date = {v: k for k, v in semana_labels.items()}
    pivot_full = pivot_full.loc[
        [l for l in [semana_labels[s] for s in semanas_order] if l in pivot_full.index]
    ]

    styled_full = pivot_full.style.map(ctr_bg).format(
        lambda v: f"{v:.2f}%" if pd.notna(v) else "—"
    )
    st.dataframe(styled_full, use_container_width=True, height=120 + len(pivot_full) * 38)

    st.download_button(
        "⬇ Descargar CSV completo",
        data=pivot_full.to_csv().encode("utf-8"),
        file_name=f"ctr_completo_{start_d}_{end_d}.csv",
        mime="text/csv",
    )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Por formato
# ══════════════════════════════════════════════════════════════════════════════
with tab_formato:
    st.subheader("Rendimiento por formato de creatividad")

    resumen_fmt = (
        df.groupby("formato")
        .agg(
            Impresiones=("impressions", "sum"),
            Clics=("clicks", "sum"),
            Inversión=("spend", "sum"),
            Anuncios=("anuncio", "nunique"),
        )
        .assign(CTR=lambda x: (x["Clics"] / x["Impresiones"] * 100).round(2))
        .sort_values("CTR", ascending=False)
        .reset_index()
    )

    col_f1, col_f2 = st.columns([2, 3])

    with col_f1:
        st.markdown("**CTR promedio por formato**")
        colores = {"Video": "#E24B4A", "Single Image": "#1877F2", "Carrusel": "#27ae60", "Colección": "#BA7517", "Otro": "#888"}
        fig_fmt = px.bar(
            resumen_fmt, x="CTR", y="formato", orientation="h",
            color="formato",
            color_discrete_map=colores,
            text=resumen_fmt["CTR"].apply(lambda v: f"{v:.2f}%"),
            height=300,
        )
        fig_fmt.update_traces(textposition="outside")
        fig_fmt.update_layout(
            showlegend=False, plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(ticksuffix="%", gridcolor="#efefef"),
            yaxis_title="", xaxis_title="CTR %",
        )
        st.plotly_chart(fig_fmt, use_container_width=True)

    with col_f2:
        st.markdown("**Tabla resumen por formato**")
        df_fmt_display = resumen_fmt.copy()
        df_fmt_display["CTR"] = df_fmt_display["CTR"].apply(lambda v: f"{v:.2f}%")
        df_fmt_display["Impresiones"] = df_fmt_display["Impresiones"].apply(lambda v: f"{v:,}")
        df_fmt_display["Clics"] = df_fmt_display["Clics"].apply(lambda v: f"{v:,}")
        df_fmt_display["Inversión"] = df_fmt_display["Inversión"].apply(lambda v: f"€{v:,.0f}")
        st.dataframe(df_fmt_display.set_index("formato"), use_container_width=True)

    st.markdown("---")
    st.markdown("**Evolución semanal de CTR por formato**")
    df_fmt_weekly = (
        df.groupby(["semana_inicio", "semana_label", "formato"])
        .agg(impressions=("impressions", "sum"), clicks=("clicks", "sum"))
        .reset_index()
    )
    df_fmt_weekly["ctr"] = (df_fmt_weekly["clicks"] / df_fmt_weekly["impressions"] * 100).round(2)
    df_fmt_weekly = df_fmt_weekly[df_fmt_weekly["impressions"] > 200]

    if not df_fmt_weekly.empty:
        fig_evol_fmt = px.line(
            df_fmt_weekly,
            x="semana_label", y="ctr", color="formato",
            markers=True,
            color_discrete_map=colores,
            labels={"ctr": "CTR %", "semana_label": "Semana", "formato": "Formato"},
            height=360,
        )
        fig_evol_fmt.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            legend=dict(orientation="h", y=-0.2),
            yaxis=dict(ticksuffix="%", gridcolor="#efefef"),
            xaxis=dict(gridcolor="#efefef"),
        )
        st.plotly_chart(fig_evol_fmt, use_container_width=True)

    st.markdown("---")
    st.markdown("**Heatmap CTR por formato · semana a semana**")
    pivot_fmt = build_pivot(df[df["formato"].isin(df_fmt_weekly["formato"].unique())], "formato")
    styled_fmt = pivot_fmt.style.map(ctr_bg).format(lambda v: f"{v:.2f}%" if pd.notna(v) else "—")
    st.dataframe(styled_fmt, use_container_width=True)

    # ── Por formato: todas las campañas y anuncios ───────────────────────────
    st.markdown("---")
    st.markdown("### Campañas y anuncios por formato")

    fmt_sel = st.selectbox(
        "Selecciona formato", sorted(df["formato"].unique().tolist()), key="sel_formato_detalle"
    )
    df_fmt_detalle = df[df["formato"] == fmt_sel]

    if df_fmt_detalle.empty:
        st.info("Sin datos para este formato en el periodo seleccionado.")
    else:
        st.caption(f"{df_fmt_detalle['campaña'].nunique()} campañas · {df_fmt_detalle['anuncio'].nunique()} anuncios con formato **{fmt_sel}**")

        resumen_fmt_det = (
            df_fmt_detalle.groupby(["campaña", "anuncio"])
            .agg(
                Impresiones=("impressions", "sum"),
                Clics=("clicks", "sum"),
                Inversión=("spend", "sum"),
            )
            .assign(CTR=lambda x: (x["Clics"] / x["Impresiones"] * 100).round(2))
            .sort_values("CTR", ascending=False)
            .reset_index()
        )
        resumen_fmt_det["CTR"]         = resumen_fmt_det["CTR"].apply(lambda v: f"{v:.2f}%")
        resumen_fmt_det["Impresiones"] = resumen_fmt_det["Impresiones"].apply(lambda v: f"{v:,}")
        resumen_fmt_det["Clics"]       = resumen_fmt_det["Clics"].apply(lambda v: f"{v:,}")
        resumen_fmt_det["Inversión"]   = resumen_fmt_det["Inversión"].apply(lambda v: f"€{v:,.0f}")
        st.dataframe(
            resumen_fmt_det.set_index(["campaña", "anuncio"]),
            use_container_width=True,
            height=120 + len(resumen_fmt_det) * 36,
        )

    # ── Por campaña ───────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Desglose por formato · por campaña")

    camp_fmt_sel = st.selectbox(
        "Selecciona campaña", sorted(df["campaña"].unique().tolist()), key="fmt_camp_sel"
    )
    df_camp_fmt = df[df["campaña"] == camp_fmt_sel]

    resumen_camp_fmt = (
        df_camp_fmt.groupby("formato")
        .agg(
            Impresiones=("impressions", "sum"),
            Clics=("clicks", "sum"),
            Inversión=("spend", "sum"),
            Anuncios=("anuncio", "nunique"),
        )
        .assign(CTR=lambda x: (x["Clics"] / x["Impresiones"] * 100).round(2))
        .sort_values("CTR", ascending=False)
        .reset_index()
    )

    if resumen_camp_fmt.empty:
        st.info("Sin datos para esta campaña en el periodo seleccionado.")
    else:
        col_cf1, col_cf2 = st.columns([2, 3])

        with col_cf1:
            st.markdown(f"**CTR por formato · {camp_fmt_sel}**")
            fig_cf = px.bar(
                resumen_camp_fmt, x="CTR", y="formato", orientation="h",
                color="formato",
                color_discrete_map=colores,
                text=resumen_camp_fmt["CTR"].apply(lambda v: f"{v:.2f}%"),
                height=max(200, len(resumen_camp_fmt) * 60),
            )
            fig_cf.update_traces(textposition="outside")
            fig_cf.update_layout(
                showlegend=False, plot_bgcolor="white", paper_bgcolor="white",
                xaxis=dict(ticksuffix="%", gridcolor="#efefef"),
                yaxis_title="", xaxis_title="CTR %",
            )
            st.plotly_chart(fig_cf, use_container_width=True)

        with col_cf2:
            st.markdown(f"**Tabla resumen · {camp_fmt_sel}**")
            df_cf_display = resumen_camp_fmt.copy()
            df_cf_display["CTR"]         = df_cf_display["CTR"].apply(lambda v: f"{v:.2f}%")
            df_cf_display["Impresiones"] = df_cf_display["Impresiones"].apply(lambda v: f"{v:,}")
            df_cf_display["Clics"]       = df_cf_display["Clics"].apply(lambda v: f"{v:,}")
            df_cf_display["Inversión"]   = df_cf_display["Inversión"].apply(lambda v: f"€{v:,.0f}")
            st.dataframe(df_cf_display.set_index("formato"), use_container_width=True)

        # Evolución semanal por formato para esa campaña
        df_cf_weekly = (
            df_camp_fmt.groupby(["semana_inicio", "semana_label", "formato"])
            .agg(impressions=("impressions", "sum"), clicks=("clicks", "sum"))
            .reset_index()
        )
        df_cf_weekly["ctr"] = (df_cf_weekly["clicks"] / df_cf_weekly["impressions"] * 100).round(2)
        df_cf_weekly = df_cf_weekly[df_cf_weekly["impressions"] > 50]

        if not df_cf_weekly.empty:
            st.markdown(f"**Evolución semanal por formato · {camp_fmt_sel}**")
            fig_cf_evol = px.line(
                df_cf_weekly,
                x="semana_label", y="ctr", color="formato",
                markers=True,
                color_discrete_map=colores,
                labels={"ctr": "CTR %", "semana_label": "Semana", "formato": "Formato"},
                height=320,
            )
            fig_cf_evol.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(orientation="h", y=-0.25),
                yaxis=dict(ticksuffix="%", gridcolor="#efefef"),
                xaxis=dict(gridcolor="#efefef"),
            )
            st.plotly_chart(fig_cf_evol, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Evolución semanal completa
# ══════════════════════════════════════════════════════════════════════════════
with tab_evol:
    st.subheader("Evolución semanal — todas las campañas")

    vista = st.radio("Agrupar por", ["Campaña", "Formato", "Mercado"], horizontal=True)
    col_map = {"Campaña": "campaña", "Formato": "formato", "Mercado": "mercado"}
    grp = col_map[vista]

    df_evol = (
        df.groupby(["semana_inicio", "semana_label", grp])
        .agg(impressions=("impressions", "sum"), clicks=("clicks", "sum"))
        .reset_index()
    )
    df_evol["ctr"] = (df_evol["clicks"] / df_evol["impressions"] * 100).round(2)
    df_evol = df_evol[df_evol["impressions"] > 200]

    metrica = st.selectbox("Métrica", ["CTR %", "Clics", "Impresiones"])
    y_col = {"CTR %": "ctr", "Clics": "clicks", "Impresiones": "impressions"}[metrica]
    y_label = {"CTR %": "CTR %", "Clics": "Clics", "Impresiones": "Impresiones"}[metrica]

    fig_evol = px.line(
        df_evol, x="semana_label", y=y_col, color=grp,
        markers=True,
        labels={y_col: y_label, "semana_label": "Semana"},
        height=450,
    )
    if metrica == "CTR %":
        fig_evol.update_layout(yaxis=dict(ticksuffix="%"))
    fig_evol.update_layout(
        plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="v", x=1.01, y=1, font=dict(size=11)),
        xaxis=dict(gridcolor="#efefef"),
        yaxis=dict(gridcolor="#efefef"),
    )
    st.plotly_chart(fig_evol, use_container_width=True)

    st.markdown("---")
    st.markdown("**Tabla completa semanal**")
    pivot_evol = build_pivot(df, grp)
    styled_evol = pivot_evol.style.map(ctr_bg).format(
        lambda v: f"{v:.2f}%" if pd.notna(v) else "—"
    )
    st.dataframe(styled_evol, use_container_width=True, height=min(100 + len(pivot_evol) * 36, 600))
