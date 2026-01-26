# Sistema de Versionado SemVer - youtube-clear-view

## Estado Actual

**Versión actual**: `v0.10.0`
**Branch**: `la que esté usando el usuario`
**Fase**: Pre-release (0.x.x) - Desarrollo activo

---

## 1. Formato de Versión

```
v {MAJOR} . {MINOR} . {PATCH} - {PRERELEASE} . {INCREMENT}
  └─0       └─9       └─0       └─alpha/beta/rc └─1,2,3...
```

**Ejemplos válidos**:
- `v0.9.0` - Versión estable
- `v0.9.0-alpha.1` - Primera alpha de 0.9.0
- `v0.9.0-beta.2` - Segunda beta de 0.9.0
- `v0.9.0-rc.1` - Release candidate 1
- `v1.0.0` - Primera versión estable en producción

---

## 2. Reglas de Numeración (Pre-release 0.x.x)

Mientras el proyecto esté en fase 0.x.x:

| Cambio | Bump | Ejemplo | Cuándo usar |
|--------|------|---------|-------------|
| **Breaking change** | MINOR | 0.8.1 → 0.9.0 | Cambios en DB schema, API incompatible |
| **New feature** | MINOR | 0.8.1 → 0.9.0 | Nueva funcionalidad (categorías, rating, OAuth) |
| **Bug fix** | PATCH | 0.8.1 → 0.8.2 | Solo correcciones, no features |
| **Hot fix crítico** | PATCH | 0.8.1 → 0.8.2 | Security fix, crash fix |

> **Nota**: En fase 0.x.x, MAJOR se mantiene en 0. Solo sube a 1.0.0 cuando esté listo para producción.

---

## 2.1. Cómo los Fixes Modifican la Versión

Los **fixes** incrementan diferentes partes de la versión dependiendo del contexto actual:

### 1️⃣ Fix en Versión Estable (sin prerelease)

**Situación**: Ya tienes una versión estable (ej: `v0.9.0`) en `main` y encuentras un bug.

**Acción**: Incrementar **PATCH** (tercer dígito)

```bash
v0.9.0 → v0.9.1  (primer fix)
v0.9.1 → v0.9.2  (segundo fix)
v0.9.2 → v0.9.3  (tercer fix)
```

**Ejemplos**:
```bash
# Bug fix normal
git tag -a v0.9.1 -m "fix: resolve OAuth token refresh bug"

# Security hotfix
git tag -a v0.9.2 -m "fix(security): sanitize channel titles to prevent XSS"

# Critical crash fix
git tag -a v0.9.3 -m "fix: prevent infinite loop on error response"
```

---

### 2️⃣ Fix Durante Pre-release (alpha/beta/rc)

**Situación**: Estás en una versión pre-release (ej: `v0.9.0-beta.2`) y encuentras bugs durante testing.

**Acción**: Incrementar el **número de prerelease**, NO el PATCH

```bash
v0.9.0-beta.2 → v0.9.0-beta.3  (siguiente beta con fixes)
```

**Razón**: Aún no has lanzado `v0.9.0` estable, los fixes son parte del proceso de estabilización de esa versión.

**Ejemplos según fase**:
```bash
# Fix en alpha
v0.9.0-alpha.1 → v0.9.0-alpha.2
git tag -a v0.9.0-alpha.2 -m "fix: correct migration script for categories table"

# Fix en beta
v0.9.0-beta.1 → v0.9.0-beta.2
git tag -a v0.9.0-beta.2 -m "fix: star rating not persisting on page refresh"

# Fix en RC
v0.9.0-rc.1 → v0.9.0-rc.2
git tag -a v0.9.0-rc.2 -m "fix: category color contrast in dark mode"
```

---

### 3️⃣ Workflow de Hotfix (después de stable)

**Situación**: Lanzaste `v0.9.0` estable, luego encuentras un bug crítico.

**Acción**: Crear branch de hotfix, fix, y tag PATCH

```bash
v0.9.0 (stable) → v0.9.1 (hotfix)
```

