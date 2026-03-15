# Video Automation System

Automated YouTube Shorts pipeline: generate a script with an AI provider, render a video with MoviePy, and upload to YouTube — on a schedule or on demand via the web dashboard.

![Dashboard](https://img.shields.io/badge/Flask-Dashboard-orange) ![Python](https://img.shields.io/badge/Python-3.10+-blue) ![YouTube](https://img.shields.io/badge/YouTube-Data_API_v3-red)

---

## Prerequisites

- Python 3.10+
- **FFmpeg** installed and on `PATH`
  - Windows: https://ffmpeg.org/download.html — extract and add `bin/` to `PATH`
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`
- A Google account with a YouTube channel

---

## Installation

```bash
git clone https://github.com/your-username/video-automation-system.git
cd video-automation-system
pip install -r requirements.txt
```

> **Windows:** Always run Python with `-X utf8` to avoid encoding issues:
> `python -X utf8 dashboard.py`

---

## Configuration

### 1. Google OAuth Credentials *(required for YouTube upload)*

1. Go to [Google Cloud Console](https://console.cloud.google.com) and create a new project
2. **Enable the API:** APIs & Services → Enable APIs & Services → search **"YouTube Data API v3"** → Enable
3. **Configure consent screen:** APIs & Services → OAuth consent screen
   - User type: **External**
   - Fill in App name and your email
   - Add your Google account as a **Test user** → Save
4. **Create credentials:** APIs & Services → Credentials → Create Credentials → **OAuth client ID**
   - Application type: **Desktop app** → Create
   - Click **Download JSON**
5. Rename the downloaded file to `client_secrets.json` and place it in the project root

The file should look like this:
```json
{
  "installed": {
    "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "client_secret": "YOUR_CLIENT_SECRET",
    ...
  }
}
```

### 2. Content API Key *(required)*

The system supports three AI providers for script generation:

| Provider | Get your key | Notes |
|---|---|---|
| **Anthropic** (Claude) | [console.anthropic.com](https://console.anthropic.com) → API Keys | Recommended |
| **OpenAI** (GPT-4o) | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | |
| **Google** (Gemini) | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | Free tier available |

Set in the dashboard under **Settings → Content Provider**, or in a `.env` file:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. TTS Voiceover *(optional)*

| Provider | Get your key | Notes |
|---|---|---|
| **ElevenLabs** | [elevenlabs.io](https://elevenlabs.io) → Profile → API Key | High quality |
| **OpenAI TTS** | Same key as OpenAI content key | |
| **Edge TTS** | No key needed — free | |

Set in **Settings → TTS**, or in `.env`:
```env
ELEVENLABS_API_KEY=...
```

### 4. Stock Video Background *(optional)*

| Provider | Get your key |
|---|---|
| **Pexels** | [pexels.com/api](https://www.pexels.com/api/) — free |
| **Pixabay** | [pixabay.com/api/docs](https://pixabay.com/api/docs/) — free |

Set in **Settings → Stock Video**, or in `.env`:
```env
PEXELS_API_KEY=...
```

### 5. Background Music

Place royalty-free `.mp3` files in the `music/` directory. The system picks one randomly per video.

Free sources:
- [Pixabay Music](https://pixabay.com/music/) (ambient / space)
- [YouTube Audio Library](https://studio.youtube.com) → Audio Library

---

## Running

```bash
# Web dashboard (recommended)
python -X utf8 dashboard.py
# Open http://localhost:5000
```

```bash
# Single pipeline run (no dashboard)
python -X utf8 main.py "optional topic here"

# Headless scheduler only
python -X utf8 scheduler.py
```

---

## First-time Setup

When you open the dashboard, a **Setup Required** banner will appear at the top listing any missing configuration. Click **Configure →** next to each item to go to Settings.

Once `client_secrets.json` is in place and your content API key is saved, connect your YouTube channel:

1. Go to **Settings → Channel**
2. Click **＋ Yeni Kanal Bağla** → **YouTube**
3. A browser window opens — sign in and grant permissions
4. Your channel appears in the dashboard header ✓

---

## Usage

### Generate a video manually

1. Open the **Production** tab
2. Enter an optional topic or leave blank for AI to choose
3. Click **Generate** → review each section → **Render** → **Publish**

### Schedule automatic uploads

1. Go to the **Schedule** tab
2. Set daily upload time
3. Assign a channel to the schedule (if multiple channels are connected)
4. Start the scheduler from the header

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/setup/status` | Setup checklist |
| GET | `/api/status` | Pipeline + scheduler state |
| GET | `/api/channels` | Connected channels list |
| POST | `/api/channels/connect` | Start YouTube OAuth flow |
| DELETE | `/api/channels/<id>` | Disconnect a channel |
| GET | `/api/settings` | All settings (keys masked) |
| POST | `/api/settings` | Save settings |
| POST | `/api/generate` | Start pipeline `{"topic":""}` |
| GET | `/api/logs/stream` | SSE live log stream |

---

## Troubleshooting

**"Missing required parameter: client_id"**
Your `client_secrets.json` is missing or empty. Follow [step 1](#1-google-oauth-credentials-required-for-youtube-upload) above.

**"Access blocked: this app's request is invalid"**
Your Google account is not listed as a test user. Add it in Google Cloud Console → OAuth consent screen → Test users.

**"invalid_client"**
The `client_secrets.json` does not match what's in Google Cloud Console. Re-download the credentials file.

**YouTube API quota exceeded**
Free quota is 10,000 units/day. One upload costs ~1,600 units (~6 uploads/day max). Quota resets at midnight Pacific Time.

**FFmpeg not found**
Install FFmpeg and ensure the `bin/` directory is on your system `PATH`. Restart the terminal after editing `PATH`.

**No audio in rendered video**
Place an `.mp3` file in the `music/` directory. If TTS is enabled, verify the API key is valid.

**`ModuleNotFoundError: moviepy.editor`**
The code uses MoviePy 2.x imports. Delete `__pycache__/` and retry.

---

## License

MIT
