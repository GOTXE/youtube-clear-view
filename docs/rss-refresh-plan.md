# RSS Refresh Migration Plan

## Goal

Switch regular channel video refresh from YouTube Data API v3 to YouTube channel RSS/Atom feeds in order to reduce quota usage drastically.

The YouTube Data API should remain available only for targeted fallback and enrichment cases.

This document is a planning artifact only. It does **not** imply implementation has started.

## Current Baseline

Current regular refresh path:

1. User/global refresh enters backend through refresh jobs and `iter_refresh_user_channels()`.
2. For each channel, backend consumes quota (`YT_REFRESH_COST`).
3. `YTService.get_channel_videos()` resolves the uploads playlist via `channels.list(part=contentDetails)`.
4. Backend calls `playlistItems.list(...)`.
5. Backend calls `videos.list(...)`.
6. The combined payload is normalized and upserted into `videos`.

Current strength:

- complete enough metadata for cards and classification support
- supports pagination and controlled backfill
- deterministic with current data model

Current weakness:

- regular refresh burns quota for every channel refresh
- scheduler and manual refresh compete for the same daily budget

## What the RSS/Atom Feed Gives Us

Channel feed URL pattern:

```text
https://www.youtube.com/feeds/videos.xml?channel_id=<YT_CHANNEL_ID>
```

Observed/expected useful fields per entry:

- `yt:videoId`
- `yt:channelId`
- `title`
- `author/name`
- `published`
- `updated`
- `link href`

Potentially useful but not guaranteed for all logic:

- feed-level channel title
- media namespace fields if present

What we can safely use from RSS for the main refresh:

- discover newest uploads for a channel
- compare known `yt_video_id` values against local DB
- insert lightweight new video placeholders quickly
- update title/published time if changed

What RSS does **not** reliably give us compared to API:

- normalized duration in seconds
- video category id
- tags
- rich thumbnails chosen from API snippet variants
- enough metadata for some classification/enrichment use cases
- long history pagination suitable for deep backfill

## Core Design Decision

Use a **hybrid refresh model**:

- RSS/Atom feed becomes the default path for normal video refresh.
- YouTube Data API remains for:
  - subscription import/update
  - channel info enrichment
  - metadata completion for newly discovered videos when needed
  - backfill/recovery flows
  - gap repair when feed window is insufficient

This avoids a risky full replacement while still achieving the quota savings.

## Target Behavior

### Normal refresh

For each subscribed channel:

1. Request RSS feed.
2. Parse entries.
3. For each new `yt:videoId` not in local DB:
   - create/update local video row with lightweight metadata
   - mark row as `metadata_incomplete=true` or equivalent
4. Stop without spending YouTube API quota for that channel.

### Metadata completion

For RSS-discovered videos missing required fields:

- complete lazily using `videos.list(...)` only for those specific new videos
- batch requests across channels where possible

### Fallback cases

Use YouTube API instead of RSS when:

- feed fetch fails repeatedly
- channel has no usable feed response
- consistency repair is requested
- backfill is active
- classification/enrichment explicitly requires metadata RSS does not provide

## Data Model Changes

Planned additions in `videos` and/or related tables:

- `source_last_seen_at`
- `metadata_completeness` or `metadata_incomplete`
- `discovered_via` with values like `rss` / `api`
- optional `feed_published_at`
- optional `feed_updated_at`

Planned additions in `user_channels` or per-channel runtime state:

- `last_feed_checked_at`
- `last_feed_success_at`
- `last_feed_error_at`
- `feed_error_count`
- `refresh_mode_override` if fallback must be forced temporarily

## Service Layer Changes

### New services/modules

1. `rss_feed.py`
- build feed URL from `yt_channel_id`
- download feed
- parse Atom/XML safely
- normalize entries into internal DTOs

2. `rss_refresh.py`
- compare feed entries with local DB
- create lightweight new videos
- collect list of video IDs requiring API completion

3. `metadata_completion.py`
- batch-complete missing metadata for RSS-discovered videos
- rate-limit and quota-control this path separately

### Existing service updates

1. `video_ingest.py`
- split current refresh into:
  - discovery path
  - metadata completion path
  - pruning path

2. `yt_api.py`
- keep current methods
- add lighter targeted helper for `videos.list(id=...)` completion only

3. `scheduler.py`
- scheduler should default to RSS discovery
- API fallback only when rules require it

## Refresh Strategy by Scenario

### Manual refresh

Default:
- RSS discovery
- targeted metadata completion for new IDs only

Benefits:
- fast
- cheap quota usage

### Scheduled/global refresh

Default:
- RSS discovery for all channels
- batched metadata completion only for net-new items

