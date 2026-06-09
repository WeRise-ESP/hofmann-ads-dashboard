"""
Dashboard de Inversión Publicitaria — Hofmann
Fuentes: Google Ads + Meta Ads + LinkedIn Ads + TikTok Ads
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import json
import os
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Hofmann | Ads Dashboard",
    page_icon="📊",
    layout="wide",
)

# ─── CSS — sidebar y login ────────────────────────────────────────────────────
st.markdown("""
<style>
/* Chips del multiselect */
[data-testid="stSidebar"] [data-baseweb="tag"] {
    background-color: #1877F2 !important;
    color: #ffffff !important;
}
[data-testid="stSidebar"] [data-baseweb="tag"] span {
    color: #ffffff !important;
}
[data-testid="stSidebar"] [data-baseweb="tag"] svg {
    fill: #ffffff !important;
}

/* Botón actualizar */
[data-testid="stSidebar"] button[kind="secondary"],
[data-testid="stSidebar"] .stButton > button {
    background-color: #1877F2 !important;
    color: #ffffff !important;
    border: none !important;
    font-weight: 600 !important;
}

/* ── Login — campo contraseña ── */
input[type="password"] {
    background-color: #ffffff !important;
    color: #1a1a2e !important;
    border: 2px solid #d0d5dd !important;
    border-radius: 8px !important;
}
[data-baseweb="input"] {
    background-color: #ffffff !important;
    border: 2px solid #d0d5dd !important;
    border-radius: 8px !important;
}
input[type="password"]::placeholder {
    color: #9aa5b4 !important;
    opacity: 1 !important;
}
[data-baseweb="input"] button svg {
    fill: #555 !important;
}
</style>
""", unsafe_allow_html=True)

# ─── Autenticación ────────────────────────────────────────────────────────────
def _check_password():
    if st.session_state.get("autenticado"):
        return True
    try:
        pwd_correcta = st.secrets["APP_PASSWORD"]
    except Exception:
        pwd_correcta = os.getenv("APP_PASSWORD", "")

    st.markdown("""
    <div style="max-width:400px;margin:80px auto 0;text-align:center">
        <h2 style="margin-bottom:8px">🔒 Hofmann Ads Dashboard</h2>
        <p style="color:#666;font-size:14px;margin-bottom:24px">
            Introduce la contraseña para continuar
        </p>
    </div>
    """, unsafe_allow_html=True)

    _, col_c, _ = st.columns([1, 2, 1])
    with col_c:
        pwd = st.text_input("Contraseña", type="password",
                            label_visibility="collapsed", placeholder="Contraseña...")
        if st.button("Entrar", use_container_width=True, type="primary"):
            if pwd and pwd == pwd_correcta:
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta")
    return False

if not _check_password():
    st.stop()

# ─── Credenciales ─────────────────────────────────────────────────────────────
def _s(key, default=""):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

# Google Ads
GA_DEVELOPER_TOKEN = _s("GOOGLE_ADS_DEVELOPER_TOKEN")
GA_CLIENT_ID       = _s("GOOGLE_ADS_CLIENT_ID")
GA_CLIENT_SECRET   = _s("GOOGLE_ADS_CLIENT_SECRET")
GA_REFRESH_TOKEN   = _s("GOOGLE_ADS_REFRESH_TOKEN")
GA_LOGIN_CID       = _s("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "4885772142")
GA_CUSTOMER_ID     = _s("GOOGLE_ADS_CUSTOMER_ID", "9010916591")

# Meta Ads
META_TOKEN      = _s("META_ACCESS_TOKEN")
META_ACCOUNT_ID = _s("META_AD_ACCOUNT_ID", "2649358358505616")

# LinkedIn Ads (opcional — se activa cuando haya credenciales)
LINKEDIN_TOKEN      = _s("LINKEDIN_ACCESS_TOKEN")
LINKEDIN_ACCOUNT_ID = _s("LINKEDIN_AD_ACCOUNT_ID")

# TikTok Ads (opcional — se activa cuando haya credenciales)
TIKTOK_TOKEN        = _s("TIKTOK_ACCESS_TOKEN")
TIKTOK_ADVERTISER_ID = _s("TIKTOK_ADVERTISER_ID")

# LinkedIn Ads — fuente alternativa vía Google Sheets (CSV manual desde Campaign Manager)
# Formato del sheet: fecha | campaña | gasto | conversiones | clics | impresiones
LINKEDIN_SHEET_URL  = _s("LINKEDIN_SHEET_URL")

# ─── Configuración de plataformas ─────────────────────────────────────────────
COLORS = {
    "Google Ads":   "#FF6D00",
    "Meta Ads":     "#1877F2",
    "LinkedIn Ads": "#0A66C2",
    "TikTok Ads":   "#FF0050",
}

PLATFORM_ICONS = {
    "Google Ads":   "🟠",
    "Meta Ads":     "🔵",
    "LinkedIn Ads": "🔷",
    "TikTok Ads":   "🩷",
}

# Plataformas activas según credenciales disponibles
AVAILABLE_PLATFORMS = ["Google Ads", "Meta Ads"]
linkedin_via_api    = bool(LINKEDIN_TOKEN and LINKEDIN_ACCOUNT_ID)
linkedin_via_sheets = bool(LINKEDIN_SHEET_URL)
if linkedin_via_api or linkedin_via_sheets:
    AVAILABLE_PLATFORMS.append("LinkedIn Ads")
if TIKTOK_TOKEN and TIKTOK_ADVERTISER_ID:
    AVAILABLE_PLATFORMS.append("TikTok Ads")

# ─── Clasificador de mercado ──────────────────────────────────────────────────
def parse_mercado(name: str, platform: str) -> str:
    n = name.upper()
    if platform == "meta":
        if n.startswith("NAC_"):
            return "Nacional"
        if n.startswith("LAT_"):
            return "Latam"
        return "Otro"
    # Google, LinkedIn, TikTok: buscar tokens en el nombre de campaña
    if any(t in n for t in ["LATAM", "- LAT", "_LAT", "LAT_"]):
        return "Latam"
    if any(t in n for t in ["- ES", "- NAC", "- BCN", "- CAT", "_ES", "_NAC", "_BCN", "_CAT", "- NACI"]):
        return "Nacional"
    return "Otro"

# ─── Conector Google Ads ──────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_google_ads_data(start: str, end: str) -> pd.DataFrame:
    try:
        from google.ads.googleads.client import GoogleAdsClient

        cfg = {
            "developer_token":   GA_DEVELOPER_TOKEN,
            "client_id":         GA_CLIENT_ID,
            "client_secret":     GA_CLIENT_SECRET,
            "refresh_token":     GA_REFRESH_TOKEN,
            "login_customer_id": GA_LOGIN_CID.replace("-", ""),
            "use_proto_plus":    True,
        }
        client     = GoogleAdsClient.load_from_dict(cfg)
        ga_service = client.get_service("GoogleAdsService")

        query = f"""
            SELECT
                campaign.name,
                segments.date,
                metrics.cost_micros,
                metrics.conversions,
                metrics.clicks,
                metrics.impressions
            FROM campaign
            WHERE segments.date BETWEEN '{start}' AND '{end}'
              AND campaign.status != 'REMOVED'
              AND metrics.cost_micros > 0
            ORDER BY segments.date DESC
        """
        rows = []
        for batch in ga_service.search_stream(
            customer_id=GA_CUSTOMER_ID.replace("-", ""), query=query
        ):
            for row in batch.results:
                rows.append({
                    "fecha":        row.segments.date,
                    "campaña":      row.campaign.name,
                    "gasto":        row.metrics.cost_micros / 1_000_000,
                    "conversiones": row.metrics.conversions,
                    "clics":        row.metrics.clicks,
                    "impresiones":  row.metrics.impressions,
                    "plataforma":   "Google Ads",
                })

        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["fecha"]   = pd.to_datetime(df["fecha"])
        df["mercado"] = df["campaña"].apply(lambda x: parse_mercado(x, "google"))
        return df

    except Exception as e:
        st.error(f"Error Google Ads: {e}")
        return pd.DataFrame()

# ─── Conector Meta Ads ────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_meta_ads_data(start: str, end: str) -> pd.DataFrame:
    try:
        url = f"https://graph.facebook.com/v21.0/act_{META_ACCOUNT_ID}/insights"
        params = {
            "access_token": META_TOKEN,
            "fields":       "campaign_name,spend,actions,clicks,impressions",
            "level":        "campaign",
            "time_increment": 1,
            "time_range":   json.dumps({"since": start, "until": end}),
            "limit":        500,
        }
        rows = []
        while True:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()

            for item in data.get("data", []):
                # Hofmann usa Pixel → leads = complete_registration (formulario web)
                leads = 0
                for a in item.get("actions", []):
                    if a.get("action_type") == "offsite_conversion.fb_pixel_complete_registration":
                        leads = float(a.get("value", 0))
                        break
                # Fallback: complete_registration si no aparece el tipo pixel
                if leads == 0:
                    for a in item.get("actions", []):
                        if a.get("action_type") == "complete_registration":
                            leads = float(a.get("value", 0))
                            break
                rows.append({
                    "fecha":        item["date_start"],
                    "campaña":      item.get("campaign_name", ""),
                    "gasto":        float(item.get("spend", 0)),
                    "conversiones": leads,
                    "clics":        int(item.get("clicks", 0)),
                    "impresiones":  int(item.get("impressions", 0)),
                    "plataforma":   "Meta Ads",
                })

            nxt = data.get("paging", {}).get("next")
            if not nxt:
                break
            url, params = nxt, {}

        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["fecha"]   = pd.to_datetime(df["fecha"])
        df["mercado"] = df["campaña"].apply(lambda x: parse_mercado(x, "meta"))
        return df

    except Exception as e:
        st.error(f"Error Meta Ads: {e}")
        return pd.DataFrame()

# ─── Conector LinkedIn Ads ────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_linkedin_ads_data(start: str, end: str) -> pd.DataFrame:
    """
    Requiere en secrets:
      LINKEDIN_ACCESS_TOKEN  — OAuth 2.0 token con scopes r_ads + r_ads_reporting
      LINKEDIN_AD_ACCOUNT_ID — ID numérico de la cuenta de anuncios
    """
    if not LINKEDIN_TOKEN or not LINKEDIN_ACCOUNT_ID:
        return pd.DataFrame()
    try:
        headers = {
            "Authorization": f"Bearer {LINKEDIN_TOKEN}",
            "LinkedIn-Version": "202405",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        # 1. Obtener nombres de campañas
        camp_resp = requests.get(
            "https://api.linkedin.com/rest/adCampaigns",
            headers=headers,
            params={
                "q": "search",
                "search.account.values[0]": f"urn:li:sponsoredAccount:{LINKEDIN_ACCOUNT_ID}",
                "fields": "id,name",
                "count": 200,
            },
            timeout=30,
        )
        campaign_names = {}
        if camp_resp.status_code == 200:
            for el in camp_resp.json().get("elements", []):
                campaign_names[str(el["id"])] = el.get("name", f"LI_{el['id']}")

        # 2. Obtener métricas diarias por campaña
        sy, sm, sd = start.split("-")
        ey, em, ed = end.split("-")
        r = requests.get(
            "https://api.linkedin.com/rest/adAnalytics",
            headers=headers,
            params={
                "q": "analytics",
                "pivot": "CAMPAIGN",
                "timeGranularity": "DAILY",
                "accounts[0]": f"urn:li:sponsoredAccount:{LINKEDIN_ACCOUNT_ID}",
                "dateRange.start.year":  sy,
                "dateRange.start.month": str(int(sm)),
                "dateRange.start.day":   str(int(sd)),
                "dateRange.end.year":    ey,
                "dateRange.end.month":   str(int(em)),
                "dateRange.end.day":     str(int(ed)),
                "fields": "costInLocalCurrency,externalWebsiteConversions,clicks,impressions,pivotValues,dateRange",
                "count": 500,
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()

        rows = []
        for item in data.get("elements", []):
            gasto = float(item.get("costInLocalCurrency", 0) or 0)
            if gasto == 0:
                continue

            pivot_vals  = item.get("pivotValues", [])
            campaign_id = pivot_vals[0].replace("urn:li:sponsoredCampaign:", "") if pivot_vals else ""
            camp_name   = campaign_names.get(campaign_id, f"LI_{campaign_id}")

            dr    = item.get("dateRange", {}).get("start", {})
            fecha = f"{dr.get('year', 2024)}-{str(dr.get('month', 1)).zfill(2)}-{str(dr.get('day', 1)).zfill(2)}"

            rows.append({
                "fecha":        fecha,
                "campaña":      camp_name,
                "gasto":        gasto,
                "conversiones": float(item.get("externalWebsiteConversions", 0) or 0),
                "clics":        int(item.get("clicks", 0) or 0),
                "impresiones":  int(item.get("impressions", 0) or 0),
                "plataforma":   "LinkedIn Ads",
            })

        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["fecha"]   = pd.to_datetime(df["fecha"])
        df["mercado"] = df["campaña"].apply(lambda x: parse_mercado(x, "linkedin"))
        return df

    except Exception as e:
        st.error(f"Error LinkedIn Ads: {e}")
        return pd.DataFrame()

# ─── Conector TikTok Ads ──────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_tiktok_ads_data(start: str, end: str) -> pd.DataFrame:
    """
    Requiere en secrets:
      TIKTOK_ACCESS_TOKEN   — Long-term access token de TikTok for Business
      TIKTOK_ADVERTISER_ID  — ID del anunciante en TikTok Ads Manager
    """
    if not TIKTOK_TOKEN or not TIKTOK_ADVERTISER_ID:
        return pd.DataFrame()
    try:
        r = requests.get(
            "https://business-api.tiktok.com/open_api/v1.3/report/integrated/get/",
            headers={"Access-Token": TIKTOK_TOKEN},
            params={
                "advertiser_id": TIKTOK_ADVERTISER_ID,
                "report_type":   "BASIC",
                "dimensions":    json.dumps(["campaign_id", "stat_time_day"]),
                "metrics":       json.dumps([
                    "spend", "real_time_conversions", "clicks", "impressions", "campaign_name"
                ]),
                "start_date": start,
                "end_date":   end,
                "page_size":  1000,
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()

        if data.get("code") != 0:
            st.error(f"TikTok Ads API: {data.get('message', 'Error desconocido')}")
            return pd.DataFrame()

        rows = []
        for item in data.get("data", {}).get("list", []):
            dims    = item.get("dimensions", {})
            metrics = item.get("metrics", {})
            gasto   = float(metrics.get("spend", 0) or 0)
            if gasto == 0:
                continue
            rows.append({
                "fecha":        dims.get("stat_time_day", start)[:10],
                "campaña":      metrics.get("campaign_name", f"TK_{dims.get('campaign_id', '')}"),
                "gasto":        gasto,
                "conversiones": float(metrics.get("real_time_conversions", 0) or 0),
                "clics":        int(metrics.get("clicks", 0) or 0),
                "impresiones":  int(metrics.get("impressions", 0) or 0),
                "plataforma":   "TikTok Ads",
            })

        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["fecha"]   = pd.to_datetime(df["fecha"])
        df["mercado"] = df["campaña"].apply(lambda x: parse_mercado(x, "tiktok"))
        return df

    except Exception as e:
        st.error(f"Error TikTok Ads: {e}")
        return pd.DataFrame()

# ─── Conector LinkedIn Ads vía Google Sheets (CSV manual) ────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def get_linkedin_sheets_data(start: str, end: str) -> pd.DataFrame:
    """
    Lee un Google Sheet publicado como CSV con los datos exportados manualmente
    desde LinkedIn Campaign Manager.

    Columnas esperadas (nombres en español o inglés, mayúsculas/minúsculas indistinto):
      fecha | campaña | gasto | conversiones | clics | impresiones
      date  | campaign| spend | conversions  | clicks| impressions

    La columna 'mercado' es opcional — si no existe se infiere del nombre de campaña.
    Requiere en secrets: LINKEDIN_SHEET_URL (URL de publicación CSV del sheet)
    """
    if not LINKEDIN_SHEET_URL:
        return pd.DataFrame()
    try:
        df = pd.read_csv(LINKEDIN_SHEET_URL)

        # Normalizar nombres de columnas
        df.columns = [c.strip().lower() for c in df.columns]
        col_map = {
            "fecha": "fecha",        "date": "fecha",
            "campaña": "campaña",    "campana": "campaña",
            "campaign": "campaña",   "campaign name": "campaña",
            "nombre campaña": "campaña",
            "gasto": "gasto",        "spend": "gasto",
            "inversión": "gasto",    "inversion": "gasto",   "cost": "gasto",
            "conversiones": "conversiones", "conversions": "conversiones",
            "clics": "clics",        "clicks": "clics",
            "impresiones": "impresiones",   "impressions": "impresiones",
            "mercado": "mercado",
        }
        df = df.rename(columns={c: col_map.get(c, c) for c in df.columns})

        # Verificar columnas mínimas
        for col in ["fecha", "campaña", "gasto"]:
            if col not in df.columns:
                st.error(f"LinkedIn Sheets: falta la columna '{col}'. "
                         "Revisa el formato del Google Sheet.")
                return pd.DataFrame()

        # Rellenar columnas opcionales
        for col, default in [("conversiones", 0), ("clics", 0), ("impresiones", 0)]:
            if col not in df.columns:
                df[col] = default

        # Parsear tipos
        df["fecha"] = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce")
        df = df.dropna(subset=["fecha"])
        df["gasto"]        = pd.to_numeric(df["gasto"],        errors="coerce").fillna(0)
        df["conversiones"] = pd.to_numeric(df["conversiones"], errors="coerce").fillna(0)
        df["clics"]        = pd.to_numeric(df["clics"],        errors="coerce").fillna(0).astype(int)
        df["impresiones"]  = pd.to_numeric(df["impresiones"],  errors="coerce").fillna(0).astype(int)

        # Filtrar por rango de fechas seleccionado
        start_dt = pd.to_datetime(start)
        end_dt   = pd.to_datetime(end)
        df = df[(df["fecha"] >= start_dt) & (df["fecha"] <= end_dt)].copy()

        if df.empty:
            return pd.DataFrame()

        df["plataforma"] = "LinkedIn Ads"

        # Mercado: usar columna si existe, si no inferir del nombre de campaña
        if "mercado" not in df.columns:
            df["mercado"] = df["campaña"].apply(lambda x: parse_mercado(str(x), "linkedin"))

        return df[["fecha", "campaña", "gasto", "conversiones", "clics", "impresiones",
                   "plataforma", "mercado"]]

    except Exception as e:
        st.error(f"Error LinkedIn Sheets: {e}")
        return pd.DataFrame()

# ─── Sidebar — filtros ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Filtros")
    today = date.today()

    periodo = st.radio(
        "Período",
        ["Hoy", "Esta semana", "Este mes", "Últimos 30 días", "Personalizado"],
        index=2,
    )

    if periodo == "Hoy":
        start_d, end_d = today, today
    elif periodo == "Esta semana":
        start_d = today - timedelta(days=today.weekday())
        end_d   = today
    elif periodo == "Este mes":
        start_d = today.replace(day=1)
        end_d   = today
    elif periodo == "Últimos 30 días":
        start_d = today - timedelta(days=30)
        end_d   = today
    else:
        start_d = st.date_input("Desde", today - timedelta(days=30))
        end_d   = st.date_input("Hasta", today)

    st.divider()

    mercado_filtro = st.multiselect(
        "Mercado",
        ["Nacional", "Latam", "Otro"],
        default=["Nacional", "Latam"],
    )
    plataforma_filtro = st.multiselect(
        "Plataforma",
        AVAILABLE_PLATFORMS,
        default=AVAILABLE_PLATFORMS,
    )

    st.divider()
    st.caption(f"📅 {start_d.strftime('%d/%m/%Y')} → {end_d.strftime('%d/%m/%Y')}")

    if st.button("🔄 Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ─── Carga de datos ───────────────────────────────────────────────────────────
st.title("📊 Hofmann · Inversión Publicitaria")

# Caption dinámico con plataformas activas
active_source_labels = []
with st.spinner("Cargando datos..."):
    df_google = get_google_ads_data(str(start_d), str(end_d))
    df_meta   = get_meta_ads_data(str(start_d), str(end_d))

    # LinkedIn: API tiene prioridad; si no hay API, usar Google Sheets
    if linkedin_via_api:
        df_linkedin = get_linkedin_ads_data(str(start_d), str(end_d))
    elif linkedin_via_sheets:
        df_linkedin = get_linkedin_sheets_data(str(start_d), str(end_d))
    else:
        df_linkedin = pd.DataFrame()

    df_tiktok = get_tiktok_ads_data(str(start_d), str(end_d))

if not df_google.empty:
    active_source_labels.append("Google Ads")
if not df_meta.empty:
    active_source_labels.append("Meta Ads")
if not df_linkedin.empty:
    label = "LinkedIn Ads (API)" if linkedin_via_api else "LinkedIn Ads (Sheets)"
    active_source_labels.append(label)
if not df_tiktok.empty:
    active_source_labels.append("TikTok Ads")

st.caption(" + ".join(active_source_labels) + " · Caché actualizado cada hora")

df_all = pd.concat([df_google, df_meta, df_linkedin, df_tiktok], ignore_index=True)

if df_all.empty:
    st.warning("No hay datos para el período seleccionado. Comprueba las credenciales.")
    st.stop()

# Aplicar filtros
mask = pd.Series(True, index=df_all.index)
if mercado_filtro:
    mask &= df_all["mercado"].isin(mercado_filtro)
if plataforma_filtro:
    mask &= df_all["plataforma"].isin(plataforma_filtro)
df = df_all[mask].copy()

if df.empty:
    st.info("No hay datos con los filtros aplicados.")
    st.stop()

# ─── KPIs ─────────────────────────────────────────────────────────────────────
total_g   = df["gasto"].sum()
total_c   = df["conversiones"].sum()
total_cpl = total_g / total_c if total_c > 0 else 0

k1, k2, k3 = st.columns(3)
with k1:
    st.metric("💰 Inversión Total", f"€ {total_g:,.0f}")
with k2:
    st.metric("🎯 Conversiones", f"{total_c:,.0f}")
with k3:
    st.metric("📈 CPL Total", f"€ {total_cpl:,.2f}")

# Sub-KPIs dinámicos por plataforma
platforms_in_df = [p for p in AVAILABLE_PLATFORMS if p in df["plataforma"].values]
if platforms_in_df:
    pcols = st.columns(len(platforms_in_df))
    for i, plat in enumerate(platforms_in_df):
        icon = PLATFORM_ICONS.get(plat, "⚫")
        sub  = df[df["plataforma"] == plat]
        g    = sub["gasto"].sum()
        c    = sub["conversiones"].sum()
        cpl  = g / c if c > 0 else 0
        with pcols[i]:
            with st.container(border=True):
                st.markdown(f"**{icon} {plat}**")
                cc1, cc2, cc3 = st.columns(3)
                cc1.metric("Inversión",    f"€ {g:,.0f}")
                cc2.metric("Conversiones", f"{c:,.0f}")
                cc3.metric("CPL",          f"€ {cpl:,.2f}")

st.divider()

# ─── Preparar datos diarios ───────────────────────────────────────────────────
df_day_total = (
    df.groupby("fecha")
    .agg(gasto=("gasto", "sum"), conversiones=("conversiones", "sum"))
    .reset_index()
    .sort_values("fecha")
)
df_day_total["fecha_str"] = df_day_total["fecha"].dt.strftime("%d/%m")
df_day_total["CPL"] = (
    df_day_total["gasto"] / df_day_total["conversiones"].replace(0, float("nan"))
)

df_day_plat = (
    df.groupby(["fecha", "plataforma"])
    .agg(gasto=("gasto", "sum"), conversiones=("conversiones", "sum"))
    .reset_index()
    .sort_values("fecha")
)
df_day_plat["fecha_str"] = df_day_plat["fecha"].dt.strftime("%d/%m")
df_day_plat["CPL"] = (
    df_day_plat["gasto"] / df_day_plat["conversiones"].replace(0, float("nan"))
)

GRID = "rgba(0,0,0,0.08)"
YAXIS_DEFAULT  = dict(gridcolor=GRID)
YAXIS_EURO     = dict(gridcolor=GRID, tickprefix="€", tickformat=",.0f")
YAXIS_EURO_CPL = dict(gridcolor=GRID, tickprefix="€", tickformat=",.2f")

def base_layout(height=340, yaxis=None):
    layout = dict(
        height=height,
        margin=dict(l=0, r=0, t=30, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    layout["yaxis"] = yaxis if yaxis is not None else YAXIS_DEFAULT
    return layout

# ─── Sección 1: Inversión ─────────────────────────────────────────────────────
st.subheader("💰 Inversión Diaria")
col_a, col_b = st.columns(2)

with col_a:
    st.caption("Total (todas las plataformas)")
    fig1 = px.bar(
        df_day_total, x="fecha_str", y="gasto",
        labels={"fecha_str": "", "gasto": "Inversión"},
        color_discrete_sequence=["#6C63FF"],
        text=df_day_total["gasto"].apply(lambda v: f"€{v:,.0f}"),
    )
    fig1.update_layout(**base_layout(yaxis=YAXIS_EURO))
    fig1.update_traces(textposition="outside", textfont_size=9, marker_color="#6C63FF")
    st.plotly_chart(fig1, use_container_width=True)

with col_b:
    st.caption("Por plataforma")
    fig2 = px.bar(
        df_day_plat, x="fecha_str", y="gasto",
        color="plataforma", color_discrete_map=COLORS, barmode="stack",
        labels={"fecha_str": "", "gasto": "Inversión", "plataforma": ""},
    )
    fig2.update_layout(**base_layout(yaxis=YAXIS_EURO))
    fig2.update_traces(textposition="inside", textfont_size=9,
                       texttemplate="€%{y:,.0f}")
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ─── Sección 2: Conversiones ──────────────────────────────────────────────────
st.subheader("🎯 Conversiones Diarias")
col_c, col_d = st.columns(2)

with col_c:
    st.caption("Total (todas las plataformas)")
    fig3 = px.bar(
        df_day_total, x="fecha_str", y="conversiones",
        labels={"fecha_str": "", "conversiones": "Conversiones"},
        text_auto=".0f",
        color_discrete_sequence=["#6C63FF"],
    )
    fig3.update_layout(**base_layout())
    fig3.update_traces(textposition="outside", textfont_size=9, marker_color="#6C63FF")
    st.plotly_chart(fig3, use_container_width=True)

with col_d:
    st.caption("Por plataforma")
    fig4 = px.bar(
        df_day_plat, x="fecha_str", y="conversiones",
        color="plataforma", color_discrete_map=COLORS, barmode="stack",
        labels={"fecha_str": "", "conversiones": "Conversiones", "plataforma": ""},
        text_auto=".0f",
    )
    fig4.update_layout(**base_layout())
    fig4.update_traces(textposition="inside", textfont_size=9)
    st.plotly_chart(fig4, use_container_width=True)

st.divider()

# ─── Sección 3: CPL diario ────────────────────────────────────────────────────
st.subheader("📈 CPL Bruto Diario")
col_e, col_f = st.columns(2)

with col_e:
    st.caption("Total (todas las plataformas)")
    df_cpl_t = df_day_total.dropna(subset=["CPL"])
    fig5 = go.Figure()
    fig5.add_trace(go.Scatter(
        x=df_cpl_t["fecha_str"], y=df_cpl_t["CPL"],
        mode="lines+markers+text",
        line=dict(color="#6C63FF", width=2),
        marker=dict(size=7),
        text=df_cpl_t["CPL"].apply(lambda v: f"€{v:,.2f}"),
        textposition="top center",
        textfont=dict(size=10),
        name="CPL Total",
    ))
    fig5.update_layout(**base_layout(yaxis=YAXIS_EURO_CPL), showlegend=False)
    st.plotly_chart(fig5, use_container_width=True)

with col_f:
    st.caption("Por plataforma")
    df_cpl_p = df_day_plat.dropna(subset=["CPL"])
    fig6 = go.Figure()
    for plat in df_cpl_p["plataforma"].unique():
        color = COLORS.get(plat, "#888888")
        sub   = df_cpl_p[df_cpl_p["plataforma"] == plat]
        if sub.empty:
            continue
        fig6.add_trace(go.Scatter(
            x=sub["fecha_str"], y=sub["CPL"],
            mode="lines+markers+text",
            line=dict(color=color, width=2),
            marker=dict(size=6),
            text=sub["CPL"].apply(lambda v: f"€{v:,.2f}"),
            textposition="top center",
            textfont=dict(size=9),
            name=plat,
        ))
    fig6.update_layout(**base_layout(yaxis=YAXIS_EURO_CPL))
    st.plotly_chart(fig6, use_container_width=True)

st.divider()

# ─── Tabla de campañas ────────────────────────────────────────────────────────
st.subheader("📋 Rendimiento por Campaña")

df_camp = (
    df.groupby(["plataforma", "mercado", "campaña"])
    .agg(
        gasto=("gasto", "sum"),
        conversiones=("conversiones", "sum"),
        clics=("clics", "sum"),
        impresiones=("impresiones", "sum"),
    )
    .reset_index()
)
df_camp["CPL (€)"] = (
    df_camp["gasto"] / df_camp["conversiones"].replace(0, float("nan"))
).round(2)
df_camp["CPC (€)"] = (
    df_camp["gasto"] / df_camp["clics"].replace(0, float("nan"))
).round(2)
df_camp = df_camp.sort_values("gasto", ascending=False)
df_camp["gasto"]        = df_camp["gasto"].round(2)
df_camp["conversiones"] = df_camp["conversiones"].round(1)

st.dataframe(
    df_camp.rename(columns={
        "plataforma":   "Plataforma",
        "mercado":      "Mercado",
        "campaña":      "Campaña",
        "gasto":        "Inversión (€)",
        "conversiones": "Conversiones",
        "clics":        "Clics",
    })[["Plataforma", "Mercado", "Campaña", "Inversión (€)", "Conversiones", "Clics", "CPL (€)"]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "Inversión (€)": st.column_config.NumberColumn(format="€ %.2f"),
        "CPL (€)":       st.column_config.NumberColumn(format="€ %.2f"),
    },
)

st.divider()

# ─── Gráfico: CPL por campaña ─────────────────────────────────────────────────
st.subheader("📈 CPL por Campaña (campañas con conversiones)")

df_cpl = df_camp[df_camp["conversiones"] > 0].copy()
df_cpl["CPL"] = df_cpl["gasto"] / df_cpl["conversiones"]
df_cpl = df_cpl.sort_values("CPL", ascending=True).head(25)

fig_cpl = px.bar(
    df_cpl,
    x="CPL",
    y="campaña",
    color="plataforma",
    color_discrete_map=COLORS,
    orientation="h",
    labels={"CPL": "CPL (€)", "campaña": "", "plataforma": ""},
    text=df_cpl["CPL"].apply(lambda x: f"€{x:.2f}"),
)
fig_cpl.update_layout(
    height=max(320, len(df_cpl) * 30),
    margin=dict(l=0, r=60, t=20, b=0),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    yaxis=dict(tickfont=dict(size=11), gridcolor="rgba(0,0,0,0)"),
    xaxis=dict(gridcolor="rgba(0,0,0,0.08)", title="CPL (€)", tickprefix="€", tickformat=",.2f"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
fig_cpl.update_traces(textposition="outside", textfont_size=11)
st.plotly_chart(fig_cpl, use_container_width=True)
