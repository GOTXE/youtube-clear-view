# W.I.P.

[Read this in English →](README.md)

# YT Clear View (YTCV)

**Una vista limpia y cronologica de tus suscripciones de YouTube.  
Sin recomendaciones. Sin ruido. Solo los canales que sigues.**

## Capturas

![YT Clear View](screenshots/YT-Clear-View.jpg)

---

## El problema

Hoy, el feed de Inicio de YouTube suele estar dominado por:
- Videos de canales que no sigues
- Recomendaciones del algoritmo
- Ranking guiado por engagement (CTR, tiempo de visualizacion, tendencias)

Como resultado, **el contenido de tus propias suscripciones queda enterrado**.

---

## La solucion

YTCV te da una **linea temporal controlada** construida solo con:
- Los canales a los que estas suscrito
- Un orden cronologico real
- Tus propias reglas de filtrado y categorizacion

Nada mas.

---

## Que hace esta app

- Se conecta a **tu cuenta de YouTube** usando la API oficial (OAuth)
- Descarga videos (y Shorts de tus suscripciones) **solo de tus canales suscritos**
- Los muestra en una **linea temporal limpia y sin distracciones**
- Permite filtrar y categorizar

Sigues usando YouTube, pero dejas de consumir lo que empuja el algoritmo.

---

## Que NO hace esta app

- No muestra el feed de Inicio de YouTube
- No muestra "Recomendado para ti"
- No muestra tendencias ni contenido sugerido
- No fuerza sugerencias basadas en autoplay

Esta app **no reemplaza YouTube**. Reemplaza la **capa de recomendaciones**.

---

## Sobre el algoritmo (importante)

YouTube usa multiples algoritmos. Este proyecto elimina intencionadamente solo uno:

| Capa | Se usa |
|---|---|
| Motor de recomendaciones (Inicio / Siguiente) | No |
| Tendencias / contenido sugerido | No |
| Timeline de suscripciones | Si (controlado por la app) |
| Metadatos oficiales | Si (via API) |

---

## Por que la API oficial de YouTube (OAuth)

Este proyecto usa YouTube Data API v3 con autenticacion OAuth:
- Acceso estable a tus suscripciones reales
- Metadatos precisos
- Mantenibilidad a largo plazo
- Cumplimiento de los terminos de YouTube

Esto **no** es una herramienta basada en scraping.

---

## Requisitos (alto nivel)

- Una cuenta de Google
- Un proyecto en Google Cloud con YouTube Data API v3 habilitada
- Credenciales OAuth (Client ID / Secret)

La instalacion y el despliegue estan en [`docs/`](docs/).

---

## Para quien es

- Usuarios cansados de feeds guiados por recomendaciones
- Personas que quieren ver solo lo que han elegido
- Cualquiera que quiera YouTube sin ruido

---

## Stack (breve)

- Backend: Python (Flask)
- Frontend: HTML / CSS / Vanilla JS
- Auth: YouTube Data API v3 (OAuth)
- Almacenamiento: SQLite

---

## Documentacion

- API reference: [docs/api-reference.md](docs/api-reference.md)
- Architecture: [docs/architecture.md](docs/architecture.md)
- Deployment: [docs/deployment.md](docs/deployment.md)
- Development: [docs/development.md](docs/development.md)

---

## Licencia

MIT. Ver [LICENSE](LICENSE) o la referencia oficial en [choosealicense.com](https://choosealicense.com/licenses/mit/).
