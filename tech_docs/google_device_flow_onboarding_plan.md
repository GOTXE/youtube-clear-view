# Google Device Flow Onboarding Plan

Estado: `EN CURSO`

Fecha: `2026-03-24`

Objetivo:
- permitir alta inicial de usuarios Google en YTCV sin depender de `localhost` ni de callbacks OAuth web clásicos
- mantener YTCV como app self-hosted en NAS/LAN
- exigir que cada usuario/instancia use sus propias credenciales de Google Cloud / YouTube Data API
- conservar login diario local con usuario/password de BBDD

## 0. Base ya confirmada

Estado: `COMPLETADO`

### 0.1. Cifrado de tokens en reposo

Confirmado en código:
- `backend/app/models/user.py`
- `backend/app/services/auth_security.py`
- `backend/tests/test_auth.py`

Conclusión:
- `google_access_token` cifrado en reposo
- `google_refresh_token` cifrado en reposo
- `google_scopes` cifrado en reposo
- cifrado usando `Fernet`

### 0.2. Viabilidad oficial del flujo

Confirmado en documentación oficial:
- Google / YouTube soportan OAuth 2.0 para dispositivos de entrada limitada
- el flujo soporta scopes:
  - `openid`
  - `profile`
  - `email`
  - `https://www.googleapis.com/auth/youtube`
  - `https://www.googleapis.com/auth/youtube.readonly`

Fuentes oficiales:
- `https://developers.google.com/youtube/v3/guides/auth/devices`
- `https://developers.google.com/identity/gsi/web/guides/devices`
- `https://developers.google.com/youtube/terms/developer-policies`

## 1. Principios de diseño

Estado: `COMPLETADO`

### 1.1. Google no será el login diario de la app

Decisión:
- Google se usa para:
  - crear la cuenta inicial
  - obtener tokens YouTube
- el login posterior en otros dispositivos será:
  - `usuario + password` local

### 1.2. Cada usuario/instancia usa sus propias credenciales

Decisión:
- no se embeben credenciales del autor en el repo
- no se comparten API keys / client secrets
- cada persona que use YTCV deberá crear:
  - su propio `API Project`
  - sus propias credenciales OAuth
  - su propia API key si la app la necesita

### 1.3. Identidad Google estable

Decisión:
- vincular por `google_sub`
- nunca por nombre visible
- email puede ser apoyo, pero no identificador principal

## 2. Fase bootstrap de instalación

Estado: `IMPLEMENTADO`

### Objetivo

Sustituir cualquier idea de `admin/admin` por un estado inicial protegido.

### Comportamiento esperado

- la app arranca en modo `install_locked`
- solo se permite entrar al asistente inicial
- el usuario debe definir:
  - `admin_username`
  - `admin_password`
- la UI debe avisar claramente:
  - que es una ventana temporal de instalación
  - que debe completarse antes del timeout

### Protección temporal

- timeout corto configurable
- si el tiempo vence:
  - el sistema queda bloqueado
  - la UI muestra:
    - `Tiempo excedido para primer login. Reinicia para terminar la instalación.`
- para continuar:
  - reiniciar stack / contenedor
  - se genera una nueva ventana de instalación

### Completion

- no existe usuario/clave por defecto fija
- la instalación no queda expuesta indefinidamente
- el usuario entiende bien el estado temporal de bootstrap

## 3. Página pública legal e informativa

Estado: `PENDIENTE`

### Objetivo

Crear una web pública dentro de YTCV con información de privacidad, uso API y revocación.

### Contenido mínimo

- YTCV usa `YouTube API Services`
- enlace a Términos de YouTube
- enlace a Google Privacy Policy
- política de privacidad propia de YTCV
- explicación clara de:
  - qué datos se solicitan
  - qué datos se almacenan
  - cómo se usan
  - cómo se eliminan o desvinculan
- explicación clara de:
  - revocación de consentimiento
  - revinculación de cuenta
- nota explícita:
  - cada usuario debe usar sus propias credenciales/API project
  - YTCV no distribuye credenciales compartidas

### Dónde debe aparecer

- accesible desde login/onboarding
- accesible desde footer
- enlazada desde GitHub README / documentación pública

### Completion

- web informativa pública operativa
- README / docs públicas alineadas
- base suficiente para consentimiento y transparencia

## 4. Alta inicial con Google Device Flow

Estado: `IMPLEMENTADO`

### Objetivo

Permitir crear cuenta con Google sin callback web clásico.

### UX mínima

Pantalla de acceso:
- `Entrar`
- `Crear cuenta con Google`

Flujo:
- solicitar `device_code`
- mostrar:
  - `user_code`
  - URL de verificación
  - QR
- polling del backend
- cuando se autoriza:
  - obtener tokens
  - obtener identidad Google
  - pasar a confirmación final

### Completion

- alta inicial funciona desde NAS/LAN
- no depende de `localhost`
- QR presente

## 5. Modelo de vinculación de cuenta

Estado: `IMPLEMENTADO`

### Reglas de identidad

- si existe usuario con el mismo `google_sub`:
  - actualizar tokens
  - no crear usuario nuevo
- si no existe `google_sub` pero hay mismo email:
  - decidir si se permite vinculación guiada o automática
- si solo coincide el nombre visible:
  - no vincular

