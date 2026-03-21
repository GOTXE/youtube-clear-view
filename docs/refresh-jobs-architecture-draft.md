# Refresh Jobs Architecture Draft

## Goal

Move refresh execution fully to the backend so refresh work continues after the browser closes.

## Scope

- scheduled refresh remains backend-driven
- manual refresh becomes backend-driven too
- frontend only starts jobs and polls status
- scheduled refresh gets quota priority over manual refresh
- schedule configuration becomes admin-only in gestor
- `Import channels` must remain the action that imports newly subscribed channels from YouTube

## User-visible behavior

- while running:
  - `Actualizando canales y videos desde YouTube`
- when complete:
  - `Actualizacion completada: {count} videos nuevos`
- when manual refresh is rejected because quota must be preserved:
  - `Imposible ejecutar, prioridad update programado`

## Execution options

### Option A: request-bound SSE execution

Pros:
- already implemented
- simple to stream progress

Cons:
- tied to browser lifetime
- not durable
- hard to unify with scheduler

### Option B: in-process background worker thread

Pros:
- simple incremental change from current backend
- browser can disconnect safely
- can share code with scheduler
- no extra infrastructure

Cons:
- process-local only
- less robust across restarts
- coordination is harder if multiple backend processes appear later

### Option C: external queue/worker

Pros:
- strongest durability and observability
- better concurrency control
- scales beyond a single process

Cons:
- more infrastructure and operational cost
- overkill for current SQLite/self-hosted setup

## Chosen direction

Start with Option B.

Reason:
- matches the current app deployment
- keeps complexity controlled
- removes the browser dependency now
- allows later migration to a queue if needed

## Data model

`refresh_jobs`

Suggested fields:
- `id`
- `user_id`
- `kind` (`manual`, `scheduled`)
- `scope_type` (`all_channels`, `channel`)
- `scope_channel_id`
- `status` (`queued`, `running`, `completed`, `failed`, `blocked`)
- `message`
- `processed_channels`
- `total_channels`
- `new_videos`
- `rate_limited`
- `blocked_reason`
- `created_at`
- `started_at`
- `finished_at`

## API direction

- `POST /api/channels/refresh`
  - create manual refresh job
- `GET /api/channels/refresh/status`
  - current or latest refresh job for current user

SSE can remain only as an observer later if still useful, not as the execution carrier.

## Pending UX adjustments

- keep manual refresh available only from the menu, not from the main web quick-action bar
- preserve `Import channels` as the explicit entry point for bringing new YouTube subscriptions into the app
- keep the scheduled refresh configuration only in gestor as a single global installation setting