**Proceso completo**:
```bash
# 1. Crear branch de hotfix desde el tag estable
git checkout -b hotfix/0.9.1 v0.9.0

# 2. Hacer el fix
git commit -m "fix: resolve OAuth token expiration bug"

# 3. Crear tag de fix (PATCH bump)
git tag -a v0.9.1 -m "fix: resolve OAuth token expiration bug

Critical fix for OAuth authentication flow.
Token expiration was not being handled correctly."

# 4. Merge a main
git checkout main
git merge hotfix/0.9.1
git push origin main v0.9.1

# 5. Merge también a desarrollo para no perder el fix
git checkout desarrollo_paso_31
git merge hotfix/0.9.1
git push origin desarrollo_paso_31
```

---

### Tabla Resumen: Qué Hacer con Fixes

| Estado Actual | Tipo de Fix | Nueva Versión | Bump |
|---------------|-------------|---------------|------|
| `v0.9.0-alpha.1` | Bug encontrado en testing | `v0.9.0-alpha.2` | Prerelease increment |
| `v0.9.0-beta.2` | Bug encontrado en testing | `v0.9.0-beta.3` | Prerelease increment |
| `v0.9.0-rc.1` | Bug crítico antes de release | `v0.9.0-rc.2` | Prerelease increment |
| `v0.9.0` (stable) | Bug después de release | `v0.9.1` | **PATCH bump** |
| `v0.9.1` | Otro bug | `v0.9.2` | **PATCH bump** |
| `v0.9.2` | Security fix urgente | `v0.9.3` | **PATCH bump** |

---

### Ejemplo Práctico: Tu Caso Actual

**Estado actual**: `v0.10.0`

#### Si encuentras bugs ahora (durante beta):

```bash
# Opción A: Continuar con beta (si aún falta testing)
v0.9.0-beta.2 → v0.9.0-beta.3

git commit -m "fix: correct category assignment logic"
git tag -a v0.9.0-beta.3 -m "fix: category assignment and UI tweaks"
git push origin v0.9.0-beta.3
```

```bash
# Opción B: Pasar a RC (si solo quedan fixes menores)
v0.9.0-beta.2 → v0.9.0-rc.1

git commit -m "fix: minor UI adjustments"
git tag -a v0.9.0-rc.1 -m "chore: prepare v0.9.0 release candidate"
git push origin v0.9.0-rc.1
```

```bash
# Opción C: Release estable (si no hay más bugs)
v0.9.0-beta.2 → v0.9.0

git checkout main
git merge desarrollo_paso_31
git tag -a v0.9.0 -m "Release v0.9.0: Category classification system"
git push origin main v0.9.0
```

#### Después de lanzar v0.9.0 estable:

```bash
# Cualquier fix será PATCH bump
v0.9.0 → v0.9.1  (primer fix post-release)
v0.9.1 → v0.9.2  (segundo fix)
```

---

### Timeline Ejemplo de Fixes

**Escenario realista de desarrollo**:

```
📅 2025-01-20: v0.9.0-alpha.1 (modelos + migrations)
                ↓
           (encuentra bug en migration)
                ↓
📅 2025-01-21: v0.9.0-alpha.2 (fix migration)
                ↓
           (completa backend + frontend)
                ↓
📅 2025-01-25: v0.9.0-beta.1 (feature completo)
                ↓
           (testing encuentra bug en rating)
                ↓
📅 2025-01-26: v0.9.0-beta.2 (fix rating persistence)
                ↓
           (testing encuentra bug en dark mode)
                ↓
📅 2025-01-27: v0.9.0-beta.3 (fix dark mode colors)
                ↓
           (todos los tests pasan)
                ↓
📅 2025-01-28: v0.9.0-rc.1 (release candidate)
                ↓
           (validación final - todo OK)
                ↓
📅 2025-01-30: v0.9.0 (STABLE RELEASE) 🎉
                ↓
           (usuario reporta bug en producción)
                ↓
📅 2025-02-01: v0.9.1 (hotfix crítico)
                ↓
           (otro bug menor)
                ↓
📅 2025-02-03: v0.9.2 (segundo hotfix)
```

---

### Regla Práctica: Pregúntate

**Al encontrar un bug, pregúntate**:

