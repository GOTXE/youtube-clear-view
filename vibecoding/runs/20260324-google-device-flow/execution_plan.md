# Execution Plan — Google Device Flow Onboarding

## Goal

Implementar alta de usuarios via Google OAuth Device Flow + bootstrap install_locked

## Current State

- status: implemented
- current_step: review complete

## Decisions Taken

- Coincidencia email sin google_user_id → vinculación guiada (pedir confirmación)
- Wizard local: password obligatorio, passkey opcional después
- QR: generado en frontend (solo contiene URL pública de Google)
- Polling: frontend → backend → Google (tokens nunca expuestos al frontend)
- Bootstrap timeout: 5 minutos, reinicio via Docker
- Bloque B (página legal) pospuesto
- Campo identidad Google: mantener `google_user_id` existente

## Steps — Bloque A: install_locked bootstrap (timeout sobre bootstrap existente)

Nota: bootstrap ya existe (admin_bootstrap.py, /api/bootstrap/admin, frontend bootstrap view).
Se usa SiteSetting como store para el timestamp — no se necesita tabla nueva.

- [x] A1 :: backend: lógica timeout en admin_bootstrap.py (reset_bootstrap_window, is_bootstrap_locked) usando SiteSetting :: owner=coder :: validation=funciones correctas
- [x] A2 :: backend: integrar timeout en endpoint /api/bootstrap/admin + /api/bootstrap/status + /api/auth/provider :: owner=coder :: validation=endpoints respetan timeout
- [x] A3 :: frontend: mostrar estado locked/countdown en vista bootstrap :: owner=coder :: validation=UI muestra timeout
- [x] A4 :: tests: test_bootstrap_timeout.py :: owner=tester_author :: validation=tests pasan
- [x] A5 :: review bloque A :: owner=reviewer :: validation=sin findings bloqueantes

## Steps — Bloque C: Google Device Flow

- [x] C1 :: backend: servicio device flow en google_oauth.py (request_device_code, poll_device_token) :: owner=coder :: validation=funciones implementadas con manejo de errores
- [x] C2 :: backend: endpoints POST /api/auth/google/device/start + GET /api/auth/google/device/status :: owner=coder :: validation=endpoints responden correctamente
- [x] C3 :: frontend: vista device-flow en login-page.js (user_code, URL, QR, polling) :: owner=coder :: validation=UI muestra código y QR, polling funciona
- [x] C4 :: tests: test_device_flow.py (start, polling states, token storage) :: owner=tester_author :: validation=tests pasan
- [x] C5 :: review bloque C :: owner=reviewer :: validation=sin findings bloqueantes

## Steps — Bloque D: Vinculación + Wizard local

- [x] D1 :: backend: lógica vinculación por google_user_id con fallback email+confirmación :: owner=coder :: validation=vinculación correcta sin duplicados
- [x] D2 :: backend: endpoint POST /api/auth/google/complete-setup adaptado para device flow :: owner=coder :: validation=wizard crea cuenta local
- [x] D3 :: frontend: flujo confirmación identidad Google + wizard username/password :: owner=coder :: validation=UI completa el flujo
- [x] D4 :: tests: test_account_linking.py (nuevo usuario, email match, google_user_id match) :: owner=tester_author :: validation=tests pasan
- [x] D5 :: review bloque D :: owner=reviewer :: validation=sin findings bloqueantes

## Steps — Bloque E: Revocación y revinculación

- [x] E1 :: backend: endpoint revinculación desde cuenta de usuario (reutilizar device flow) :: owner=coder :: validation=revinculación funciona
- [x] E2 :: backend: detección token inválido → marcar google_auth_status=needs_reauth :: owner=coder :: validation=estado actualizado correctamente
- [x] E3 :: frontend: opción "Revincular YouTube" en menú usuario :: owner=coder :: validation=botón visible y funcional
- [x] E4 :: tests: test_revocation.py :: owner=tester_author :: validation=tests pasan
- [x] E5 :: review bloque E :: owner=reviewer :: validation=sin findings bloqueantes

## Commit Strategy

Un commit por cada paso (A1, A2, A3...). Mensajes con prefijo convencional:
- `feat: add install_locked app_state model and migration` (A1)
- `feat: add bootstrap guard middleware` (A2)
- etc.

## Blockers

- Bloque B (página legal) pospuesto — no bloquea implementación técnica

## Next Action

- coder: empezar A1
