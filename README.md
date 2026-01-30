# W.I.P.

[Read this in Spanish →](README_ES.md)

# YT Clear View (YTCV)

**A clean, chronological view of your YouTube subscriptions.  
No recommendations. No noise. Just the channels you follow.**

## Screenshots

![YT Clear View](screenshots/YT-Clear-View.jpg)

---

## The Problem

Today, YouTube's Home feed is dominated by:
- Videos from channels you don't follow
- Algorithmic recommendations
- Engagement-driven ranking (CTR, watch time, trends)

As a result, **content from your own subscriptions gets buried**.

---

## The Solution

YTCV gives you a **controlled timeline** built only from:
- The channels you are subscribed to
- A real chronological order
- Your own filtering and categorization rules

Nothing else.

---

## What This App Does

- Connects to **your YouTube account** using the official API (OAuth)
- Fetches videos (and subscription Shorts) **only from your subscribed channels**
- Displays them in a **clean, distraction-free timeline**
- Allows filtering and categorization

You stay connected to YouTube - you just stop consuming what the algorithm pushes.

---

## What This App Does NOT Do

- No YouTube Home feed
- No "Recommended for you"
- No trends or suggested content
- No autoplay-driven suggestions

This app does **not replace YouTube**. It replaces the **recommendation layer**.

---

## About the Algorithm (Important)

YouTube uses multiple algorithms. This project intentionally removes only one:

| Layer | Used |
|---|---|
| Recommendation engine (Home / Up Next) | No |
| Trending / Suggested content | No |
| Subscriptions timeline | Yes (controlled by the app) |
| Official metadata | Yes (via API) |

---

## Why the Official YouTube API (OAuth)

This project uses the YouTube Data API v3 with OAuth authentication:
- Stable access to real subscriptions
- Accurate metadata
- Long-term maintainability
- Compliance with YouTube terms

This is **not** a scraping-based tool.

---

## Requirements (High Level)

- A Google account
- A Google Cloud project with YouTube Data API v3 enabled
- OAuth credentials (Client ID / Secret)

Setup and deployment live under [`docs/`](docs/).

---

## Who This Is For

- Users tired of recommendation-driven feeds
- People who want to watch only what they chose
- Anyone who wants YouTube without the noise

---

## Tech Stack (Brief)

- Backend: Python (Flask)
- Frontend: HTML / CSS / Vanilla JS
- Auth: YouTube Data API v3 (OAuth)
- Storage: SQLite

---

## Documentation

- API reference: [docs/api-reference.md](docs/api-reference.md)
- Architecture: [docs/architecture.md](docs/architecture.md)
- Deployment: [docs/deployment.md](docs/deployment.md)
- Development: [docs/development.md](docs/development.md)

---

## License

MIT. See [LICENSE](LICENSE) or the official reference at [choosealicense.com](https://choosealicense.com/licenses/mit/).