1. **¿Ya lancé una versión estable sin sufijo (-alpha/-beta/-rc)?**
   - ✅ **Sí** → PATCH bump (0.9.0 → 0.9.1)
   - ❌ **No, estoy en pre-release** → Incrementa prerelease (beta.2 → beta.3)

2. **¿El fix rompe compatibilidad con versiones anteriores?**
   - ✅ **Sí, breaking change** → MINOR bump (o MAJOR si estás en 1.x.x)
   - ❌ **No, backward compatible** → PATCH bump

3. **¿Es un fix trivial o crítico?**
   - **Trivial** (typo, log message): Puede esperar al siguiente release
   - **Crítico** (crash, security): Hotfix inmediato con PATCH bump

---

### Casos Especiales

#### Fix que agrega funcionalidad menor

Si el fix requiere agregar una pequeña función auxiliar:

```bash
# ✅ Correcto - sigue siendo fix
git tag -a v0.9.1 -m "fix: add missing validation to prevent crash"

# ❌ Incorrecto - si agrega feature real
# Esto debería ser v0.10.0, no v0.9.1
```

**Criterio**: Si el cambio es visible para el usuario como nueva funcionalidad → MINOR bump, no PATCH.

#### Múltiples fixes acumulados

Puedes combinar varios fixes pequeños en un solo PATCH:

```bash
# Varios commits de fix
git commit -m "fix: OAuth token refresh"
git commit -m "fix: dark mode contrast"
git commit -m "fix: rating persistence"

# Un solo tag PATCH que los agrupa
git tag -a v0.9.1 -m "fix: multiple bug fixes

- OAuth token refresh handling
- Dark mode color contrast improved
- Star rating persistence on reload"
```

---

## 3. Ciclo de Pre-release

### Alpha (`-alpha.N`)

**Propósito**: Feature base implementada, puede tener bugs
**Estado**: Backend funcional, pruebas iniciales
**Testing**: Interno, desarrollador únicamente

**Cuándo crear**:
- Modelos de datos completados
- Migrations funcionando
- Tests básicos pasando

**Ejemplo**:
```bash
git tag -a v0.9.0-alpha.1 -m "feat: add category models and migrations"
git push origin v0.9.0-alpha.1
```

---

### Beta (`-beta.N`)

**Propósito**: Feature completa, testing activo
**Estado**: Backend + Frontend funcional, buscando bugs
**Testing**: Equipo ampliado, usuarios de testing

**Cuándo crear**:
- Funcionalidad completa end-to-end
- UI implementada y funcional
- Integración frontend-backend estable
- Documentación básica disponible

**Ejemplo**:
```bash
git tag -a v0.9.0-beta.1 -m "feat: complete category UI and rating system"
git push origin v0.9.0-beta.1
```

---

### RC - Release Candidate (`-rc.N`)

**Propósito**: Todo completo, solo ajustes finales
**Estado**: Tests pasados, docs actualizadas, listo para merge a main
**Testing**: Pruebas finales, validación completa

**Cuándo crear**:
- Todos los tests pasando (unit + integration)
- Performance validado
- Documentación completa
- Sin bugs conocidos críticos
- Listo para merge a `main`

**Ejemplo**:
```bash
git tag -a v0.9.0-rc.1 -m "chore: prepare v0.9.0 release - category system"
git push origin v0.9.0-rc.1
```

---

### Stable (sin sufijo)

**Propósito**: Versión oficial en producción
**Estado**: Merge a `main` completado
**Testing**: Validación final en ambiente similar a producción

**Cuándo crear**:
- Después de merge exitoso a `main`
- Deploy en ambiente staging/producción exitoso
- README y CHANGELOG actualizados

**Ejemplo**:
```bash
# Después de merge a main
git checkout main
git tag -a v0.9.0 -m "Release v0.9.0: Automatic channel categorization and rating system"
git push origin v0.9.0
```

---

## 4. Workflow Típico

### Desarrollo de Feature Nueva