### Confirmación final

Tras autorización:
- mostrar:
  - avatar
  - nombre
  - email
  - confirmación explícita antes de crear/vincular

### Completion

- no hay duplicados por nombre
- la asociación está basada en un identificador estable

## 6. Wizard local posterior

Estado: `IMPLEMENTADO`

### Objetivo

Tras Google, convertir la identidad en una cuenta local YTCV utilizable desde cualquier dispositivo.

### Flujo

- Google autorizado
- pantalla de confirmación
- wizard local:
  - `username`
  - `password`
- cuenta lista

### Resultado

- siguientes logins en otros dispositivos:
  - solo con usuario/password local
- no hace falta repetir Google para el resto de dispositivos del hogar

### Completion

- Google se usa una vez para el alta/vinculación inicial
- login posterior es local

## 7. Revocación y revinculación

Estado: `IMPLEMENTADO`

### Alcance acordado

- solo en cuenta de usuario
- no en gestor

### Requisitos

- opción visible:
  - `Revincular cuenta de YouTube`
- si Google revoca acceso o el vínculo queda inválido:
  - marcarlo como inválido
  - pedir revinculación
- gestor no administrará vínculos Google
- gestor sigue centrado en administración local de usuarios

### Completion

- ciclo de vida completo del vínculo Google desde la cuenta del usuario

## 8. Persistencia y seguridad de tokens

Estado: `COMPLETADO EN PARTE`

### Ya existente

- cifrado en reposo con `Fernet`
- expiración del access token ya gestionada parcialmente
- unlink Google ya existe

### Pendiente

- revisar modelo para `google_sub`
- revisar si conviene guardar datos auxiliares de identidad:
  - email Google
  - nombre visible
  - avatar
- revisar manejo de expiración / revocación en device flow

### Completion

- tokens persistidos con trazabilidad completa
- identidad Google estable guardada correctamente

## 9. Cumplimiento y riesgos

Estado: `EN SEGUIMIENTO`

### Riesgo 1: distribución pública

Si YTCV se publica en GitHub como app que terceros instalan, el riesgo no está en GitHub en sí, sino en que:
- el cliente usa scopes sensibles de YouTube
- Google puede exigir transparencia y controles

Mitigación:
- no compartir credenciales del autor
- cada usuario usa sus propias credenciales
- Terms + Privacy + revocación visibles

### Riesgo 2: refresh token

Riesgo:
- si se filtra, permite renovar acceso

Estado actual:
- cifrado en reposo confirmado

Mitigación adicional:
- mantener cifrado
- revisar rotación/revocación
- UI clara para desvincular

### Riesgo 3: mala vinculación de identidad

Riesgo:
- enlazar por nombre visible o criterio inestable

Mitigación:
- usar `google_sub`

### Riesgo 4: bootstrap expuesto

Riesgo:
- dejar instalación inicial abierta indefinidamente

Mitigación:
- `install_locked`
- timeout
- bloqueo hasta reinicio

## 10. Fases de implementación

Estado: `PENDIENTE`

### Bloque A — `IMPLEMENTADO`

- modo `install_locked` con timeout configurable (5 min default)
- bootstrap admin temporal via SiteSetting
- countdown + mensajes de timeout en frontend

### Bloque B — `POSPUESTO`

- página pública legal/informativa
- enlaces en footer/login/GitHub docs

### Bloque C — `IMPLEMENTADO`

- backend device flow (google_oauth.py + endpoints)
- UI de código + URL + QR (generado backend con qrcode lib)
- polling frontend → backend → Google
- CSRF protection, session cleanup, interval cap

### Bloque D — `IMPLEMENTADO`

- vinculación por `google_user_id` con fallback email + confirmación
- creación cuenta local con username + password
- wizard local reutilizado para device flow

### Bloque E — `IMPLEMENTADO`

- revinculación desde cuenta de usuario via device flow
- detección de token inválido → needs_reauth (ya existía)

## 11. Pendientes abiertos

Estado: `CERRADOS (excepto legal)`

- ~~decidir política exacta si coincide email pero no `google_sub`~~ → vinculación guiada con confirmación, añadir `google_user_id` al usuario existente
- ~~decidir si el wizard local debe obligar password inmediatamente o permitir passkey después~~ → password obligatorio, passkey opcional después (ya implementado en menú)
- decidir copy final de la página legal → **POSPUESTO** (Bloque B no se implementa en esta iteración)
- ~~decidir si el QR se genera backend o frontend~~ → frontend (solo contiene URL pública de Google, sin datos sensibles)

Decisiones adicionales:
- polling: frontend → backend → Google (tokens nunca expuestos al frontend, client_secret solo en backend)
- bootstrap timeout: 5 minutos, reinicio via Docker
- campo identidad Google: mantener `google_user_id` existente (no crear `google_sub`)
- orden implementación: A (install_locked) → C (device flow) → D (vinculación+wizard) → E (revocación)

## 12. Criterio para empezar implementación

Estado: `EN CURSO`

Decisiones cerradas:
- ✅ política de coincidencia por email
- ✅ wizard local: password obligatorio
- ✅ QR: frontend
- ⏸️ copy de instalación bloqueada — no bloquea implementación técnica
- ⏸️ alcance mínimo web legal — pospuesto (Bloque B)
