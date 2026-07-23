# Dashboard de Inversión Publicitaria — Hofmann

Dashboard en **Streamlit** que unifica la inversión y el rendimiento de las
campañas de pago de Hofmann: **Google Ads, Meta Ads, LinkedIn Ads y TikTok Ads**.

## Despliegue

| | |
|---|---|
| **Repositorio** | `WeRise-ESP/hofmann-ads-dashboard` (privado, rama `main`) |
| **App en producción** | https://hofmann-ads-dashboard.streamlit.app |
| **Main file path** | `dashboard_ads.py` |

**Actualizar la app = hacer `git push` a `main`.** Streamlit Cloud redespliega
solo; no hay que hacer nada más.

⚠️ **No cambies el subdominio.** La URL está registrada como *Redirect URL* en la
configuración OAuth de alguna plataforma de ads: si cambia, se rompe la
autenticación.

## Puesta en marcha en local

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
streamlit run dashboard_ads.py
```

## Credenciales

`.streamlit/secrets.toml` **no está en el repo** (lo protege `.gitignore`).
En producción viven en **App settings → Secrets** del panel de Streamlit.
Incluye las credenciales de Google Ads, Meta Ads y la URL del Google Sheet de
LinkedIn Ads.

## Accesos

- **Administrar la app** (redeploy, secrets, invitados): cualquier miembro de
  WeRise-ESP con acceso al repositorio.
- **Ver el dashboard**: lista de invitados por email en **App settings →
  Sharing**. Esa lista vive en la app, no en el repo — si algún día se recrea la
  app, hay que volver a introducirla.