```
desarrollo_paso_31 (branch de desarrollo):

1. Desarrollo inicial
   ├─ Implementar modelos
   ├─ Crear migrations
   └─ Tests básicos
   → git tag v0.X.0-alpha.1

2. Completar backend
   ├─ Services completos
   ├─ Routes y endpoints
   └─ Tests de integración
   → git tag v0.X.0-alpha.2 (o beta.1 si está muy completo)

3. Implementar frontend
   ├─ UI completa
   ├─ Integración con backend
   └─ CSS y componentes
   → git tag v0.X.0-beta.1

4. Testing y refinamiento
   ├─ Fix bugs encontrados
   ├─ Optimizaciones
   └─ Docs actualizadas
   → git tag v0.X.0-beta.2 (si es necesario)

5. Preparar release
   ├─ Tests exhaustivos
   ├─ Performance validation
   └─ Code review
   → git tag v0.X.0-rc.1

6. Merge a main
   git checkout main
   git merge desarrollo_paso_31
   → git tag v0.X.0
```

---

## 5. Comandos Git Útiles

### Crear tag annotated (recomendado)

```bash
# Con mensaje inline
git tag -a v0.9.0-alpha.1 -m "feat: add category models"

# Con editor para mensaje largo
git tag -a v0.9.0-alpha.1

# Push tag específico a remote
git push origin v0.9.0-alpha.1

# Push todos los tags
git push origin --tags
```

### Listar tags

```bash
# Listar todos los tags
git tag

# Listar tags con patrón
git tag -l "v0.9.*"

# Ver detalles de un tag (mensaje, commit, autor, fecha)
git show v0.9.0-alpha.1

# Listar tags con sus mensajes
git tag -n
```

### Ver cambios entre tags

```bash
# Diff entre dos tags
git diff v0.8.0 v0.9.0

# Log de commits entre tags
git log v0.8.0..v0.9.0 --oneline

# Archivos cambiados entre tags
git diff v0.8.0 v0.9.0 --name-only
```

### Eliminar tag (si cometiste error)

```bash
# Eliminar tag local
git tag -d v0.9.0-alpha.1

# Eliminar tag en remote
git push origin --delete v0.9.0-alpha.1

# Recrear tag en el mismo commit
git tag -a v0.9.0-alpha.1 -m "feat: mensaje corregido"
git push origin v0.9.0-alpha.1
```

### Checkout a un tag

```bash
# Ver código de un tag específico (detached HEAD)
git checkout v0.9.0-beta.1

# Crear branch desde un tag
git checkout -b hotfix/v0.9.0 v0.9.0

# Volver a la rama de desarrollo
git checkout desarrollo_paso_31
```

---

## 6. Convenciones de Mensajes

### Conventional Commits

Usar prefijos estándar en los mensajes de tags:

```
feat:     nueva funcionalidad
fix:      corrección de bug
docs:     solo documentación
chore:    tareas de mantenimiento
test:     agregar o modificar tests
refactor: refactorización sin cambiar funcionalidad
perf:     mejoras de performance
style:    cambios de formato (no afectan lógica)
build:    cambios en build system o dependencias
ci:       cambios en configuración de CI/CD
```

### Ejemplos de mensajes de tag

```bash
# Features
git tag -a v0.9.0-alpha.1 -m "feat: add category models and migrations"
git tag -a v0.9.0-beta.1 -m "feat: complete category classification UI"
git tag -a v0.10.0 -m "feat: add OAuth2 authentication with Google"

# Fixes
git tag -a v0.8.2 -m "fix: resolve OAuth token refresh issue"
git tag -a v0.9.1 -m "fix: correct category color mapping in dark mode"

# Releases
git tag -a v0.9.0-rc.1 -m "chore: prepare v0.9.0 release"
git tag -a v0.9.0 -m "Release v0.9.0: Automatic channel categorization and rating system"

# Hotfixes
git tag -a v0.9.2 -m "fix(security): patch SQL injection vulnerability"
```

---

## 7. Cuándo Crear Tag

### ✅ Sí crear tag cuando:

- Completas una fase significativa del desarrollo
- Toda la funcionalidad de un milestone está implementada
- Quieres marcar un checkpoint para posible rollback
- Antes de merge a `main`
- Después de merge exitoso a `main` (tag estable)
- Feature lista para testing por otros
- Fix crítico implementado y testeado

### ❌ No crear tag cuando:

