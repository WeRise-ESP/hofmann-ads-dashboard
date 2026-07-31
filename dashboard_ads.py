"""
Dashboard de Inversión Publicitaria + Leads CRM — Hofmann
Fuentes: Google Ads + Meta Ads + LinkedIn Ads + TikTok Ads + HubSpot CRM
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import json
import os
import re
from io import StringIO
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
LINKEDIN_VERSION    = _s("LINKEDIN_API_VERSION", "202503")  # versión activa del API

# TikTok Ads (opcional — se activa cuando haya credenciales)
TIKTOK_TOKEN         = _s("TIKTOK_ACCESS_TOKEN")
TIKTOK_ADVERTISER_ID = _s("TIKTOK_ADVERTISER_ID")
TIKTOK_APP_ID        = _s("TIKTOK_APP_ID",     "7649605007397879824")
TIKTOK_APP_SECRET    = _s("TIKTOK_APP_SECRET",  "4444ab6a8662ad49835f30c57272c40db4e4ac95")
TIKTOK_AUTH_URL = (
    "https://business-api.tiktok.com/portal/auth"
    f"?app_id={TIKTOK_APP_ID}&state=hofmann"
    "&redirect_uri=https%3A%2F%2Fhofmann-ads-dashboard.streamlit.app"
)

# LinkedIn Ads — fuente alternativa vía Google Sheets (CSV manual desde Campaign Manager)
# Formato del sheet: fecha | campaña | gasto | conversiones | clics | impresiones
LINKEDIN_SHEET_URL = _s("LINKEDIN_SHEET_URL")

# HubSpot CRM
HUBSPOT_TOKEN = _s("HUBSPOT_TOKEN")

# ─── TikTok OAuth callback (captura auth_code al volver del flujo OAuth) ──────
_qp = st.query_params
if "auth_code" in _qp and _qp.get("state") == "hofmann":
    with st.spinner("Renovando token de TikTok..."):
        _resp = requests.post(
            "https://business-api.tiktok.com/open_api/v1.3/oauth2/access_token/",
            json={"app_id": TIKTOK_APP_ID, "secret": TIKTOK_APP_SECRET,
                  "auth_code": _qp["auth_code"]},
            timeout=15,
        )
        _d = _resp.json()
        if _d.get("code") == 0:
            st.session_state["tt_token"] = _d["data"]["access_token"]
            st.session_state.pop("tt_expired", None)
            st.query_params.clear()
            st.rerun()
        else:
            st.error(f"Error renovando token TikTok: {_d.get('message')}")
            st.query_params.clear()

# ─── Configuración de plataformas ─────────────────────────────────────────────
COLORS = {
    "Google Ads":   "#FF6D00",
    "Meta Ads":     "#1877F2",
    "LinkedIn Ads": "#00B050",
    "TikTok Ads":   "#010101",
}

PLATFORM_ICONS = {
    "Google Ads":   "🟠",
    "Meta Ads":     "🔵",
    "LinkedIn Ads": "🔷",
    "TikTok Ads":   "🩷",
}

# Token efectivo de TikTok: sesión tiene prioridad sobre secrets
TIKTOK_EFFECTIVE_TOKEN = st.session_state.get("tt_token", TIKTOK_TOKEN)

# Plataformas activas según credenciales disponibles
AVAILABLE_PLATFORMS = ["Google Ads", "Meta Ads"]
linkedin_via_api    = bool(LINKEDIN_TOKEN and LINKEDIN_ACCOUNT_ID)
linkedin_via_sheets = bool(LINKEDIN_SHEET_URL)
if linkedin_via_api or linkedin_via_sheets:
    AVAILABLE_PLATFORMS.append("LinkedIn Ads")
if TIKTOK_EFFECTIVE_TOKEN and TIKTOK_ADVERTISER_ID:
    AVAILABLE_PLATFORMS.append("TikTok Ads")

# ─── Helpers de métricas ──────────────────────────────────────────────────────
def calc_cpl(gasto: pd.Series, conversiones: pd.Series) -> pd.Series:
    """CPL real si hay conversiones; si no → gasto completo (inversión sin resultado)."""
    return gasto.where(conversiones == 0, gasto / conversiones.replace(0, 1))

# ─── Clasificador de mercado (Ads) ────────────────────────────────────────────
# Regla Hofmann → Nacional si el nombre contiene alguno de estos tokens:
#   NAC / NACIONAL   (NAC_, _NAC, - NAC…)
#   CAT              (Catalunya)
#   ES               (delimitado: "- ES", "_ES"…)
# Cualquier otra cosa (LATAM, etc.) → Latam.
# El look-behind (?<![A-Z]) evita falsos positivos como "INTERNACIONAL".
_NACIONAL_RE = re.compile(r"(?<![A-Z])NAC|(?<![A-Z])CAT|(?<![A-Z])ESP?(?![A-Z])")

# Excepciones manuales: campañas cuyo nombre engaña al clasificador.
# Clave = substring (mayúsculas) del nombre de campaña · Valor = mercado forzado.
_MERCADO_OVERRIDES = {
    # LinkedIn: en el sheet lleva prefijo NAC_ por error, pero es de Latam.
    "ONLINE_CONVERS_DIRECCION": "Latam",
}

def parse_mercado(name: str, platform: str = "") -> str:
    """Nacional si el nombre trae un token nacional (NAC/CAT/ES); si no → Latam.

    Se puede pasar más de un nombre separado por espacios (p. ej. campaña + grupo
    de anuncios en TikTok) para clasificar por el grupo cuando la campaña no trae
    la nomenclatura. Las excepciones de _MERCADO_OVERRIDES tienen prioridad.
    """
    n = (name or "").upper()
    for key, merc in _MERCADO_OVERRIDES.items():
        if key in n:
            return merc
    return "Nacional" if _NACIONAL_RE.search(n) else "Latam"

# ─── Clasificador de modalidad (Online / Presencial) ─────────────────────────
# Regla Hofmann: si el nombre contiene "ONLINE" → Online; si no → Presencial.
# Excepciones: campañas cuyo nombre no lleva "online" pero sí lo son (p. ej.
# LinkedIn "Direc_Rest_Convers_Latam" = la maestría online de dirección).
_MODALIDAD_OVERRIDES = {
    "DIREC_REST_CONVERS": "Online",
}

def parse_modalidad(name: str) -> str:
    n = (name or "").upper()
    for key, moda in _MODALIDAD_OVERRIDES.items():
        if key in n:
            return moda
    return "Online" if "ONLINE" in n else "Presencial"

# ─── Clasificadores HubSpot ───────────────────────────────────────────────────
_PAIS_MAP = {
    "ES": "España", "SPAIN": "España", "ESPAÑA": "España",
    "CO": "Colombia", "COLOMBIA": "Colombia",
    "MX": "México", "MEXICO": "México", "MÉXICO": "México",
    "AR": "Argentina", "ARGENTINA": "Argentina",
    "PE": "Perú", "PERU": "Perú", "PERÚ": "Perú",
    "CL": "Chile", "CHILE": "Chile",
    "EC": "Ecuador", "ECUADOR": "Ecuador",
    "VE": "Venezuela", "VENEZUELA": "Venezuela",
    "BO": "Bolivia", "BOLIVIA": "Bolivia",
    "PY": "Paraguay", "PARAGUAY": "Paraguay",
    "UY": "Uruguay", "URUGUAY": "Uruguay",
    "PA": "Panamá", "PANAMA": "Panamá", "PANAMÁ": "Panamá",
    "CR": "Costa Rica", "COSTA RICA": "Costa Rica",
    "GT": "Guatemala", "GUATEMALA": "Guatemala",
    "HN": "Honduras", "HONDURAS": "Honduras",
    "SV": "El Salvador", "EL SALVADOR": "El Salvador",
    "DO": "Rep. Dominicana", "DOMINICAN REPUBLIC": "Rep. Dominicana",
    "US": "USA", "UNITED STATES": "USA",
    "GB": "Reino Unido", "UNITED KINGDOM": "Reino Unido",
    "FR": "Francia", "FRANCE": "Francia",
    "DE": "Alemania", "GERMANY": "Alemania",
    "IT": "Italia", "ITALY": "Italia",
}

def normalizar_pais(raw: str) -> str:
    k = (raw or "").strip().upper()
    return _PAIS_MAP.get(k, raw.strip().title() if raw else "Desconocido") or "Desconocido"


def parse_plataforma_hs(source: str, data1: str) -> str:
    s  = (source or "").upper().strip()
    d1 = (data1 or "").lower().strip()
    if s == "PAID_SEARCH":
        return "Google Ads"
    if s == "PAID_SOCIAL":
        if any(x in d1 for x in ["facebook", "instagram", "meta", "fb"]):
            return "Meta Ads"
        if "linkedin" in d1:
            return "LinkedIn Ads"
        if "tiktok" in d1:
            return "TikTok Ads"
        return "Social Pagado"
    if s == "ORGANIC_SEARCH":
        return "SEO Orgánico"
    if s == "EMAIL_MARKETING":
        return "Email"
    if s == "DIRECT_TRAFFIC":
        return "Directo"
    if s in ("SOCIAL_MEDIA", "SOCIAL"):
        return "Social Orgánico"
    if s == "REFERRALS":
        return "Referido"
    if s == "OFFLINE":
        return "Offline"
    return s or "Desconocido"


def parse_programa_hs(curso: str, modalidad: str, formulario: str) -> str:
    if curso and curso.strip():
        return curso.strip()
    if modalidad and modalidad.strip():
        return modalidad.strip()
    form = (formulario or "").lower()
    if "pastel" in form:
        return "Pastelería"
    if "cocin" in form:
        return "Cocina"
    if "máster" in form or "master" in form:
        return "Máster"
    if "diploma" in form:
        return "Diploma"
    if "superior" in form:
        return "Curso Superior"
    return "Sin programa"

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
            "LinkedIn-Version": LINKEDIN_VERSION,
            "X-Restli-Protocol-Version": "2.0.0",
        }

        # 1. Obtener nombres de campañas (endpoint bajo la cuenta, Rest.li 2.0)
        camp_url = (
            f"https://api.linkedin.com/rest/adAccounts/{LINKEDIN_ACCOUNT_ID}/adCampaigns"
            "?q=search&search=(status:(values:List(ACTIVE,PAUSED,DRAFT,COMPLETED)))"
            "&fields=id,name&count=200"
        )
        camp_resp = requests.get(camp_url, headers=headers, timeout=30)
        campaign_names = {}
        if camp_resp.status_code == 200:
            for el in camp_resp.json().get("elements", []):
                campaign_names[str(el["id"])] = el.get("name", f"LI_{el['id']}")

        # 2. Obtener métricas diarias por campaña.
        # LinkedIn (Rest.li 2.0) exige comas y List(...) sin codificar, por eso
        # construimos la URL a mano en vez de usar params (requests codifica las comas).
        sy, sm, sd = start.split("-")
        ey, em, ed = end.split("-")
        acct = requests.utils.quote(
            f"urn:li:sponsoredAccount:{LINKEDIN_ACCOUNT_ID}", safe=""
        )
        analytics_url = (
            "https://api.linkedin.com/rest/adAnalytics?q=analytics&pivot=CAMPAIGN"
            "&timeGranularity=DAILY"
            f"&accounts=List({acct})"
            f"&dateRange=(start:(year:{sy},month:{int(sm)},day:{int(sd)}),"
            f"end:(year:{ey},month:{int(em)},day:{int(ed)}))"
            "&fields=costInLocalCurrency,externalWebsiteConversions,oneClickLeads,"
            "clicks,impressions,pivotValues,dateRange&count=500"
        )
        r = requests.get(analytics_url, headers=headers, timeout=30)
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
                # LinkedIn mide según el tipo de campaña: unas en "Conversiones"
                # (externalWebsiteConversions) y otras en "Posibles contactos"
                # (oneClickLeads, formularios de contacto). Sumamos ambas.
                "conversiones": (float(item.get("externalWebsiteConversions", 0) or 0)
                                 + float(item.get("oneClickLeads", 0) or 0)),
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
def get_tiktok_ads_data(start: str, end: str, token: str) -> pd.DataFrame:
    """
    Requiere en secrets:
      TIKTOK_ACCESS_TOKEN   — Access token de TikTok for Business (24h)
      TIKTOK_ADVERTISER_ID  — ID del anunciante en TikTok Ads Manager
    El token se renueva automáticamente desde el dashboard via OAuth.
    """
    if not token or not TIKTOK_ADVERTISER_ID:
        return pd.DataFrame()
    try:
        # Nivel grupo de anuncios: así podemos clasificar el mercado por el nombre
        # del grupo cuando la campaña no trae la nomenclatura NAC/LAT.
        r = requests.get(
            "https://business-api.tiktok.com/open_api/v1.3/report/integrated/get/",
            headers={"Access-Token": token},
            params={
                "advertiser_id": TIKTOK_ADVERTISER_ID,
                "report_type":   "BASIC",
                "data_level":    "AUCTION_ADGROUP",
                "dimensions":    json.dumps(["adgroup_id", "stat_time_day"]),
                "metrics":       json.dumps([
                    "spend", "conversion", "clicks", "impressions",
                    "campaign_name", "adgroup_name",
                ]),
                "start_date": start,
                "end_date":   end,
                "page_size":  1000,
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()

        if data.get("code") in (40001, 40002, 40004):
            st.session_state["tt_expired"] = True
            return pd.DataFrame()
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
            camp_name = metrics.get("campaign_name", f"TK_{dims.get('adgroup_id', '')}")
            adg_name  = metrics.get("adgroup_name", "")
            rows.append({
                "fecha":        dims.get("stat_time_day", start)[:10],
                "campaña":      camp_name,
                "gasto":        gasto,
                "conversiones": float(metrics.get("conversion", 0) or 0),
                "clics":        int(metrics.get("clicks", 0) or 0),
                "impresiones":  int(metrics.get("impressions", 0) or 0),
                "plataforma":   "TikTok Ads",
                # mercado por campaña; si la campaña no trae NAC, se mira el grupo
                "mercado":      parse_mercado(f"{camp_name} {adg_name}"),
            })

        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["fecha"] = pd.to_datetime(df["fecha"])
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
        r = requests.get(LINKEDIN_SHEET_URL, timeout=20)
        r.raise_for_status()
        r.encoding = "utf-8"                          # forzar UTF-8 (ñ, acentos)
        content = r.content.decode("utf-8-sig")       # utf-8-sig elimina BOM si existe
        df = pd.read_csv(StringIO(content))

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
        # Función que acepta tanto "26,71" (europeo) como "26.71" (anglosajón)
        def to_num(series):
            return (
                series.astype(str)
                      .str.strip()
                      .str.replace(",", ".", regex=False)
                      .pipe(pd.to_numeric, errors="coerce")
                      .fillna(0)
            )

        # Intentar formato ISO (YYYY-MM-DD) primero; si falla, probar formato europeo (DD/MM/YYYY)
        df["fecha"] = pd.to_datetime(df["fecha"], format="%Y-%m-%d", errors="coerce")
        mask_failed = df["fecha"].isna()
        if mask_failed.any():
            df.loc[mask_failed, "fecha"] = pd.to_datetime(
                df.loc[mask_failed, "fecha"], dayfirst=True, errors="coerce"
            )
        df = df.dropna(subset=["fecha"])
        df["gasto"]        = to_num(df["gasto"])
        df["conversiones"] = to_num(df["conversiones"])
        df["clics"]        = to_num(df["clics"]).astype(int)
        df["impresiones"]  = to_num(df["impresiones"]).astype(int)

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

# ─── Conector HubSpot CRM — Leads ─────────────────────────────────────────────
_CAT_EVENTOS = {"Webinar", "Open Day", "Open Day Digital", "Sesión Informativa Online"}
_KW_EVENTOS  = ("webinar", "open day", "openday", "puertas abiertas",
                 "sesión informativa", "sesion informativa")

@st.cache_data(ttl=1800, show_spinner=False)
def get_hubspot_leads(start: str, end: str, token: str, excluir_eventos: bool) -> pd.DataFrame:
    if not token:
        return pd.DataFrame()
    try:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        fi_ts = int(pd.Timestamp(start).timestamp() * 1000)
        ff_ts = int(pd.Timestamp(end + " 23:59:59").timestamp() * 1000)

        props = [
            "email", "firstname", "lastname", "createdate",
            "pais_de_residencia", "ip_country", "country",
            "categoria_lead", "hs_object_source", "first_conversion_event_name",
            "hs_analytics_source", "hs_analytics_source_data_1", "hs_analytics_source_data_2",
            "hs_latest_source", "hs_latest_source_data_1", "hs_latest_source_data_2",
            "curso", "modalidad_curso",
        ]

        rows, after = [], None
        while True:
            payload = {
                "filterGroups": [{"filters": [
                    {"propertyName": "createdate", "operator": "GTE", "value": str(fi_ts)},
                    {"propertyName": "createdate", "operator": "LTE", "value": str(ff_ts)},
                ]}],
                "properties": props,
                "limit": 100,
            }
            if after:
                payload["after"] = after
            r = requests.post(
                "https://api.hubapi.com/crm/v3/objects/contacts/search",
                headers=headers, json=payload, timeout=30,
            )
            r.raise_for_status()
            data = r.json()

            for c in data.get("results", []):
                p = c["properties"]
                cat      = (p.get("categoria_lead") or "").strip()
                form_raw = (p.get("first_conversion_event_name") or "").lower()

                if excluir_eventos:
                    if cat in _CAT_EVENTOS:
                        continue
                    if any(k in form_raw for k in _KW_EVENTOS):
                        continue

                pais_raw = (
                    p.get("pais_de_residencia") or
                    p.get("ip_country") or
                    p.get("country") or ""
                )
                # UTM source → plataforma; UTM campaign from data_2 or data_1
                latest_src = p.get("hs_latest_source") or p.get("hs_analytics_source") or ""
                latest_d1  = p.get("hs_latest_source_data_1") or p.get("hs_analytics_source_data_1") or ""
                latest_d2  = p.get("hs_latest_source_data_2") or p.get("hs_analytics_source_data_2") or ""

                rows.append({
                    "fecha":       (p.get("createdate") or "")[:10],
                    "pais":        normalizar_pais(pais_raw),
                    "categoria":   cat or "Sin categoría",
                    "plataforma_hs": parse_plataforma_hs(latest_src, latest_d1),
                    "campaña_hs":  latest_d2 or latest_d1 or "Sin campaña",
                    "programa":    parse_programa_hs(
                                       p.get("curso") or "",
                                       p.get("modalidad_curso") or "",
                                       form_raw,
                                   ),
                    "formulario":  p.get("first_conversion_event_name") or "",
                })

            pg = data.get("paging", {})
            if not pg or "next" not in pg:
                break
            after = pg["next"]["after"]

        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        return df

    except Exception as e:
        st.error(f"Error HubSpot CRM: {e}")
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
        ["Nacional", "Latam"],
        default=["Nacional", "Latam"],
    )
    modalidad_filtro = st.multiselect(
        "Modalidad",
        ["Online", "Presencial"],
        default=["Online", "Presencial"],
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

    # Botón renovación TikTok — aparece cuando el token caduca
    if TIKTOK_ADVERTISER_ID and st.session_state.get("tt_expired"):
        st.divider()
        st.warning("⚠️ Token TikTok caducado")
        st.link_button("🔄 Renovar acceso TikTok", TIKTOK_AUTH_URL,
                       use_container_width=True)

# ─── Carga de datos (Ads) ─────────────────────────────────────────────────────
st.title("📊 Hofmann · Ads & CRM Dashboard")

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

    df_tiktok = get_tiktok_ads_data(str(start_d), str(end_d), TIKTOK_EFFECTIVE_TOKEN)

if not df_google.empty:
    active_source_labels.append("Google Ads")
if not df_meta.empty:
    active_source_labels.append("Meta Ads")
if not df_linkedin.empty:
    label = "LinkedIn Ads (API)" if linkedin_via_api else "LinkedIn Ads (Sheets)"
    active_source_labels.append(label)
if not df_tiktok.empty:
    active_source_labels.append("TikTok Ads")

st.caption((" + ".join(active_source_labels) if active_source_labels else "Sin datos de Ads") +
           " · Caché actualizado cada hora")

df_all = pd.concat([df_google, df_meta, df_linkedin, df_tiktok], ignore_index=True)

# Modalidad (Online / Presencial) inferida del nombre de campaña
if not df_all.empty:
    df_all["modalidad"] = df_all["campaña"].apply(parse_modalidad)

# Aplicar filtros de sidebar
if not df_all.empty:
    mask = pd.Series(True, index=df_all.index)
    if mercado_filtro:
        mask &= df_all["mercado"].isin(mercado_filtro)
    if modalidad_filtro:
        mask &= df_all["modalidad"].isin(modalidad_filtro)
    if plataforma_filtro:
        mask &= df_all["plataforma"].isin(plataforma_filtro)
    df = df_all[mask].copy()
else:
    df = pd.DataFrame()

# ─── Tabs principales ─────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📊 Inversión Publicitaria", "👥 Leads por Campaña"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Inversión Publicitaria
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    if df_all.empty:
        st.warning("No hay datos para el período seleccionado. Comprueba las credenciales.")
        st.stop()

    if df.empty:
        st.info("No hay datos con los filtros aplicados.")
        st.stop()

    # ─── KPIs ─────────────────────────────────────────────────────────────────
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

    # ─── General por mercado (todas las plataformas) ──────────────────────────
    mcols = st.columns(2)
    for mc, (merc, emoji) in zip(mcols, [("Nacional", "🇪🇸"), ("Latam", "🌎")]):
        subm = df[df["mercado"] == merc]
        gm   = subm["gasto"].sum()
        cm   = subm["conversiones"].sum()
        cplm = gm / cm if cm > 0 else 0
        with mc:
            with st.container(border=True):
                st.markdown(f"**{emoji} {merc}** · General")
                mm1, mm2, mm3 = st.columns(3)
                mm1.metric("Inversión",    f"€ {gm:,.0f}")
                mm2.metric("Conversiones", f"{cm:,.0f}")
                mm3.metric("CPL",          f"€ {cplm:,.2f}")

    # ─── General por modalidad (todas las plataformas) ────────────────────────
    ocols = st.columns(2)
    for oc, (moda, emoji) in zip(ocols, [("Online", "💻"), ("Presencial", "🏫")]):
        subo = df[df["modalidad"] == moda]
        gmod = subo["gasto"].sum()
        co   = subo["conversiones"].sum()
        cplo = gmod / co if co > 0 else 0
        with oc:
            with st.container(border=True):
                st.markdown(f"**{emoji} {moda}** · General")
                oo1, oo2, oo3 = st.columns(3)
                oo1.metric("Inversión",    f"€ {gmod:,.0f}")
                oo2.metric("Conversiones", f"{co:,.0f}")
                oo3.metric("CPL",          f"€ {cplo:,.2f}")

    st.divider()

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
                    # Desglose por mercado (Nacional / Latam)
                    for merc, emoji in [("Nacional", "🇪🇸"), ("Latam", "🌎")]:
                        sm = sub[sub["mercado"] == merc]
                        gm = sm["gasto"].sum()
                        cm = sm["conversiones"].sum()
                        st.caption(
                            f"{emoji} **{merc}** · € {gm:,.0f} · "
                            f"{cm:,.0f} conv"
                        )

    st.divider()

    # ─── Preparar datos diarios ───────────────────────────────────────────────
    df_day_total = (
        df.groupby("fecha")
        .agg(gasto=("gasto", "sum"), conversiones=("conversiones", "sum"))
        .reset_index()
        .sort_values("fecha")
    )
    df_day_total["fecha_str"] = df_day_total["fecha"].dt.strftime("%d/%m")
    df_day_total["CPL"] = calc_cpl(df_day_total["gasto"], df_day_total["conversiones"])

    df_day_plat = (
        df.groupby(["fecha", "plataforma"])
        .agg(gasto=("gasto", "sum"), conversiones=("conversiones", "sum"))
        .reset_index()
        .sort_values("fecha")
    )
    df_day_plat["fecha_str"] = df_day_plat["fecha"].dt.strftime("%d/%m")
    df_day_plat["CPL"] = calc_cpl(df_day_plat["gasto"], df_day_plat["conversiones"])

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

    # ─── Sección 1: Inversión ─────────────────────────────────────────────────
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

    # ─── Sección 2: Conversiones ──────────────────────────────────────────────
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

    # ─── Sección 3: CPL diario ────────────────────────────────────────────────
    st.subheader("📈 CPL Bruto Diario")
    col_e, col_f = st.columns(2)

    with col_e:
        st.caption("Total (todas las plataformas)")
        df_cpl_t = df_day_total
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
        df_cpl_p = df_day_plat
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

    # ─── Tabla de campañas ────────────────────────────────────────────────────
    st.subheader("📋 Rendimiento por Campaña")

    df_camp = (
        df.groupby(["plataforma", "mercado", "modalidad", "campaña"])
        .agg(
            gasto=("gasto", "sum"),
            conversiones=("conversiones", "sum"),
            clics=("clics", "sum"),
            impresiones=("impresiones", "sum"),
        )
        .reset_index()
    )
    df_camp["CPL (€)"] = calc_cpl(df_camp["gasto"], df_camp["conversiones"]).round(2)
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
            "modalidad":    "Modalidad",
            "campaña":      "Campaña",
            "gasto":        "Inversión (€)",
            "conversiones": "Conversiones",
            "clics":        "Clics",
        })[["Plataforma", "Mercado", "Modalidad", "Campaña", "Inversión (€)", "Conversiones", "Clics", "CPL (€)"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Inversión (€)": st.column_config.NumberColumn(format="€ %.2f"),
            "CPL (€)":       st.column_config.NumberColumn(format="€ %.2f"),
        },
    )

    st.divider()

    # ─── Gráfico: CPL por campaña ─────────────────────────────────────────────
    st.subheader("📈 CPL por Campaña")

    df_cpl = df_camp.copy()
    df_cpl["CPL"] = calc_cpl(df_cpl["gasto"], df_cpl["conversiones"])
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

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Leads por Campaña (HubSpot CRM)
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("👥 Leads por Plataforma, País y Programa")

    if not HUBSPOT_TOKEN:
        st.warning("No hay token de HubSpot configurado. Añade **HUBSPOT_TOKEN** en los secrets.")
        st.stop()

    # ─── Filtros inline ───────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4 = st.columns([1, 1, 1, 1])
    with fc1:
        excluir_eventos = st.checkbox("Excluir Webinar / Open Day", value=True)

    with st.spinner("Cargando leads de HubSpot..."):
        df_hs = get_hubspot_leads(str(start_d), str(end_d), HUBSPOT_TOKEN, excluir_eventos)

    if df_hs.empty:
        st.info("No hay leads en el período y filtros seleccionados.")
        st.stop()

    plat_opts = sorted(df_hs["plataforma_hs"].unique().tolist())
    pais_opts = sorted(df_hs["pais"].unique().tolist())
    prog_opts = sorted(df_hs["programa"].unique().tolist())

    with fc2:
        filtro_plat_hs = st.multiselect("Plataforma", plat_opts, default=plat_opts)
    with fc3:
        filtro_pais_hs = st.multiselect("País", pais_opts, default=pais_opts)
    with fc4:
        filtro_prog_hs = st.multiselect("Programa", prog_opts, default=prog_opts)

    # Aplicar filtros
    df_hsf = df_hs.copy()
    if filtro_plat_hs:
        df_hsf = df_hsf[df_hsf["plataforma_hs"].isin(filtro_plat_hs)]
    if filtro_pais_hs:
        df_hsf = df_hsf[df_hsf["pais"].isin(filtro_pais_hs)]
    if filtro_prog_hs:
        df_hsf = df_hsf[df_hsf["programa"].isin(filtro_prog_hs)]

    if df_hsf.empty:
        st.info("No hay leads con los filtros aplicados.")
        st.stop()

    # ─── KPIs ─────────────────────────────────────────────────────────────────
    _PLATS_PAGO = {"Google Ads", "Meta Ads", "LinkedIn Ads", "TikTok Ads", "Social Pagado"}
    total_leads   = len(df_hsf)
    leads_pagados = len(df_hsf[df_hsf["plataforma_hs"].isin(_PLATS_PAGO)])
    paises_n      = df_hsf["pais"].nunique()
    pct_pagados   = leads_pagados / total_leads * 100 if total_leads > 0 else 0

    kh1, kh2, kh3, kh4 = st.columns(4)
    kh1.metric("👥 Total Leads",    f"{total_leads:,}")
    kh2.metric("💰 Leads Pagados",  f"{leads_pagados:,}")
    kh3.metric("📍 Países",         f"{paises_n}")
    kh4.metric("📊 % Pagados",      f"{pct_pagados:.0f}%")

    # Sub-KPIs por todas las fuentes presentes (ordenadas: pago primero, luego orgánico)
    _ORDEN_FUENTES = [
        "Google Ads", "Meta Ads", "LinkedIn Ads", "TikTok Ads", "Social Pagado",
        "SEO Orgánico", "Social Orgánico", "Email", "Directo", "Referido", "Offline", "Desconocido",
    ]
    _ICONS_HS = {
        **PLATFORM_ICONS,
        "SEO Orgánico":    "🟢",
        "Social Orgánico": "🟣",
        "Email":           "📧",
        "Directo":         "🔗",
        "Referido":        "↩️",
        "Offline":         "🏢",
        "Social Pagado":   "💸",
        "Desconocido":     "❓",
    }
    fuentes_presentes = [f for f in _ORDEN_FUENTES if f in df_hsf["plataforma_hs"].values]
    # añadir cualquier fuente no prevista en el orden
    fuentes_presentes += [f for f in df_hsf["plataforma_hs"].unique() if f not in fuentes_presentes]

    if fuentes_presentes:
        MAX_COLS = 5
        chunks = [fuentes_presentes[i:i+MAX_COLS] for i in range(0, len(fuentes_presentes), MAX_COLS)]
        for chunk in chunks:
            pcols_hs = st.columns(len(chunk))
            for i, fuente in enumerate(chunk):
                icon = _ICONS_HS.get(fuente, "⚫")
                n    = len(df_hsf[df_hsf["plataforma_hs"] == fuente])
                with pcols_hs[i]:
                    with st.container(border=True):
                        st.markdown(f"**{icon} {fuente}**")
                        st.metric("Leads", f"{n:,}")

    st.divider()

    # ─── Leads diarios por plataforma ─────────────────────────────────────────
    st.subheader("📅 Leads Diarios por Plataforma")

    COLORS_HS = {
        **COLORS,
        "SEO Orgánico":    "#34A853",
        "Email":           "#EA4335",
        "Directo":         "#FBBC04",
        "Social Orgánico": "#9C27B0",
        "Social Pagado":   "#607D8B",
        "Referido":        "#00BCD4",
        "Offline":         "#795548",
        "Desconocido":     "#9E9E9E",
    }

    df_hs_day = (
        df_hsf.groupby(["fecha", "plataforma_hs"])
        .size().reset_index(name="leads")
        .sort_values("fecha")
    )
    df_hs_day["fecha_str"] = pd.to_datetime(df_hs_day["fecha"]).dt.strftime("%d/%m")

    fig_day_hs = px.bar(
        df_hs_day, x="fecha_str", y="leads",
        color="plataforma_hs", color_discrete_map=COLORS_HS, barmode="stack",
        labels={"fecha_str": "", "leads": "Leads", "plataforma_hs": ""},
        text_auto=".0f",
    )
    fig_day_hs.update_layout(
        height=340,
        margin=dict(l=0, r=0, t=30, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(gridcolor="rgba(0,0,0,0.08)"),
    )
    fig_day_hs.update_traces(textposition="inside", textfont_size=9)
    st.plotly_chart(fig_day_hs, use_container_width=True)

    st.divider()

    # ─── País y Programa ──────────────────────────────────────────────────────
    col_p1, col_p2 = st.columns(2)

    with col_p1:
        st.subheader("🌍 Leads por País")
        df_pais = (
            df_hsf.groupby("pais").size()
            .reset_index(name="leads")
            .sort_values("leads", ascending=True)
            .tail(15)
        )
        fig_pais = px.bar(
            df_pais, x="leads", y="pais", orientation="h",
            labels={"leads": "Leads", "pais": ""},
            text_auto=".0f",
            color_discrete_sequence=["#6C63FF"],
        )
        fig_pais.update_layout(
            height=max(280, len(df_pais) * 30),
            margin=dict(l=0, r=40, t=20, b=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(tickfont=dict(size=11), gridcolor="rgba(0,0,0,0)"),
            xaxis=dict(gridcolor="rgba(0,0,0,0.08)"),
            showlegend=False,
        )
        fig_pais.update_traces(textposition="outside", textfont_size=10)
        st.plotly_chart(fig_pais, use_container_width=True)

    with col_p2:
        st.subheader("🎓 Leads por Programa")
        df_prog = (
            df_hsf.groupby("programa").size()
            .reset_index(name="leads")
            .sort_values("leads", ascending=True)
        )
        fig_prog = px.bar(
            df_prog, x="leads", y="programa", orientation="h",
            labels={"leads": "Leads", "programa": ""},
            text_auto=".0f",
            color_discrete_sequence=["#1877F2"],
        )
        fig_prog.update_layout(
            height=max(280, len(df_prog) * 30),
            margin=dict(l=0, r=40, t=20, b=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(tickfont=dict(size=11), gridcolor="rgba(0,0,0,0)"),
            xaxis=dict(gridcolor="rgba(0,0,0,0.08)"),
            showlegend=False,
        )
        fig_prog.update_traces(textposition="outside", textfont_size=10)
        st.plotly_chart(fig_prog, use_container_width=True)

    st.divider()

    # ─── Tabla principal: Plataforma × Campaña × País × Programa ─────────────
    st.subheader("📋 Detalle por Campaña, País y Programa")

    df_camp_hs = (
        df_hsf.groupby(["plataforma_hs", "campaña_hs", "pais", "programa"])
        .size().reset_index(name="Leads")
        .sort_values("Leads", ascending=False)
        .rename(columns={
            "plataforma_hs": "Plataforma",
            "campaña_hs":    "Campaña",
            "pais":          "País",
            "programa":      "Programa",
        })
    )
    st.dataframe(
        df_camp_hs,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Plataforma": st.column_config.TextColumn(width="small"),
            "Leads":      st.column_config.NumberColumn(format="%d"),
        },
    )

    st.divider()

    # ─── Heatmap: País × Plataforma ───────────────────────────────────────────
    st.subheader("🗺️ Leads: País × Plataforma")

    df_heat = (
        df_hsf.groupby(["pais", "plataforma_hs"])
        .size().reset_index(name="leads")
    )
    top_paises = df_hsf["pais"].value_counts().head(12).index.tolist()
    df_heat = df_heat[df_heat["pais"].isin(top_paises)]

    pivot = df_heat.pivot_table(index="pais", columns="plataforma_hs",
                                values="leads", aggfunc="sum", fill_value=0)
    fig_heat = px.imshow(
        pivot,
        text_auto=True,
        aspect="auto",
        color_continuous_scale="Blues",
        labels={"x": "Plataforma", "y": "País", "color": "Leads"},
    )
    fig_heat.update_layout(
        height=max(300, len(pivot) * 40),
        margin=dict(l=0, r=0, t=30, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        coloraxis_showscale=False,
    )
    fig_heat.update_xaxes(tickangle=-30)
    st.plotly_chart(fig_heat, use_container_width=True)
