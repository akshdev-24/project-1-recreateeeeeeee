# Shayari Shorts Automation

## What this version does
- Gemini generates **only Shayari text**.
- Title is selected from `assets/titles.txt` (exactly 50 unique titles).
- A title is never reused until all 50 titles are used; then a new cycle starts.
- Description always comes from `assets/description.txt`.
- Tags always come from `assets/tags.txt`.
- No SEO title generator, queries, hashtags or automatic metadata generation.
- Background: `assets/background.jpg`; the full image is fitted without cropping and blurred fill is used around it when needed.
- Font: **Times New Roman Regular only** from `assets/fonts/times.ttf`.
- Music: `assets/music/bg_music.mp3`.
- Output: 1080x1920, 9:16, 15 seconds by default.
- YouTube upload is hard-coded **UNLISTED**.
- GitHub Actions supports manual Shayari input and scheduled runs at 09:00 and 14:00 IST.

## GitHub Secrets
Required for automatic upload:
- `GOOGLE_API_KEY`
- `CLIENT_SECRET_B64` — base64 of `client_secrets.json`
- `CREDENTIALS_B64` — base64 of authorized `credentials.json`

`PEXELS_API_KEY` is not used by this project.