- Commits intermedios pequeños (WIP)
- Solo cambios de formato o linting
- Experimentos que no funcionaron
- Refactors internos sin cambio de funcionalidad
- Commits de "fix typo" o similares
- Durante debugging activo

---

## 8. Buenas Prácticas

### 1. Tags annotated vs lightweight

**Siempre usar tags annotated (`-a`)**:
- Incluyen autor, fecha, mensaje
- Son objetos completos en Git
- Mejor para trazabilidad

```bash
# ✅ Correcto - annotated tag
git tag -a v0.9.0 -m "Release v0.9.0"

# ❌ Evitar - lightweight tag
git tag v0.9.0
```

### 2. Mensajes descriptivos

**Mensaje debe explicar QUÉ y POR QUÉ**:

```bash
# ✅ Bueno
git tag -a v0.9.0-beta.1 -m "feat: complete category classification UI

- Added category carousels with infinite loading
- Implemented star rating component (1-5)
- Applied yt_list color system with CSS tokens
- All tests passing, ready for testing team"

# ❌ Malo
git tag -a v0.9.0-beta.1 -m "beta 1"
```

### 3. Consistencia en nomenclatura

**Mantener el formato**:
- Siempre prefijo `v` (v0.9.0, no 0.9.0)
- Siempre 3 números (0.9.0, no 0.9)
- Guión antes de prerelease (v0.9.0-beta.1, no v0.9.0beta1)
- Punto entre prerelease y número (beta.1, no beta1)

### 4. No reusar tags

**Nunca sobrescribir un tag existente**:
```bash
# ❌ Nunca hacer esto
git tag -f v0.9.0 HEAD
git push origin v0.9.0 --force

# ✅ En su lugar, crear nuevo incremento
git tag -a v0.9.0-beta.2 -m "fix: correct issues from beta.1"
```

### 5. Sincronizar con remote

**Siempre push después de crear tag**:
```bash
git tag -a v0.9.0-beta.1 -m "feat: category UI complete"
git push origin v0.9.0-beta.1
```

### 6. Changelog actualizado

**Mantener CHANGELOG.md sincronizado con tags**:
```markdown
## [0.9.0-beta.1] - 2025-01-26

### Added
- Automatic channel categorization (14 categories)
- Star rating system (1-5) for channels
- Category carousels with infinite loading
- yt_list color system integration

### Changed
- Channel model extended with topicIds, keywords, country
- UserChannel model extended with rating fields

### Fixed
- OAuth token refresh on expired credentials
```

---

## 9. Integración Futura con CI/CD

Cuando se configure CI/CD, se pueden automatizar acciones basadas en tags:

### GitHub Actions ejemplo

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    tags:
      - 'v*.*.*'           # Solo tags estables (v0.9.0, v1.0.0)
      - '!v*.*.*-alpha.*'  # Excluir alphas
      - '!v*.*.*-beta.*'   # Excluir betas
      - '!v*.*.*-rc.*'     # Excluir release candidates

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to production
        run: ./scripts/deploy.sh
```

### Otras automatizaciones posibles

- **Alpha tags**: Trigger tests automáticos
- **Beta tags**: Deploy a staging environment
- **RC tags**: Tests de regresión completos + notificación al equipo
- **Stable tags**: Deploy a producción + release notes automáticas

---

## 10. Historia de Versiones del Proyecto

### Versión Actual

**v0.9.0-beta.1** (2025-01-26)
- Sistema de categorización automática de canales
- Sistema de valoración por estrellas (1-5)
- Integración de clasificadores desde yt_list

### Versiones Anteriores

**v0.8.1-beta.1**
- OAuth2 con Google
- Importación de suscripciones
- Auto-refresh de videos

**v0.8.0**
- Sistema de temas manuales
- Carousels con infinite loading
- Dark mode support

---

## 11. Roadmap de Versiones Futuras

### v0.9.0 (Próximo stable)
- Completar testing del sistema de categorías
- Performance optimization
- Docs completas
- **ETA**: Q1 2025

### v0.10.0
- Filtros avanzados (por categoría + rating)
- Búsqueda mejorada
- Export de datos

### v1.0.0 (Primera versión estable)
- Todos los features core completos
- Testing exhaustivo en producción
- Performance validado a escala
- Docs completas para usuarios
- **ETA**: Q2 2025

---

## 12. FAQ

### ¿Cuándo pasar de 0.x.x a 1.0.0?

Cuando:
- Todas las features core están implementadas
- Has validado el producto con usuarios reales
- No esperas breaking changes frecuentes
- Estás comprometido con backward compatibility
- La API está estable

### ¿Puedo saltarme alpha/beta/rc?

Sí, si:
- El cambio es muy pequeño (patch)
- Estás muy seguro de la estabilidad
- Ya tienes tests exhaustivos

Pero es recomendable usarlos para features grandes.

### ¿Qué hago si me equivoco en un tag?

1. Eliminar el tag incorrecto
2. Crear uno nuevo con el número siguiente

```bash
# Oops, pusheé v0.9.0-beta.1 muy pronto
git tag -d v0.9.0-beta.1
git push origin --delete v0.9.0-beta.1

