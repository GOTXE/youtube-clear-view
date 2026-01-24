# Guía Completa: YouTube Clear View

## 📋 Descripción General

Aplicación web para curar contenido de YouTube, permitiendo ver solo los videos de canales suscritos sin el algoritmo de recomendaciones. La aplicación contará con:

- **Backend API** en Python3 + Flask + SQLite (alojado en NAS)
- **Frontend responsive** HTML/CSS/JavaScript vanilla (alojado en NAS)
- **Multi-usuario** con sincronización entre dispositivos
- **Detección automática** de tipo de dispositivo (TV 50"+, Tablet, Móvil, Escritorio)
- **Integración** con YouTube Data API v3
- **Todo configurable** vía archivo `.env` (sin hardcoding)

---

## 🏗️ Arquitectura del Proyecto

**Separación Backend/Frontend:**
- **Backend**: Microservicio en NAS (Docker/systemd) - API REST en puerto 5550
- **Frontend**: Carpeta web de Synology (`/volume1/web/youtube-clear-view/`)

```
youtube-clear-view/
├── backend/                   # Microservicio API en NAS
│   ├── app.py                 # Aplicación Flask principal
│   ├── config.py              # Configuración desde .env
│   ├── models.py              # Modelos SQLAlchemy
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py           # Autenticación de usuarios
│   │   ├── channels.py       # Gestión de canales
│   │   ├── videos.py         # Videos y visualizaciones
│   │   ├── themes.py         # Temáticas personalizadas
│   │   └── devices.py        # Gestión de dispositivos
│   ├── services/
│   │   ├── __init__.py
│   │   └── youtube_api.py    # Integración con YouTube API
│   ├── database.py           # Inicialización DB
│   ├── requirements.txt      # Dependencias Python
│   ├── .env.example          # Plantilla de configuración
│   ├── .env                  # Configuración real (NO commitear)
│   ├── start.sh              # Script de inicio
│   └── docker-compose.yml    # Deployment en Docker
├── frontend/                  # Se desplegará en /volume1/web/youtube-clear-view/
│   ├── index.html            # Página principal
│   ├── config.js             # Configuración (URL del backend)
│   ├── css/
│   │   ├── main.css          # Estilos base
│   │   ├── tv.css            # Estilos para TV 50"+
│   │   ├── tablet.css        # Estilos para tablet
│   │   └── mobile.css        # Estilos para móvil
│   ├── js/
│   │   ├── app.js            # Lógica principal
│   │   ├── api.js            # Cliente API REST
│   │   ├── auth.js           # Gestión de autenticación
│   │   ├── carousel.js       # Componente carrousel
│   │   ├── device.js         # Detección de dispositivo
│   │   └── utils.js          # Utilidades
│   └── assets/
│       └── icons/            # Iconos y recursos
├── tech_docs/                 # Documentación técnica local (NO sincronizar / NO commitear)
├── .gitignore
└── README.md

Acceso:
- Backend API: http://tu-nas.local:5550/api
- Frontend Web: http://tu-nas.local/youtube-clear-view/
```

---

## 🚀 Paso 1: Configuración Inicial del Proyecto

### Prompt para codex:

```
Necesito crear la estructura inicial de un proyecto llamado "youtube-clear-view" con la siguiente arquitectura:

- Directorio backend/ con:
  - app.py (Flask app vacía con estructura básica)
  - config.py (carga configuración desde .env)
  - models.py (modelos SQLAlchemy vacíos, preparados para definir)
  - database.py (inicialización SQLAlchemy)
  - requirements.txt (Flask, SQLAlchemy, python-dotenv, requests, flask-cors)
  - .env.example (plantilla con variables: FLASK_SECRET_KEY, YOUTUBE_API_KEY, DATABASE_URI, FLASK_PORT, FLASK_HOST)
  - carpetas routes/ y services/ con __init__.py

- Directorio frontend/ con:
  - index.html (HTML5 básico responsive)
  - carpetas css/, js/, assets/icons/
  - archivos CSS vacíos: main.css, tv.css, tablet.css, mobile.css
  - archivos JS vacíos: app.js, api.js, auth.js, carousel.js, device.js, utils.js

- Archivos raíz:
  - tech_docs/ (documentación técnica local, NO sincronizar / NO commitear)
  - .gitignore (Python, Node, .env, SQLite, __pycache__, etc.)
  - README.md (descripción básica del proyecto)

Por favor crea todos estos archivos con estructura básica funcional.
```

### Comandos Git:

```bash
cd /ruta/donde/quieras/el/proyecto
# codex habrá creado la estructura
git init
git remote add origin git@tu-github-server:usuario/youtube-clear-view.git
git add .
git commit -m "chore: initial project structure"
git push -u origin main
```

---

## 🗄️ Paso 2: Modelos de Base de Datos

### Prompt para CODEX:

```
Necesito definir los modelos SQLAlchemy en backend/models.py para la base de datos SQLite con las siguientes tablas:

1. **User**:
   - id (PK, autoincremental)
   - username (único, no nulo)
   - display_name (nombre para mostrar)
   - created_at (timestamp)
   - updated_at (timestamp)

2. **Channel**:
   - id (PK, autoincremental)
   - youtube_channel_id (único, no nulo)
   - title (nombre del canal)
   - thumbnail_url
   - description
   - created_at

3. **UserChannel** (relación many-to-many):
   - id (PK)
   - user_id (FK a User)
   - channel_id (FK a Channel)
   - subscribed_at

4. **Theme** (temáticas personalizadas):
   - id (PK)
   - user_id (FK a User)
   - name (nombre de la temática)
   - color (código color hex para UI)
   - created_at

5. **ThemeChannel** (canales asignados a temáticas):
   - id (PK)
   - theme_id (FK a Theme)
   - channel_id (FK a Channel)

6. **Video**:
   - id (PK)
   - youtube_video_id (único)
   - channel_id (FK a Channel)
   - title
   - description
   - thumbnail_url
   - published_at
   - duration
   - fetched_at (cuando se obtuvo de la API)

7. **WatchedVideo**:
   - id (PK)
   - user_id (FK a User)
   - video_id (FK a Video)
   - watched_at
   - device_id (FK a UserDevice, opcional)

8. **UserDevice**:
   - id (PK)
   - user_id (FK a User)
   - device_identifier (hash único del dispositivo)
   - device_type (enum: 'tv', 'tablet', 'mobile', 'desktop')
   - user_agent
   - last_used_at
   - created_at

Por favor implementa estos modelos con:
- Relaciones apropiadas (relationships)
- Índices en campos de búsqueda frecuente
- Métodos to_dict() para serialización JSON
- Configuración de cascadas apropiadas
```

### Comandos Git:

```bash
git add backend/models.py
git commit -m "feat: add database models for users, channels, videos and devices"
git push
```

---

## ⚙️ Paso 3: Configuración y Database Setup

### Prompt para codex:

```
Necesito implementar:

1. **backend/config.py**:
   - Clase Config que cargue todas las variables del .env
   - Validación de que existan las variables críticas
   - Valores por defecto razonables donde aplique
   - Variables: FLASK_SECRET_KEY, YOUTUBE_API_KEY, DATABASE_URI (default: sqlite:///youtube_clear_view.db), FLASK_PORT (default: 5550), FLASK_HOST (default: 0.0.0.0), CORS_ORIGINS

2. **backend/database.py**:
   - Inicialización de SQLAlchemy
   - Función init_db(app) que configure la base de datos
   - Función create_tables() que cree todas las tablas
   - Manejo de errores apropiado

3. **backend/app.py**:
   - Inicializar Flask app
   - Cargar configuración desde Config
   - Inicializar base de datos
   - Configurar CORS (importante: el frontend estará en Synology Web Station)
     - Permitir orígenes desde CORS_ORIGINS en .env
     - Credenciales habilitadas (credentials=True)
     - Headers apropiados para autenticación
   - Registrar blueprints (vacíos por ahora)
   - Endpoint de health check: GET /api/health
   - Manejo de errores 404, 500
   - Modo debug configurable desde .env

**IMPORTANTE**: Como el frontend estará en `/volume1/web/youtube-clear-view/` y el backend en puerto 5550, es crítico configurar CORS correctamente.

Por favor implementa estos archivos de forma robusta y sin hardcoding.
```

### Comandos Git:

```bash
git add backend/config.py backend/database.py backend/app.py
git commit -m "feat: implement configuration management and database initialization"
git push
```

---

## 🔌 Paso 4: Servicio de YouTube API

### Prompt para codex:

```
Necesito implementar backend/services/youtube_api.py con una clase YouTubeService que:

1. **__init__(api_key)**:
   - Inicializa con la API key de YouTube
   - Configura el cliente de la API

2. **get_channel_info(channel_id)**:
   - Obtiene información de un canal: título, descripción, thumbnail
   - Retorna dict con los datos o None si error
   - Manejo de errores de API

3. **get_channel_videos(channel_id, max_results=50)**:
   - Obtiene los últimos videos de un canal
   - Retorna lista de dicts con: video_id, title, description, thumbnail, published_at, duration
   - Manejo de paginación si es necesario

4. **search_videos(query, channel_id=None, max_results=20)**:
   - Busca videos por texto
   - Opcionalmente filtra por canal
   - Retorna lista de videos

5. **get_video_details(video_id)**:
   - Obtiene detalles completos de un video específico
   - Incluye duración, estadísticas, etc.

Todos los métodos deben:
- Manejar rate limits de la API
- Loggear errores apropiadamente
- Retornar None o [] en caso de error (no lanzar excepciones)
- Cachear respuestas si es posible (opcional pero recomendado)

Usa la librería 'google-api-python-client' y añádela a requirements.txt.
```

### Comandos Git:

```bash
git add backend/services/youtube_api.py backend/requirements.txt
git commit -m "feat: implement YouTube API service integration"
git push
```

---

## 🛣️ Paso 5: Routes - Autenticación

### Prompt para codex:

```
Implementa backend/routes/auth.py con Blueprint para autenticación:

**Endpoints:**

1. **POST /api/auth/login**:
   - Body: {username: string}
   - Si el usuario existe, retorna: {user_id, username, display_name, token}
   - Si no existe, lo crea automáticamente
   - Token simple (puede ser JWT o hash único)
   - Retorna 200 con datos del usuario

2. **GET /api/auth/users**:
   - Retorna lista de todos los usuarios: [{id, username, display_name}]
   - Para selector de usuario en frontend

3. **GET /api/auth/current**:
   - Requiere token en header: Authorization: Bearer <token>
   - Retorna datos del usuario actual
   - 401 si token inválido

4. **PUT /api/auth/profile**:
   - Body: {display_name: string}
   - Actualiza el perfil del usuario
   - Requiere autenticación

Implementa:
- Decorador @require_auth para proteger endpoints
- Generación y validación de tokens
- Manejo apropiado de errores
- Logging de acciones
```

### Comandos Git:

```bash
git add backend/routes/auth.py
git commit -m "feat: implement user authentication endpoints"
git push
```

---

## 🛣️ Paso 6: Routes - Canales

### Prompt para codex:

```
Implementa backend/routes/channels.py con Blueprint para gestión de canales:

**Endpoints:**

1. **GET /api/channels**:
   - Requiere autenticación
   - Retorna canales suscritos del usuario actual
   - Incluye información del canal de YouTube

2. **POST /api/channels/subscribe**:
   - Body: {youtube_channel_id: string}
   - Suscribe al usuario al canal
   - Si el canal no existe en DB, lo obtiene de YouTube API y lo crea
   - Retorna 201 con datos del canal

3. **DELETE /api/channels/:channel_id/unsubscribe**:
   - Desuscribe al usuario del canal
   - No elimina el canal de la DB (otros usuarios pueden estar suscritos)
   - Retorna 204

4. **POST /api/channels/refresh**:
   - Body: {channel_id: int} (opcional, si no se pasa, refresca todos)
   - Obtiene nuevos videos de los canales desde YouTube API
   - Actualiza la tabla Video
   - Retorna número de videos nuevos encontrados

5. **GET /api/channels/:channel_id/videos**:
   - Retorna videos del canal específico
   - Query params: ?limit=20&offset=0
   - Marca cuáles ya fueron vistos por el usuario

Todos requieren autenticación. Usa el YouTubeService para obtener datos de YouTube.
```

### Comandos Git:

```bash
git add backend/routes/channels.py
git commit -m "feat: implement channel management endpoints"
git push
```

---

## 🛣️ Paso 7: Routes - Videos

### Prompt para codex:

```
Implementa backend/routes/videos.py con Blueprint para gestión de videos:

**Endpoints:**

1. **GET /api/videos/latest**:
   - Requiere autenticación
   - Retorna los últimos videos de todos los canales suscritos
   - Query params: ?limit=50
   - Ordenados por published_at descendente
   - Marca cuáles ya fueron vistos
   - Retorna: [{video, channel, watched}]

2. **GET /api/videos/by-theme/:theme_id**:
   - Retorna videos de los canales asociados a una temática
   - Mismo formato que /latest

3. **POST /api/videos/:video_id/watch**:
   - Body: {device_id: int} (opcional)
   - Marca el video como visto
   - Retorna 204

4. **DELETE /api/videos/:video_id/unwatch**:
   - Desmarca el video como visto
   - Retorna 204

5. **GET /api/videos/search**:
   - Query params: ?q=texto&channel_id=1&theme_id=2
   - Busca videos en la base de datos local
   - Filtros opcionales por canal o temática
   - Retorna resultados paginados

Implementa paginación eficiente y manejo de índices para búsquedas rápidas.
```

### Comandos Git:

```bash
git add backend/routes/videos.py
git commit -m "feat: implement video management and search endpoints"
git push
```

---

## 🛣️ Paso 8: Routes - Temáticas

### Prompt para codex:

```
Implementa backend/routes/themes.py con Blueprint para gestión de temáticas:

**Endpoints:**

1. **GET /api/themes**:
   - Requiere autenticación
   - Retorna temáticas del usuario con canales asociados
   - Formato: [{id, name, color, channels: [{id, title, thumbnail}]}]

2. **POST /api/themes**:
   - Body: {name: string, color: string}
   - Crea nueva temática para el usuario
   - Retorna 201 con la temática creada

3. **PUT /api/themes/:theme_id**:
   - Body: {name: string, color: string}
   - Actualiza temática
   - Retorna temática actualizada

4. **DELETE /api/themes/:theme_id**:
   - Elimina temática (no elimina canales)
   - Retorna 204

5. **POST /api/themes/:theme_id/channels**:
   - Body: {channel_ids: [int, int, ...]}
   - Asocia canales a la temática
   - Retorna 200

6. **DELETE /api/themes/:theme_id/channels/:channel_id**:
   - Desasocia canal de la temática
   - Retorna 204

Validar que el usuario solo pueda modificar sus propias temáticas.
```

### Comandos Git:

```bash
git add backend/routes/themes.py
git commit -m "feat: implement theme management endpoints"
git push
```

---

## 🛣️ Paso 9: Routes - Dispositivos

### Prompt para codex:

```
Implementa backend/routes/devices.py con Blueprint para gestión de dispositivos:

**Endpoints:**

1. **POST /api/devices/register**:
   - Body: {device_identifier: string, user_agent: string}
   - Registra un nuevo dispositivo para el usuario
   - Si ya existe, actualiza last_used_at
   - Retorna: {id, device_type: null} (device_type null = pendiente configurar)

2. **GET /api/devices**:
   - Requiere autenticación
   - Retorna dispositivos del usuario
   - Formato: [{id, device_identifier, device_type, last_used_at}]

3. **PUT /api/devices/:device_id/type**:
   - Body: {device_type: 'tv' | 'tablet' | 'mobile' | 'desktop'}
   - Usuario confirma/cambia tipo de dispositivo
   - Retorna dispositivo actualizado

4. **DELETE /api/devices/:device_id**:
   - Elimina dispositivo
   - Retorna 204

5. **GET /api/devices/detect**:
   - Body: {user_agent: string, screen_width: int, screen_height: int}
   - Sugiere tipo de dispositivo basado en características
   - Retorna: {suggested_type: string, confidence: float}
   - Algoritmo de detección:
     - screen_width >= 1920 && screen_height >= 1080 → 'tv' (alta confianza)
     - screen_width >= 768 && screen_width < 1920 → 'tablet'
     - screen_width < 768 → 'mobile'
     - Resto → 'desktop'

Implementar lógica robusta de detección y registro de dispositivos.
```

### Comandos Git:

```bash
git add backend/routes/devices.py
git commit -m "feat: implement device management and detection endpoints"
git push
```

---

## 🎨 Paso 10: Frontend - Configuración del Backend

### Prompt para codex:

```
Crea frontend/config.js para configurar la conexión con el backend:

**Requisitos:**

Este archivo será el único lugar donde se configura la URL del backend API.

```javascript
// Configuración de la aplicación
const APP_CONFIG = {
  // URL del backend API (cambiar según entorno)
  API_BASE_URL: 'http://tu-nas.local:5550/api',
  
  // Versión de la API
  API_VERSION: 'v1',
  
  // Timeout para requests (ms)
  REQUEST_TIMEOUT: 30000,
  
  // Configuración de YouTube
  YOUTUBE_BASE_URL: 'https://www.youtube.com',
  
  // Configuración de paginación
  DEFAULT_PAGE_SIZE: 20,
  VIDEOS_PER_CAROUSEL: 50,
  
  // Configuración de UI
  NOTIFICATION_DURATION: 3000,
  CAROUSEL_AUTO_SCROLL: false,
  
  // Configuración de detección de dispositivo
  DEVICE_TYPES: {
    TV: 'tv',
    TABLET: 'tablet',
    MOBILE: 'mobile',
    DESKTOP: 'desktop'
  },
  
  // Breakpoints para detección responsive (px)
  BREAKPOINTS: {
    MOBILE_MAX: 767,
    TABLET_MIN: 768,
    TABLET_MAX: 1919,
    TV_MIN: 1920
  }
};

// Exportar configuración
window.APP_CONFIG = APP_CONFIG;
```

**Instrucciones para el usuario:**
1. Este archivo debe editarse para poner la URL correcta del backend
2. En producción, cambiar `tu-nas.local:5550` por la IP/dominio real del NAS
3. Ejemplo: `http://192.168.1.100:5550/api` o `http://nas.midominio.com:5550/api`

Crear también un archivo `config.example.js` con valores de ejemplo para commitear al repo.
```

### Comandos Git:

```bash
git add frontend/config.js frontend/config.example.js
git commit -m "feat: add frontend configuration for backend API connection"
git push
```

---

## 🎨 Paso 11: Frontend - HTML Base

### Prompt para codex:

```
Crea frontend/index.html con estructura HTML5 semántica y responsive:

**Requisitos:**

1. **Head**:
   - Meta tags: viewport, charset UTF-8, description
   - Title: "YouTube Clear View"
   - Links a todos los CSS (main.css siempre, luego tv/tablet/mobile según media queries)
   - Preconnect a API de YouTube

2. **Body estructura**:
   - Header:
     - Logo/título "YouTube Clear View"
     - Selector de usuario (dropdown)
     - Usuario actual mostrado
     - Indicador de tipo de dispositivo
   
   - Section de filtros:
     - Barra de búsqueda (input text con botón)
     - Filtros seleccionables (checkboxes): "No vistos", "Última semana", etc.
     - Selector de temática (dropdown con las temáticas del usuario)
   
   - Section carrousel principal:
     - Título: "Últimos videos"
     - Contenedor de carrousel (scroll horizontal)
   
   - Section carrouseles por temática:
     - Dinámicos según temáticas del usuario
     - Cada uno con título de la temática y su color
   
   - Footer:
     - Configuración (botón)
     - About

3. **Accesibilidad**:
   - ARIA labels apropiados
   - Navegación por teclado
   - Semántica correcta

4. **Sin contenido hardcoded**:
   - Todo será poblado dinámicamente desde JavaScript

**Scripts al final del body (en este orden):**
1. config.js (PRIMERO - configuración del backend)
2. utils.js
3. api.js
4. auth.js
5. device.js
6. carousel.js
7. app.js

IMPORTANTE: config.js debe cargarse antes que cualquier otro script para que APP_CONFIG esté disponible.
```

### Comandos Git:

```bash
git add frontend/index.html
git commit -m "feat: create responsive HTML structure for frontend"
git push
```

---

## 🎨 Paso 12: Frontend - CSS Main y Responsive

### Prompt para codex:

```
Implementa los archivos CSS con sistema responsive:

**frontend/css/main.css**:
- Variables CSS para colores, espaciados, fuentes
- Reset CSS básico
- Estilos base para body, header, sections
- Sistema de grid/flexbox
- Estilos para botones, inputs, cards de video
- Animaciones suaves para hover y transiciones
- Tipografía: fuente sans-serif legible

**frontend/css/tv.css** (media query min-width: 1920px):
- Tamaños de fuente grandes (mínimo 24px para texto, 48px para títulos)
- Miniaturas de video: 400px x 225px mínimo
- Espaciado generoso entre elementos (40px+)
- Focus states muy visibles para navegación con control remoto
- Carouseles con 4-5 items visibles
- Diseño para distancia de visualización 2.5m+

**frontend/css/tablet.css** (media query 768px - 1919px):
- Tamaños moderados
- Miniaturas: 300px x 169px
- Carouseles con 3 items visibles
- Touch-friendly: botones mínimo 44px x 44px

**frontend/css/mobile.css** (media query max-width: 767px):
- Layout vertical
- Carouseles con 1-2 items visibles
- Navegación móvil optimizada
- Miniaturas: 100% width, responsive

**Paleta de colores sugerida**:
- Fondo oscuro (#1a1a1a) para reducir fatiga visual
- Texto claro (#f5f5f5)
- Acentos: azul (#3b82f6) y verde (#10b981)
- Modo claro como alternativa (configurable)

Implementa sistema de temas CSS custom properties.
```

### Comandos Git:

```bash
git add frontend/css/
git commit -m "feat: implement responsive CSS styles for all device types"
git push
```

---

## 🎨 Paso 13: Frontend - JavaScript API Client

### Prompt para codex:

```
Implementa frontend/js/api.js con cliente para comunicación con el backend:

**Clase APIClient**:

Propiedades:
- baseURL (obtener de APP_CONFIG.API_BASE_URL)
- timeout (obtener de APP_CONFIG.REQUEST_TIMEOUT)
- token (JWT o auth token)

Métodos genéricos:
- async request(endpoint, method, body, headers)
  - Incluir timeout
  - Incluir token en headers si existe
  - Manejar errores de red y CORS
  - Parsear respuestas JSON
- async get(endpoint)
- async post(endpoint, body)
- async put(endpoint, body)
- async delete(endpoint)
- setToken(token)
- getToken()

Métodos específicos para cada endpoint:
- **Auth**: login(username), getUsers(), getCurrentUser(), updateProfile(displayName)
- **Channels**: getChannels(), subscribe(youtubeChannelId), unsubscribe(channelId), refreshChannels(channelId?), getChannelVideos(channelId, limit, offset)
- **Videos**: getLatestVideos(limit), getVideosByTheme(themeId), markAsWatched(videoId, deviceId?), markAsUnwatched(videoId), searchVideos(query, channelId?, themeId?)
- **Themes**: getThemes(), createTheme(name, color), updateTheme(themeId, name, color), deleteTheme(themeId), addChannelsToTheme(themeId, channelIds), removeChannelFromTheme(themeId, channelId)
- **Devices**: registerDevice(deviceIdentifier, userAgent), getDevices(), setDeviceType(deviceId, deviceType), deleteDevice(deviceId), detectDevice(userAgent, screenWidth, screenHeight)

Manejo de errores:
- Catch network errors
- Parse error responses del backend
- Retry lógico en caso de rate limiting
- Logging de errores en consola

Retornar siempre JSON parseado o lanzar error claro.
```

### Comandos Git:

```bash
git add frontend/js/api.js
git commit -m "feat: implement API client for backend communication"
git push
```

---

## 🎨 Paso 14: Frontend - Autenticación

### Prompt para codex:

```
Implementa frontend/js/auth.js para gestión de autenticación:

**Funcionalidades**:

1. **Inicialización**:
   - Verificar si hay token guardado en localStorage
   - Si hay token, validar con backend (/api/auth/current)
   - Si válido, cargar usuario actual
   - Si no, mostrar selector de usuarios

2. **Selector de usuarios**:
   - Obtener lista de usuarios del backend
   - Mostrar lista visual con nombres
   - Botón "Nuevo usuario" para crear
   - Al seleccionar: hacer login y guardar token

3. **Crear usuario**:
   - Modal/prompt para ingresar username
   - Validación básica (no vacío, alfanumérico)
   - Crear usuario vía API
   - Auto-login tras creación

4. **Funciones**:
   - getCurrentUser() → retorna objeto usuario o null
   - isAuthenticated() → boolean
   - logout() → limpia token, recarga página
   - switchUser() → muestra selector sin logout completo

5. **UI**:
   - Mostrar usuario actual en header
   - Botón para cambiar de usuario
   - Actualizar UI cuando cambia usuario

Integrar con APIClient. Emitir eventos custom cuando cambia el estado de auth.
```

### Comandos Git:

```bash
git add frontend/js/auth.js
git commit -m "feat: implement user authentication and session management"
git push
```

---

## 🎨 Paso 15: Frontend - Detección de Dispositivos

### Prompt para codex:

```
Implementa frontend/js/device.js para detección y gestión de dispositivos:

**Funcionalidades**:

1. **Detección automática**:
   - Generar device_identifier único (fingerprint basado en: user agent, screen resolution, timezone, language)
   - Obtener datos: user_agent, screen.width, screen.height
   - Llamar a /api/devices/detect para sugerencia
   - Registrar dispositivo: /api/devices/register

2. **Primera vez en dispositivo**:
   - Si device_type es null (nuevo dispositivo)
   - Mostrar modal/diálogo: "Detectamos que usas [suggested_type]. ¿Es correcto?"
   - Opciones: Confirmar / Cambiar manualmente (radio buttons: TV, Tablet, Móvil, Escritorio)
   - Guardar preferencia: /api/devices/:id/type

3. **Aplicar estilos**:
   - Añadir clase al <body>: device-tv, device-tablet, device-mobile, device-desktop
   - Los CSS responsive ya aplicarán estilos apropiados
   - Guardar device_id en localStorage para futuras sesiones

4. **Funciones**:
   - async detectDevice()
   - async registerDevice()
   - async confirmDeviceType(type)
   - getDeviceId() → retorna device_id del localStorage
   - getCurrentDeviceType() → retorna tipo actual

5. **Persistencia**:
   - Guardar device_id en localStorage
   - Al iniciar app, verificar si dispositivo ya está registrado
   - Actualizar last_used_at en cada visita

Ejecutar automáticamente al cargar la página, después de autenticación.
```

### Comandos Git:

```bash
git add frontend/js/device.js
git commit -m "feat: implement automatic device detection and type selection"
git push
```

---

## 🎨 Paso 16: Frontend - Componente Carrousel

### Prompt para codex:

```
Implementa frontend/js/carousel.js con componente reutilizable de carrousel:

**Clase Carousel**:

Constructor:
- containerId: ID del elemento DOM contenedor
- videos: array de objetos video
- options: {itemsPerView: 'auto', gap: 20, showControls: true}

Métodos:
- render(): crea el HTML del carrousel
- renderVideoCard(video): crea card individual de video
  - Thumbnail como imagen de fondo
  - Título del video (truncado)
  - Nombre del canal
  - Duración del video
  - Indicador "visto" si watched === true
  - Click abre video en nueva pestaña de YouTube
  - Click también marca como visto (si no lo está)
- scrollLeft(): desplaza carrousel a la izquierda
- scrollRight(): desplaza carrousel a la derecha
- destroy(): limpia event listeners

**HTML estructura del carrousel**:
```html
<div class="carousel">
  <button class="carousel-control left">◀</button>
  <div class="carousel-track">
    <!-- Video cards -->
  </div>
  <button class="carousel-control right">▶</button>
</div>
```

**Interactividad**:
- Navegación con botones left/right
- Scroll horizontal suave (smooth scroll)
- Touch/drag para scroll en móviles
- Teclado: flechas izquierda/derecha
- Al hacer click en video:
  1. Abrir en nueva pestaña: `https://youtube.com/watch?v=${video.youtube_video_id}`
  2. Llamar a API: markAsWatched(video.id, deviceId)
  3. Actualizar UI: añadir clase "watched"

**Responsive**:
- TV: 4-5 videos visibles
- Tablet: 3 videos visibles
- Mobile: 1-2 videos visibles
- Ajustar automáticamente según clase en <body>

Exportar clase para uso en app.js.
```

### Comandos Git:

```bash
git add frontend/js/carousel.js
git commit -m "feat: implement reusable carousel component for video display"
git push
```

---

## 🎨 Paso 17: Frontend - Utilidades

### Prompt para codex:

```
Implementa frontend/js/utils.js con funciones auxiliares:

**Funciones**:

1. **formatDuration(seconds)**:
   - Convierte segundos a formato HH:MM:SS o MM:SS
   - Ejemplo: 125 → "2:05"

2. **formatDate(dateString)**:
   - Formatea fecha ISO a texto legible
   - Ejemplo: "2024-01-20" → "20 ene 2024"
   - Locale español

3. **truncateText(text, maxLength)**:
   - Trunca texto y añade "..." si excede maxLength
   - Ejemplo: truncateText("Video largo", 10) → "Video la..."

4. **debounce(func, delay)**:
   - Implementa debounce para búsquedas
   - Retorna función debounced

5. **getYouTubeVideoUrl(videoId)**:
   - Retorna URL completa: `https://www.youtube.com/watch?v=${videoId}`

6. **getYouTubeThumbnail(videoId, quality)**:
   - quality: 'default', 'medium', 'high', 'maxres'
   - Retorna URL de thumbnail

7. **generateDeviceFingerprint()**:
   - Genera hash único del dispositivo
   - Usa: navigator.userAgent, screen.width, screen.height, timezone, language
   - Retorna string hash (puedes usar simple concatenación + btoa)

8. **showNotification(message, type)**:
   - type: 'success', 'error', 'info', 'warning'
   - Muestra toast notification temporal (3 segundos)
   - Crea elemento DOM, lo inserta, y lo remueve

9. **showModal(title, content, buttons)**:
   - Muestra modal personalizable
   - buttons: [{text, onClick, primary}]
   - Retorna Promise que resuelve con botón clickeado

10. **loadingSpinner(show, containerId?)**:
    - Muestra/oculta spinner de carga
    - Si containerId, lo muestra en ese contenedor
    - Si no, overlay de pantalla completa

Exportar todas las funciones. Usar en otros módulos.
```

### Comandos Git:

```bash
git add frontend/js/utils.js
git commit -m "feat: implement utility functions for UI and data formatting"
git push
```

---

## 🎨 Paso 18: Frontend - Aplicación Principal

### Prompt para codex:

```
Implementa frontend/js/app.js como orquestador principal de la aplicación:

**Inicialización**:

1. **DOMContentLoaded**:
   - Verificar que APP_CONFIG esté disponible
   - Inicializar APIClient con APP_CONFIG.API_BASE_URL
   - Ejecutar initAuth()
   - Ejecutar initDevice()
   - Una vez autenticado y dispositivo configurado: loadApp()

2. **initAuth()**:
   - Verificar autenticación (auth.js)
   - Si no autenticado: mostrar selector de usuarios
   - Esperar a que usuario se autentique
   - Setup event listeners para cambio de usuario

3. **initDevice()**:
   - Detectar y registrar dispositivo (device.js)
   - Si es primera vez: mostrar modal de confirmación de tipo
   - Aplicar clases CSS según tipo de dispositivo

4. **loadApp()**:
   - Cargar canales del usuario
   - Cargar temáticas del usuario
   - Cargar videos recientes
   - Renderizar carrousel principal con últimos videos
   - Renderizar carrouseles por temática
   - Setup event listeners para filtros y búsqueda

**Renderización**:

1. **renderMainCarousel(videos)**:
   - Usar clase Carousel
   - Crear carrousel con videos más recientes
   - Insertar en section correspondiente

2. **renderThemeCarousels(themes)**:
   - Para cada temática del usuario
   - Obtener videos de esa temática
   - Crear carrousel
   - Aplicar color de la temática al título

3. **setupFilters()**:
   - Event listener en checkboxes de filtros
   - Al cambiar: recargar videos con filtros
   - Filtros: "No vistos", "Última semana", "Último mes"

4. **setupSearch()**:
   - Event listener en input de búsqueda (con debounce)
   - Llamar a searchVideos() de API
   - Renderizar resultados en lugar de carrouseles normales
   - Botón "Limpiar búsqueda" para volver a vista normal

5. **setupRefresh()**:
   - Botón/timer para refrescar videos desde YouTube API
   - Llamar a /api/channels/refresh
   - Actualizar carrouseles con nuevos videos
   - Mostrar notificación con número de videos nuevos

**Estado global**:
- currentUser
- currentDevice
- channels
- themes
- filters (objeto con estado de filtros activos)

**Event listeners**:
- Cambio de usuario
- Filtros
- Búsqueda
- Configuración (modal de ajustes)

Integrar todos los módulos previos. Este es el archivo principal que coordina toda la app.
```

### Comandos Git:

```bash
git add frontend/js/app.js
git commit -m "feat: implement main application orchestration and UI rendering"
git push
```

---

## 🧪 Paso 19: Testing y Debugging

### Prompt para codex:

```
Necesito implementar funcionalidades de testing y debugging:

1. **backend/app.py**:
   - Añadir endpoint GET /api/debug/db que retorne estadísticas de la DB:
     - Número de usuarios, canales, videos, temáticas
     - Útil para verificar que todo funciona
   - Solo disponible si FLASK_DEBUG=True

2. **Script de población de datos de prueba** (backend/seed_db.py):
   - Crear usuarios de ejemplo (user1, user2)
   - Crear canales de ejemplo (puedes usar IDs reales de YouTube)
   - Crear algunas temáticas
   - Asociar canales a usuarios y temáticas
   - Marcar algunos videos como vistos
   - Comando: python seed_db.py

3. **frontend/js/app.js**:
   - Añadir función de debug al objeto window para inspeccionar estado
   - window.appDebug = {getState, reloadVideos, clearCache, etc.}

4. **Logging**:
   - Backend: configurar logging apropiado (archivo + consola)
   - Frontend: console.log estructurado para debugging

Por favor implementa estos elementos para facilitar el desarrollo y debugging.
```

### Comandos Git:

```bash
git add backend/seed_db.py backend/app.py frontend/js/app.js
git commit -m "feat: add debugging tools and test data seeding script"
git push
```

---

## 🚀 Paso 20: Deployment en NAS Synology

### Prompt para codex:

```
Necesito preparar la aplicación para deployment en NAS Synology con backend y frontend separados:

## BACKEND (Microservicio en NAS)

1. **Script de inicio** (backend/start.sh):
   ```bash
   #!/bin/bash
   cd "$(dirname "$0")"
   source venv/bin/activate
   python app.py
   ```
   - Hacerlo ejecutable: chmod +x start.sh
   - Lee configuración de .env

2. **Systemd service** (backend/youtube-clear-view.service):
   - Service para que corra como daemon en Linux
   - Auto-restart en caso de fallo
   - Logs a journalctl
   - WorkingDirectory correcto
   - User y Group apropiados

3. **docker-compose.yml** (backend/docker-compose.yml):
   - Servicio backend (Python Flask)
   - Volumen para SQLite DB persistente
   - Puerto 5550:5550 (o configurable)
   - Variables de entorno desde .env
   - Restart policy: unless-stopped
   - Health check endpoint

## FRONTEND (Carpeta Web Synology)

4. **Script de deployment** (frontend/deploy-to-synology.sh):
   ```bash
   #!/bin/bash
   # Script para copiar frontend a Synology via SCP o rsync
   SYNOLOGY_USER="tu-usuario"
   SYNOLOGY_HOST="tu-nas.local"
   SYNOLOGY_PATH="/volume1/web/youtube-clear-view"
   
   # Copiar archivos
   rsync -avz --exclude 'node_modules' \
     ./ ${SYNOLOGY_USER}@${SYNOLOGY_HOST}:${SYNOLOGY_PATH}/
   
   echo "Frontend deployed to ${SYNOLOGY_HOST}:${SYNOLOGY_PATH}"
   ```
   - Configurable vía variables
   - Excluir archivos innecesarios

5. **Instrucciones de deployment** en README.md:
   
   **Backend:**
   - Clonar repo en el NAS
   - Crear entorno virtual: python3 -m venv venv
   - Instalar dependencias: pip install -r requirements.txt
   - Configurar .env con datos reales
   - Inicializar DB: python -c "from database import create_tables; create_tables()"
   - Opción A: Docker → docker-compose up -d
   - Opción B: Systemd → copiar service, systemctl enable/start
   - Verificar: curl http://localhost:5550/api/health
   
   **Frontend:**
   - Editar config.js con URL real del backend
   - Ejecutar deploy-to-synology.sh
   - O copiar manualmente a /volume1/web/youtube-clear-view/
   - Configurar permisos en Synology (lectura para http)
   - Acceder desde navegador: http://tu-nas.local/youtube-clear-view/

6. **Nginx/Apache config** (opcional, frontend/synology-web.conf):
   - Configuración de ejemplo si se necesita proxy reverso
   - Redirección de /youtube-clear-view a la carpeta correcta
   - Headers CORS si es necesario

Por favor crea estos archivos de configuración y scripts de deployment.
```

### Comandos Git:

```bash
git add backend/start.sh backend/youtube-clear-view.service backend/docker-compose.yml
git add frontend/deploy-to-synology.sh frontend/synology-web.conf
git add README.md
git commit -m "chore: add deployment configuration for Synology NAS"
git push
```

---

## 📚 Paso 21: Documentación Final

### Prompt para codex:

```
Actualiza el README.md con documentación completa del proyecto:

**Secciones**:

1. **Descripción**: qué hace la app, características principales
2. **Arquitectura**: diagrama de componentes, stack tecnológico
3. **Requisitos**: Python 3.10+, navegador moderno, API key de YouTube
4. **Instalación**:
   - Clonar repo
   - Setup backend (venv, requirements.txt)
   - Setup frontend (copiar archivos al servidor web)
   - Configurar .env
5. **Configuración**:
   - Obtener YouTube API key
   - Variables de .env explicadas
   - Configurar github SSH
6. **Uso**:
   - Iniciar aplicación
   - Acceder desde navegador
   - Primer uso (crear usuario)
   - Suscribirse a canales
   - Crear temáticas
7. **API Documentation**:
   - Lista de todos los endpoints
   - Request/response examples
8. **Desarrollo**:
   - Estructura del proyecto
   - Cómo contribuir
   - Convención de commits
9. **Troubleshooting**: problemas comunes y soluciones
10. **Licencia**: MIT o la que prefieras

Incluye screenshots/mockups si es posible (puedes dejar placeholders).
```

### Comandos Git:

```bash
git add README.md
git commit -m "docs: add comprehensive project documentation"
git push
```

---

## 🎯 Resumen de Comandos Git

### Formato de Commits (Conventional Commits)

```
<type>: <description>

Types:
- feat: nueva funcionalidad
- fix: corrección de bug
- docs: cambios en documentación
- style: formateo, punto y coma faltante, etc.
- refactor: refactorización de código
- test: añadir tests
- chore: tareas de mantenimiento
```

### Workflow Completo

```bash
# Inicialización
git init
git remote add origin git@tu-github:usuario/youtube-clear-view.git

# Después de cada paso importante
git add <archivos-modificados>
git commit -m "tipo: descripción clara del cambio"
git push

# Ver estado
git status

# Ver historial
git log --oneline

# Crear rama para feature
git checkout -b feature/nombre-feature
# ... hacer cambios ...
git add .
git commit -m "feat: descripción"
git push -u origin feature/nombre-feature
# Mergear en main después de review
```

---

## 🔧 Variables de Entorno (.env)

```bash
# Flask Configuration
FLASK_SECRET_KEY=tu-secret-key-super-segura-aqui
FLASK_PORT=5550
FLASK_HOST=0.0.0.0
FLASK_DEBUG=False

# Database
DATABASE_URI=sqlite:///youtube_clear_view.db

# YouTube API
YOUTUBE_API_KEY=tu-api-key-de-google-cloud-console

# CORS - IMPORTANTE: El frontend está en Synology Web Station
# Permite requests desde la carpeta web
CORS_ORIGINS=http://tu-nas.local,http://192.168.1.100,http://localhost

# Logging
LOG_LEVEL=INFO
LOG_FILE=app.log
```

**Notas importantes:**
- `CORS_ORIGINS`: Añade todas las URLs desde donde se accederá al frontend
  - IP del NAS: `http://192.168.1.100`
  - Hostname: `http://tu-nas.local`
  - Si usas dominio: `http://nas.midominio.com`
- Separar múltiples orígenes con comas
- NO incluir trailing slash
- Usar `http://` o `https://` según corresponda

---

## ✅ Checklist de Implementación

**Backend:**
- [ ] Paso 1: Estructura inicial del proyecto
- [ ] Paso 2: Modelos de base de datos
- [ ] Paso 3: Configuración y database setup (con CORS)
- [ ] Paso 4: Servicio YouTube API
- [ ] Paso 5: Routes - Autenticación
- [ ] Paso 6: Routes - Canales
- [ ] Paso 7: Routes - Videos
- [ ] Paso 8: Routes - Temáticas
- [ ] Paso 9: Routes - Dispositivos

**Frontend:**
- [ ] Paso 10: Configuración del Backend (config.js)
- [ ] Paso 11: HTML base
- [ ] Paso 12: CSS responsive (TV/Tablet/Móvil/Desktop)
- [ ] Paso 13: API Client
- [ ] Paso 14: Autenticación
- [ ] Paso 15: Detección dispositivos
- [ ] Paso 16: Componente Carrousel
- [ ] Paso 17: Utilidades
- [ ] Paso 18: App principal

**Testing y Deployment:**
- [ ] Paso 19: Testing y debugging
- [ ] Paso 20: Deployment en Synology
- [ ] Paso 21: Documentación final

**Post-deployment:**
- [ ] Configurar .env con datos reales
- [ ] Editar frontend/config.js con URL del backend
- [ ] Desplegar backend (Docker o systemd)
- [ ] Copiar frontend a /volume1/web/youtube-clear-view/
- [ ] Verificar CORS funcionando correctamente
- [ ] Obtener YouTube API key
- [ ] Crear primer usuario
- [ ] Suscribirse a canales de prueba

---

## 📦 Deployment en Synology NAS - Guía Detallada

### Backend (Microservicio)

**Opción A: Docker (Recomendado)**

1. Conectar por SSH al NAS:
   ```bash
   ssh admin@tu-nas.local
   ```

2. Crear directorio del proyecto:
   ```bash
   mkdir -p /volume1/docker/youtube-clear-view
   cd /volume1/docker/youtube-clear-view
   ```

3. Clonar repositorio:
   ```bash
   git clone git@tu-github:usuario/youtube-clear-view.git .
   cd backend
   ```

4. Crear y configurar .env:
   ```bash
   cp .env.example .env
   nano .env  # Editar con tus valores reales
   ```

5. Iniciar con Docker Compose:
   ```bash
   docker-compose up -d
   ```

6. Verificar que funciona:
   ```bash
   curl http://localhost:5550/api/health
   # Debe retornar: {"status": "ok"}
   ```

**Opción B: Systemd (Sin Docker)**

1. Instalar Python 3 y pip si no está instalado
2. Crear entorno virtual:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Copiar service file:
   ```bash
   sudo cp youtube-clear-view.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable youtube-clear-view
   sudo systemctl start youtube-clear-view
   ```

4. Verificar logs:
   ```bash
   sudo journalctl -u youtube-clear-view -f
   ```

### Frontend (Carpeta Web)

**Método 1: Script de Deploy (Recomendado)**

1. Desde tu PC de desarrollo, editar `frontend/deploy-to-synology.sh`:
   ```bash
   SYNOLOGY_USER="admin"
   SYNOLOGY_HOST="192.168.1.100"
   SYNOLOGY_PATH="/volume1/web/youtube-clear-view"
   ```

2. Ejecutar deployment:
   ```bash
   cd frontend
   chmod +x deploy-to-synology.sh
   ./deploy-to-synology.sh
   ```

**Método 2: Manual**

1. Conectar por SSH o usar File Station
2. Copiar todo el contenido de `frontend/` a `/volume1/web/youtube-clear-view/`
3. Asegurar permisos correctos:
   ```bash
   chmod -R 755 /volume1/web/youtube-clear-view
   chown -R http:http /volume1/web/youtube-clear-view
   ```

**Configuración Web Station (Synology DSM)**

1. Abrir Web Station en DSM
2. Verificar que el servicio esté corriendo
3. El frontend debería estar accesible en: `http://tu-nas.local/youtube-clear-view/`

**IMPORTANTE: Configurar config.js**

Antes de desplegar el frontend, editar `frontend/config.js`:

```javascript
const APP_CONFIG = {
  API_BASE_URL: 'http://192.168.1.100:5550/api',  // IP real de tu NAS
  // ... resto de configuración
};
```

### Verificación Final

1. **Backend funcionando:**
   ```bash
   curl http://tu-nas.local:5550/api/health
   ```

2. **Frontend accesible:**
   - Abrir navegador: `http://tu-nas.local/youtube-clear-view/`
   - Debería cargar la interfaz

3. **CORS configurado:**
   - Abrir consola del navegador (F12)
   - No debería haber errores de CORS
   - Si hay errores, revisar CORS_ORIGINS en backend/.env

4. **Crear primer usuario:**
   - Click en "Nuevo usuario"
   - Ingresar nombre
   - Debería poder loguearse

### Troubleshooting

**Error CORS:**
- Verificar que CORS_ORIGINS en .env incluya la URL del frontend
- Ejemplo: `CORS_ORIGINS=http://192.168.1.100,http://nas.local`
- Reiniciar backend después de cambiar .env

**Backend no responde:**
- Verificar que el puerto 5550 no esté bloqueado por firewall
- Ver logs: `docker logs youtube-clear-view-backend` o `journalctl -u youtube-clear-view`

**Frontend no carga:**
- Verificar permisos de archivos en /volume1/web/youtube-clear-view/
- Verificar que Web Station esté corriendo
- Verificar config.js tenga la URL correcta del backend

**YouTube API no funciona:**
- Verificar que YOUTUBE_API_KEY en .env sea válida
- Verificar cuota de API en Google Cloud Console

---

## 🎓 Notas Adicionales

### Mejoras Futuras Sugeridas

1. **Cache de datos de YouTube**: implementar Redis para cachear respuestas de la API
2. **WebSockets**: actualizaciones en tiempo real cuando hay nuevos videos
3. **PWA**: convertir en Progressive Web App para instalación en dispositivos
4. **Background jobs**: Celery para refrescar videos automáticamente cada X horas
5. **Análisis**: estadísticas de visualización, canales más vistos, etc.
6. **Exportar/Importar**: suscripciones desde YouTube oficial
7. **Modo offline**: service worker para ver videos previamente cargados sin conexión
8. **Subtítulos**: integración con API de subtítulos de YouTube
9. **Playlists**: crear y gestionar playlists personalizadas
10. **Notificaciones**: avisar cuando canales favoritos suben videos

### Performance Tips

- Implementar lazy loading de imágenes
- Comprimir thumbnails
- Paginación en todos los endpoints
- Índices en campos de búsqueda frecuente
- Conexión pooling para SQLite
- Minificar CSS/JS para producción
- CDN para assets estáticos si aplica

### Seguridad

- Rate limiting en endpoints públicos
- Validación de inputs (server-side y client-side)
- CSRF protection si usas formularios
- HTTPS en producción (configurar en Nginx)
- Sanitización de datos de YouTube API
- No exponer información sensible en errores

---

## YouTube

- YouTube API Docs: https://developers.google.com/youtube/v3

---

**¡Proyecto listo para comenzar!** 🚀

Sigue los pasos en orden, usa los prompts para codex en cada fase, y no olvides hacer commits descriptivos siguiendo Conventional Commits.
