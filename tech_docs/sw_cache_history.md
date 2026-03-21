# Service Worker Cache History

Purpose:
- Keep a simple manual record of `frontend/sw.js` cache versions.
- Before any frontend rebuild that should invalidate browser cache, check this file and bump to the next version.

Rule:
1. Read the last recorded version.
2. Increase by `+1`.
3. Update `frontend/sw.js`.
4. Rebuild `proxy`.
5. Append a short note here.

Current latest:
- `ytcv-v55`

History:
- `ytcv-v55`
  - Reason: add title to the global scheduled refresh card in gestor.
- `ytcv-v54`
  - Reason: remove the user menu button for auto updates after moving schedule management to gestor.
- `ytcv-v53`
  - Reason: move scheduled refresh configuration to gestor and remove schedule controls from the user UI.
- `ytcv-v52`
  - Reason: show active global refresh state on entry and block manual refresh while it is running.
- `ytcv-v51`
  - Reason: localize and humanize refresh warning messages.
- `ytcv-v50`
  - Reason: clarify menu labels for channel updates vs video refresh.
- `ytcv-v49`
  - Reason: remove duplicate web refresh button and keep refresh only in the menu.
- `ytcv-v48`
  - Reason: backend refresh jobs frontend integration and gestor quota summary.
- `ytcv-v47`
  - Reason: start with subscriptions panel collapsed and highlight toggle button.
- `ytcv-v46`
  - Reason: keep subscriptions toggle only in the quick action row.
- `ytcv-v45`
  - Reason: shared subscriptions toggle icon for desktop, tablet, and TV.
- `ytcv-v44`
  - Reason: video overlay button polish, category chips cleanup, and subscriptions icon toggle.
- `ytcv-v43`
  - Reason: player overlay reopen hotfix cache invalidation.
- `ytcv-v42`
  - Reason: video overlay hotfix iteration and rebuild consistency.
- `ytcv-v41`
  - Reason: login masthead title iteration and ensure fresh frontend cache.
- `ytcv-v40`
  - Reason: login footer/layout cache invalidation.
- `ytcv-v39`
  - Reason: gestor/admin dedicated route and login/overlay updates.
- `ytcv-v37`
  - Reason: auth callback fallback and onboarding flow cache invalidation.
- `ytcv-v36`
  - Reason: login/service worker cache refresh after frontend changes.

Quick checklist before rebuild:
- Did frontend HTML/CSS/JS change?
- If yes, bump `CACHE_VERSION` first.
- Then run:

```bash
./scripts/dev_docker.sh up --build proxy
```

Verification:

```bash
curl http://localhost:8080/sw.js | grep ytcv-v
```

Pending fix:
- `frontend/sw.js` can be bumped correctly while `frontend/dist/sw.js` still stays on an old cache version (`ytcv-v1`).
- Review the frontend build pipeline so the generated `dist/sw.js` always reflects the current source `CACHE_VERSION` before rebuilding `proxy`.
