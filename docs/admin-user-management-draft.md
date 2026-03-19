# Admin User Management Draft

## Status

Draft abierto. Este documento define una primera propuesta para ampliar el panel de admin con gestión de usuarios.
Se deja intencionadamente abierto para añadir más operaciones y reglas más adelante.

## Objetivo

Permitir que el administrador del sitio gestione cuentas desde la UI admin sin tocar directamente la base de datos.

Casos iniciales:

- listar usuarios
- deshabilitar o reactivar cuenta
- eliminar cuenta
- resetear password local
- forzar cambio de password en el siguiente login

## Motivación

El sistema ya tiene autenticación híbrida:

- bootstrap inicial por Google OAuth
- accesos posteriores por login local, passkey o pairing

Hace falta una superficie admin para soporte operativo:

- bloquear usuarios temporalmente
- recuperar acceso si olvidan la password local
- limpiar cuentas obsoletas
- inspeccionar rápidamente el estado de cada usuario

## Alcance funcional inicial

### 1. Listado de usuarios

Nueva sección en admin:

- tabla o lista de usuarios
- búsqueda por `username` o `email`
- orden por actividad reciente o por nombre

Campos visibles recomendados:

- `id`
- `username`
- `display_name`
- `email`
- `auth_provider`
- `google_auth_status`
- `has_password`
- `totp_enabled`
- `is_admin`
- `is_active`
- `must_change_password`
- `session_created_at`
- número de dispositivos

### 2. Deshabilitar cuenta

Acción:

- marcar usuario como inactivo

Efecto esperado:

- no puede iniciar sesión local
- no puede completar login pairing
- si ya tiene sesión activa, decidir si se invalida en el acto o en la siguiente comprobación

Decisión recomendada:

- invalidar sesión activa al deshabilitar para que el bloqueo sea inmediato

### 3. Reactivar cuenta

Acción:

- volver a marcar usuario como activo

Efecto esperado:

- puede volver a usar login local y demás métodos permitidos

### 4. Reset de password local

Acción admin:

- fijar una password temporal nueva

Efecto esperado:

- se guarda nueva `password_hash`
- se marca `must_change_password = true`

Caso de uso:

- usuario olvidó la password local
- el admin le entrega una temporal
- el usuario entra una vez y queda obligado a cambiarla

### 5. Cambio obligatorio de password

El backend debe poder exigir cambio de password justo después del login local.

Flujo propuesto:

1. el usuario inicia sesión con password temporal
2. backend autentica correctamente
3. backend responde con flag `password_change_required = true`
4. frontend muestra modal/pantalla bloqueante de cambio de password
5. hasta completar el cambio no se carga la app normal

### 6. Eliminar cuenta

Acción admin:

- borrado duro o blando, por decidir

Recomendación inicial:

- empezar con borrado duro solo si se controla bien la cascada en tablas relacionadas
- si no, usar soft delete primero

Entidades a revisar:

- `User`
- `UserChannel`
- `Theme`
- `ThemeChannel`
- `WatchedVideo`
- `UserDevice`
- `UserPasskey`
- `LoginPairing`
- `UserSettings`
- cualquier estado MFA o tokens Google persistidos

## Cambios de modelo propuestos

En `User`:

- `is_active = db.Column(db.Boolean, nullable=False, default=True)`
- `must_change_password = db.Column(db.Boolean, nullable=False, default=False)`
- opcional futuro:
  - `disabled_at`
  - `disabled_reason`
  - `password_reset_by_admin_at`

## Cambios backend propuestos

### Nuevos endpoints admin

#### GET `/api/admin/users`

Devuelve listado resumido de usuarios.

Opciones futuras:

- `q` para búsqueda
- paginación
- filtros (`active`, `has_password`, `provider`, `mfa`)

#### POST `/api/admin/users/<user_id>/disable`

Deshabilita cuenta.

#### POST `/api/admin/users/<user_id>/enable`

Reactiva cuenta.

#### POST `/api/admin/users/<user_id>/reset-password`

Body propuesto:

```json
{
  "temporary_password": "TempPassword123!"
}
```

Efecto:

- actualiza password
- marca `must_change_password = true`

#### DELETE `/api/admin/users/<user_id>`

Elimina usuario.

## Cambios en login local

En `POST /api/auth/login`:

- si `is_active == false`:
  - rechazar login
- si login válido y `must_change_password == true`:
  - responder con payload especial

Payload propuesto:

```json
{
  "authenticated": false,
  "password_change_required": true,
  "user_id": 12,
  "username": "alice"
}
```

Alternativa:

- crear sesión limitada temporal y permitir solo `POST /api/auth/profile/password`

Recomendación:

- usar una sesión limitada temporal similar al patrón de MFA challenge
- así se evita dejar la app completamente autenticada antes del cambio de password

## Cambios frontend propuestos

### Panel admin

Nueva subsección:

- `User management`

UI recomendada:

- tabla/lista con filtros
- menú por usuario con acciones:
  - disable
  - enable
  - reset password
  - delete

### Login flow

Si backend devuelve `password_change_required`:

- mostrar modal o vista bloqueante
- pedir:
  - password actual temporal
  - nueva password
  - confirmación

Condición:

- no dejar navegar a la app hasta resolverlo

## Reglas y seguridad

- el admin no debe ver hashes ni secretos
- el reset de password debe registrarse en logs
- eliminar cuenta debe pedir confirmación fuerte
- impedir que un admin se deshabilite o elimine a sí mismo por accidente
- revisar qué hacer con el último admin activo

Recomendación:

- bloquear:
  - auto-delete
  - auto-disable
  - quitar privilegios al último admin sin otro admin alternativo

## Preguntas abiertas

- ¿borrado duro o soft delete?
- ¿debe el reset de password invalidar sesiones activas?
- ¿el admin puede cambiar `username` y `email`?
- ¿debe permitirse desvincular Google desde admin?
- ¿debe permitirse revocar passkeys de un usuario?
- ¿se necesita auditoría visible de cambios admin sobre usuarios?
- ¿hay que permitir creación manual de cuentas desde admin?

## Implementación sugerida por fases

### Fase 1

- columnas `is_active` y `must_change_password`
- listado admin de usuarios
- disable / enable
- reset password + cambio obligatorio en siguiente login

### Fase 2

- delete account
- invalidación de sesiones activas
- guardas para último admin

### Fase 3

- filtros avanzados
- auditoría
- gestión admin de passkeys / MFA / Google linkage

## Notas de prueba

Escenarios mínimos a cubrir:

- usuario activo puede iniciar sesión
- usuario deshabilitado no puede iniciar sesión
- reset password marca `must_change_password`
- login con password temporal obliga a cambiar password
- tras cambiar password se limpia `must_change_password`
- delete elimina o desactiva todas las relaciones según la política elegida
- no se puede romper el acceso del último admin
