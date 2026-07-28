# Dashboard de Inversión Publicitaria — Hofmann

Contexto para trabajar en este proyecto. Léelo antes de tocar código.

## Qué es
Dashboard **Streamlit** que unifica inversión y rendimiento de las campañas de pago
de **Hofmann**: Google Ads, Meta Ads, LinkedIn Ads y TikTok Ads.

- **Repo:** `WeRise-ESP/hofmann-ads-dashboard` (rama `main`)
- **App:** https://hofmann-ads-dashboard.streamlit.app
- **Entry point / main file:** `dashboard_ads.py`
- **Actualizar = `git push` a `main`** → Streamlit Cloud redespliega solo.

## Arrancar en local
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
streamlit run dashboard_ads.py
```
Necesitas `.streamlit/secrets.toml` (NO está en git — pídelo por el gestor de
contraseñas del equipo).

## Fuentes de datos
| Plataforma | Cómo |
|---|---|
| Google Ads | API (secrets) |
| Meta Ads | token de sistema permanente (secrets) |
| LinkedIn Ads | vía Google Sheet (`LINKEDIN_SHEET_URL` en secrets) |
| TikTok Ads | API (usa la métrica `conversion`, no `result`) |

- La app está protegida por contraseña (secrets).
- ⚠️ **NO cambies el subdominio de la app.** La URL está registrada como *Redirect URL*
  en la configuración OAuth de alguna plataforma de ads: si cambia, se rompe la
  autenticación.