Benefits:
- predictable quota cost
- safer to run multiple times daily

### Import/Update channels

Still uses API:
- user subscriptions import requires authenticated YouTube API access

### Backfill

Still uses API:
- RSS feed window is too small for reliable historical reconstruction

## Feed Window Risk

This is the biggest design risk.

Because the feed is only a recent window, we can lose items if:

- the app is offline too long
- scheduler is disabled
- a user has many uploads on a channel between refreshes

Mitigation strategy:

1. Keep scheduler reasonably frequent.
2. Store `last_feed_success_at` per channel.
3. If channel has been unchecked longer than a threshold:
   - escalate that channel to API recovery mode
4. Add periodic repair job:
   - low-frequency API reconciliation for stale channels only

## Metadata Policy

### Required immediately from RSS

- `yt_video_id`
- `channel_id`
- `title`
- `published_at`
- `source=RSS`

### Deferred metadata

- `duration`
- `thumbnail_url`
- `description`
- `video_category_id`
- `tags`

### UI implication

Cards must tolerate temporarily incomplete data:

- duration missing -> hide duration until completed
- thumbnail missing -> use channel thumbnail or generic placeholder
- short/video split must degrade safely until duration is known

## Classification Impact

Regular channel classification should **not** depend on full API refresh.

Rules:

- keep channel-level enrichment separate from normal RSS discovery
- use API only when classification truly needs more evidence
- avoid spending video refresh quota on metadata not needed for user browsing

## Operational Controls

New admin/runtime knobs to plan:

- `VIDEO_REFRESH_MODE = rss_preferred | api_only | hybrid`
- RSS timeout
- RSS failure threshold before API fallback
- stale-channel threshold for repair
- batch size for metadata completion

## Phase Plan

### Phase 0: Design Freeze
Status: Pending

Deliverables:

- final field mapping RSS -> local video
- fallback policy table
- stale-channel repair policy
- UI policy for incomplete metadata

Completion criteria:

- no open ambiguity about what regular refresh uses
- no ambiguity about when API fallback is allowed

### Phase 1: RSS Reader Foundation
Status: Pending

Scope:

- add RSS fetcher/parser
- add normalized RSS entry DTO
- unit tests for parsing and malformed feeds

Completion criteria:

- can parse a real channel feed into normalized entries
- parser survives missing/partial fields

### Phase 2: Hybrid Discovery Pipeline
Status: Pending

Scope:

- integrate RSS into refresh jobs
- discover new IDs from feeds
- create lightweight video rows
- do not break current UI

Completion criteria:

- regular refresh works with RSS-first path
- new items appear in DB without full API refresh

### Phase 3: Targeted Metadata Completion
Status: Pending

Scope:

- identify which RSS-found videos still need metadata
- batch-complete only those videos with `videos.list(...)`
- preserve quota controls

Completion criteria:

- most normal cards have enough metadata after refresh
- quota usage drops sharply versus current baseline

### Phase 4: Fallback and Repair
Status: Pending

Scope:

- fallback to API on feed failure/staleness
- periodic repair for stale channels
- observability for RSS errors and fallback counts

Completion criteria:

- stale or failed feeds do not silently lose videos
- admin can understand when fallback is happening

### Phase 5: Admin Visibility
Status: Pending

Scope:

- gestor/runtime metrics:
  - channels refreshed via RSS today
  - API fallback count today
  - metadata completion calls today
  - estimated quota saved

Completion criteria:

- admin can see if RSS mode is healthy

### Phase 6: Cleanup and Default Switch
Status: Pending

Scope:

- make RSS-first the default
- keep `api_only` kill switch
- update docs/manuals

Completion criteria:

- production-ready switch with rollback path

## Pending Decisions

1. Should RSS-discovered videos be visible before metadata completion finishes?
2. How long can a channel stay feed-only before forced API repair?
3. Should metadata completion run inline with refresh job or as a second background job?
4. Should short detection wait for duration or use temporary heuristics?
5. Do we want separate metrics for RSS savings in gestor before rollout?

## Recommended Acceptance Metrics

Target after rollout:

- manual refresh quota usage reduced drastically
- scheduled refresh quota usage reduced drastically
- no noticeable increase in missing videos
- no UI regressions for recent uploads

## Out of Scope for This Plan

- switching subscription import away from API
- removing YouTube Data API from the project entirely
- redesigning watch progress or overlays

## Phase Completion Ledger

- Phase 0: Pending
- Phase 1: Pending
- Phase 2: Pending
- Phase 3: Pending
- Phase 4: Pending
- Phase 5: Pending
- Phase 6: Pending
