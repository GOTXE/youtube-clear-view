# YouTube Data API v3 - Configuration Guide

## Google Cloud Console Setup

### 1. Create Project
- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Create a new project or select an existing one
- Note the project name for reference

### 2. Enable YouTube Data API v3
- Navigate to: APIs & Services → Library
- Search for "YouTube Data API v3"
- Click "Enable"

### 3. Create API Key
- Navigate to: APIs & Services → Credentials
- Click "Create Credentials" → "API Key"
- Copy the generated key

### 4. Restrict the API Key

#### API Restriction (REQUIRED):
- Click on the created key → "Restrict key"
- Under "API restrictions" → select "Restrict key"
- Select ONLY: **YouTube Data API v3**
- Save

#### Application Restriction:
- **None** (no application restriction)
- Reason: The key is used server-side (Python backend), not from a browser
- "HTTP referrers (websites)" does NOT work for server-side requests
- "IP addresses" only works with a fixed public IP (not applicable with dynamic IP)

### 5. Set Daily Quota Limit (RECOMMENDED)
- Navigate to: APIs & Services → YouTube Data API v3 → Quotas
- Set a reasonable daily limit: **5,000 - 10,000 units/day**
- This prevents unexpected usage/billing if the key is ever leaked
- Default quota is 10,000 units/day

### 6. Configure in Project
- Add the key to `backend/.env`:
  ```
  YOUTUBE_API_KEY=AIzaSy...your-key-here
  ```
- The `.env` file is in `.gitignore` (NEVER committed to the public repo)
- For reference, see `backend/.env.example` for the template

## Security Notes

- The API key is used ONLY by the backend (server-side Python requests)
- The frontend NEVER has access to the API key
- The key is stored in `.env` which is gitignored
- Without a fixed IP, the key cannot be restricted by application
- The daily quota limit is the main protection against abuse
- If the key is compromised: revoke it in Google Cloud Console and create a new one

## API Quota Usage Reference

| Operation | Cost (units) |
|-----------|-------------|
| search.list | 100 |
| channels.list | 1 |
| videos.list | 1 |
| playlistItems.list | 1 |

- With 10,000 units/day: ~100 searches or ~10,000 channel/video lookups
- The backend cache (video_cache.py) reduces API calls significantly

## Troubleshooting

- **403 Forbidden**: API key invalid, expired, or API not enabled
- **403 quotaExceeded**: Daily quota limit reached, wait 24h or increase limit
- **400 keyInvalid**: Key format wrong or key revoked
- Check usage: APIs & Services → YouTube Data API v3 → Metrics