# Ahora está realmente listo
git tag -a v0.9.0-beta.2 -m "feat: category UI complete (was beta.1)"
git push origin v0.9.0-beta.2
```

### ¿Puedo crear tags en branches que no sean main?

Sí, especialmente:
- Alpha/beta tags en `desarrollo_paso_31`
- RC tags justo antes de merge
- **Stable tags solo en `main`**

### ¿Cómo manejo hotfixes?

Si ya tienes v0.9.0 en main y encuentras un bug:

```bash
# Crear branch desde el tag
git checkout -b hotfix/0.9.1 v0.9.0

# Fix el bug
git commit -m "fix: critical OAuth bug"

# Tag el hotfix
git tag -a v0.9.1 -m "fix: resolve OAuth token expiration"

# Merge a main
git checkout main
git merge hotfix/0.9.1
git push origin main
git push origin v0.9.1

# Merge también a desarrollo
git checkout desarrollo_paso_31
git merge hotfix/0.9.1
```

---

## Recursos

- [Semantic Versioning 2.0.0](https://semver.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Git Tagging Documentation](https://git-scm.com/book/en/v2/Git-Basics-Tagging)
- [Keep a Changelog](https://keepachangelog.com/)

---

## Apéndice: Ejemplo Completo de Release

### Escenario: Preparar v0.9.0 stable desde v0.9.0-beta.1

```bash
# 1. Verificar estado actual
git status
git tag -l "v0.9.*"

# 2. Completar testing y fixes
# (hacer commits de fixes si es necesario)

# 3. Crear release candidate
git tag -a v0.9.0-rc.1 -m "chore: prepare v0.9.0 release

Release candidate for category classification system.
All tests passing, ready for final validation."

git push origin v0.9.0-rc.1

# 4. Testing final en RC
# (si se encuentran bugs, crear v0.9.0-rc.2, etc.)

# 5. Merge a main
git checkout main
git pull origin main
git merge desarrollo_paso_31

# 6. Actualizar docs
# - README.md
# - CHANGELOG.md
# - docs/deployment.md

git add .
git commit -m "docs: update for v0.9.0 release"

# 7. Crear tag stable
git tag -a v0.9.0 -m "Release v0.9.0: Automatic Channel Categorization

Major Features:
- Automatic channel categorization into 14 predefined categories
- 4-method classification cascade (YouTube Topics, TF-IDF, Hybrid, Ollama)
- Star rating system (1-5) for channels
- Category carousels with infinite loading
- Manual category override capability
- yt_list color system integration with CSS tokens

Breaking Changes:
- Database schema updated (new tables: categories, channel_categories)
- UserChannel model extended with rating fields
- Channel model extended with classification metadata

Migration required: yes
Tests coverage: 85%"

# 8. Push everything
git push origin main
git push origin v0.9.0

# 9. Crear GitHub Release (opcional)
gh release create v0.9.0 \
  --title "v0.9.0 - Automatic Channel Categorization" \
  --notes-file CHANGELOG.md

# 10. Volver a desarrollo
git checkout desarrollo_paso_31
git merge main
```

---

**Última actualización**: 2025-01-26
**Autor**: Sistema de versionado establecido para youtube-clear-view
