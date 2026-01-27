# W.I.P.

[Read this in English →](README.md)

# YT Clear View

Vista curada de YT sin el algoritmo de recomendacion.

## Capturas

![YT Clear View](screenshots/YT-Clear-View.jpg)

## Caracteristicas

- API REST con Flask y SQLite
- Microservicio separado para logs
- Frontend vanilla HTML/CSS/JS
- Deteccion de dispositivo y layout responsive
- Tema oscuro por defecto con persistencia
- Carrusel infinito para videos
- Localizacion UI (EN/ES) con JSON externo
- Integracion YT Data API v3
- Despliegue HTTPS detras de reverse proxy

### Categorizacion automatica de canales (NEW)

- **14+ categorias**: Gaming, Technology, Education, Music, Food, Fitness, Travel, Fashion, News, Entertainment, Vlogs, Sports, Art, Science
- **Clasificacion multi-metodo**: 4 metodos en cascada (YT Topics, TF-IDF, Hybrid Semantic, Ollama LLM)
- **Override manual**: reasigna cualquier canal a otra categoria
- **Carousels por categoria**: videos organizados por tipo de contenido
- **Colores por categoria**: cada categoria tiene su color propio

## Inicio rapido (Development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Crea `backend/.env` desde `backend/.env.example`, luego ejecuta:

```bash
cd backend
python -m flask --app app run --port 5550
```

O usa el script:

```bash
./scripts/run_local.sh
```

El script inicia:
- Backend en `http://localhost:5550`
- Frontend en `http://localhost:8080`
- Log viewer en `http://localhost:5551/logs` (default `admin/admin` si no esta en `.env`)

## Produccion (simple)

Usa un script separado para produccion:

```bash
./scripts/run_prod.sh
```

Notas:
- Usa un servidor real (nginx) para servir `frontend/`.
- Asegura que `backend/.env` tenga tus URLs de produccion y valores OAuth.

## Google Cloud setup (required)

Necesitas un proyecto en Google Cloud con YouTube Data API v3 habilitada y credenciales OAuth.

Pasos (cortos y simples):
1. Ve a Google Cloud Console: `https://console.cloud.google.com`
2. Crea o selecciona un proyecto.
3. Habilita **YouTube Data API v3**.
4. Configura la pantalla de consentimiento OAuth (nombre app + email).
5. Crea credenciales OAuth (tipo: **Web application**).
6. Define **Authorized JavaScript origins** y **Authorized redirect URIs** segun tus URLs.

En `backend/.env` (ver `backend/.env.example`) configura:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`

## URLs locales y config

Si ejecutas en local, deben coincidir:
- `backend/.env` contiene la URL del backend y el redirect OAuth.
- `frontend/config.js` define donde apunta la app y el log viewer.

Si cambias puertos o hostnames, actualiza ambos para:
- que el frontend apunte al backend/log viewer correcto.
- que el redirect OAuth coincida con el backend.

## Documentacion

- API reference: `docs/api-reference.md`
- Architecture: `docs/architecture.md`
- Deployment: `docs/deployment.md`
- Development: `docs/development.md`

## Licencia

MIT. Ver `LICENSE`.
