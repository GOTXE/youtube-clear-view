# Development connection issue (dev=false)

## Summary
While running in development with `PROD=false`, the backend was reachable on the host machine but not from another device on the LAN. The local frontend showed "New user" instead of Google OAuth because the client could not reach `/api/auth/provider` on the backend.

## Observed behavior
- On the host machine:
  - `http://localhost:5550/api/auth/provider` returned `google`.
  - `http://192.168.2.209:5550/api/auth/provider` returned `google`.
- From a different device on the same network:
  - `http://192.168.2.209:5550/api/auth/provider` failed (connection refused).

## Root cause found
The backend process was bound to `127.0.0.1:5550` instead of `0.0.0.0:5550`:

```
ss -tlnp | grep 5550
LISTEN 0 128 127.0.0.1:5550 0.0.0.0:* users:("python",pid=...,fd=...)
```

Because the backend was only listening on loopback, other devices could not connect.

## Fixes applied
1. **scripts/run_local.sh** now respects `FLASK_HOST` and `FLASK_PORT`:
   - It runs Flask with `--host "${FLASK_HOST}"` and `--port "${FLASK_PORT}"`.

2. **Single `.env` toggle**:
   - Added `PROD=false` in `backend/.env.example` and `backend/.env`.
   - `run_local.sh` reads `PROD` to decide whether to use a prod or dev API base URL.

3. **Frontend config sync**:
   - `run_local.sh` copies `frontend/config.example.js` to `frontend/config.js` and replaces `API_BASE_URL` with the correct value for the selected mode.

After these changes, the backend bound to `0.0.0.0:5550`, and the API was reachable on the host IP **from the host machine**.

## Still failing
Even after binding to `0.0.0.0`, access from another device still failed with "connection refused".

## Likely remaining cause
- **Firewall or network policy** on the host machine (UFW/iptables or OS firewall) still blocking inbound connections on port 5550.
- The issue is not in the app code at this point.

## Notes
This is expected to be different in production because the backend will be behind the reverse proxy and accessed via HTTPS.
