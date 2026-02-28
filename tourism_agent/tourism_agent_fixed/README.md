# 🌍 Tourism Agent – Automated Travel Video Pipeline

Automatically discovers travel trends, creates tourism videos, and publishes them
to YouTube, Instagram, Facebook, and Telegram — **100% free APIs**.

```
Trend Discovery → Script Writing → Image Collection → Video Creation
     → Voiceover → Music → Final Assembly → Social Media Publishing → Analytics
```

---

## 📁 Project Structure

```
tourism_agent/
├── main.py                    # Entry point, runs the full pipeline
├── config.py                  # All settings, API keys, location config
├── requirements.txt           # All dependencies
├── .env                       # API keys (never commit this!)
├── .env.example               # Template for env variables
│
├── agents/
│   ├── trend_agent.py         # Google Trends, Reddit, YouTube, DuckDuckGo, NewsAPI
│   ├── script_agent.py        # Gemini 1.5 Flash script generation
│   ├── image_agent.py         # Unsplash, Pexels, Pixabay, Wikimedia
│   ├── video_agent.py         # moviepy – Ken Burns, transitions, text overlays
│   ├── voice_agent.py         # ElevenLabs → gTTS → pyttsx3 (fallback chain)
│   ├── music_agent.py         # Pixabay Music, numpy ambient fallback
│   ├── publisher_agent.py     # YouTube, Instagram, Facebook, Telegram
│   └── analytics_agent.py    # SQLite metrics, HTML reports
│
├── utils/
│   ├── file_manager.py        # Path helpers, deduplication, cleanup
│   ├── logger.py              # loguru – coloured console + rotating file
│   └── scheduler.py           # APScheduler – 3× daily cron jobs
│
└── output/
    ├── videos/                # Final MP4 files
    ├── images/                # Downloaded & processed images
    ├── audio/                 # Voiceover & music files
    ├── scripts/               # Generated JSON + TXT scripts
    └── reports/               # Weekly HTML analytics reports
```

---

## ⚡ Quick Start

### 1. Clone / Download

```bash
git clone <your-repo>
cd tourism_agent
```

### 2. Install Dependencies

```bash
# Python 3.11+ recommended
pip install -r requirements.txt

# Also install ffmpeg (required by moviepy)
# macOS:
brew install ffmpeg
# Ubuntu/Debian:
sudo apt install ffmpeg
# Windows: https://ffmpeg.org/download.html (add to PATH)
```

### 3. Copy and Fill the .env File

```bash
cp .env.example .env
# Open .env and fill in your API keys (see "Getting Free API Keys" below)
```

### 4. Change the Target Location (optional)

Edit `config.py` → `LOCATION` dict. Change `name`, `country`, `hashtags`, etc.

### 5. Run

```bash
# Full pipeline
python main.py

# Test mode (no actual publishing)
python main.py --dry-run

# Use a custom topic
python main.py --topic "Best beaches in Tunis"

# Publish to YouTube only
python main.py --platform youtube

# Generate 3 videos in batch
python main.py --count 3

# Run on schedule (3× daily, blocks)
python main.py --schedule

# View analytics report
python main.py --analytics
```

---

## 🔑 Getting Free API Keys

### Gemini 1.5 Flash (AI Script Writer)
- Go to **https://aistudio.google.com**
- Sign in with Google → Click "Get API Key" → Create API Key
- Free: 1,000,000 tokens / day
- Add to `.env`: `GEMINI_API_KEY=your_key_here`

### Unsplash (Images)
- Go to **https://unsplash.com/developers**
- Click "Your apps" → "New Application"
- Accept terms → Fill in app details
- Copy the **Access Key**
- Free: 50 requests / hour
- Add to `.env`: `UNSPLASH_ACCESS_KEY=your_key_here`

### Pexels (Images)
- Go to **https://www.pexels.com/api/**
- Click "Get Started" → Create free account
- Copy API key from dashboard
- Free: 200 requests / hour
- Add to `.env`: `PEXELS_API_KEY=your_key_here`

### Pixabay (Images + Music)
- Go to **https://pixabay.com/api/docs/**
- Register → Copy your API key
- Free: 100 requests / minute
- Add to `.env`: `PIXABAY_API_KEY=your_key_here`

### ElevenLabs (Voice – Best Quality)
- Go to **https://elevenlabs.io**
- Sign up free → Profile → API Keys → Generate
- Free: 10,000 characters / month
- Add to `.env`: `ELEVENLABS_API_KEY=your_key_here`
- ⚠️ If limit exceeded, falls back to gTTS automatically

### YouTube Data API
- Go to **https://console.developers.google.com**
- Create project → Enable **YouTube Data API v3**
- Create **OAuth 2.0 credentials** (Desktop app type)
- Download JSON, extract `client_id` and `client_secret`
- Run the OAuth flow once to get the refresh token:
  ```bash
  python -c "
  from google_auth_oauthlib.flow import InstalledAppFlow
  flow = InstalledAppFlow.from_client_secrets_file(
      'client_secrets.json',
      scopes=['https://www.googleapis.com/auth/youtube.upload']
  )
  creds = flow.run_local_server(port=8080)
  print('Refresh token:', creds.refresh_token)
  "
  ```
- Free: 10,000 units / day (1 video upload ≈ 1,600 units)

### Instagram / Facebook (Meta Graph API)
1. Create Facebook App at **https://developers.facebook.com**
2. Add **Instagram Graph API** product
3. Create a **Facebook Business Page** (free)
4. Connect your Instagram Business account to the page
5. Generate a **Long-Lived Access Token** via the Graph API Explorer
6. Add to `.env`: tokens and page IDs

### Telegram Bot
1. Open Telegram → Search **@BotFather**
2. Send `/newbot` → Follow prompts → Copy the bot token
3. Create a channel → Add your bot as administrator
4. Copy the channel username (e.g. `@my_travel_channel`)
5. Add to `.env`: `TELEGRAM_BOT_TOKEN=...` and `TELEGRAM_CHANNEL_ID=@channel`

### Reddit (Trend Discovery)
1. Go to **https://www.reddit.com/prefs/apps**
2. Scroll down → "Create App" → Choose "script"
3. Copy `client_id` (under app name) and `secret`
4. Add to `.env`

### NewsAPI
1. Go to **https://newsapi.org**
2. Register → Copy API key
3. Free: 100 requests / day
4. Add to `.env`: `NEWS_API_KEY=your_key_here`

---

## ⚙️ Configuration

All settings live in `config.py`:

| Setting | Description |
|---------|-------------|
| `LOCATION` | Target city/country, hashtags, keywords, local attractions |
| `VIDEO_CONFIG` | Resolution (1080×1920), FPS, image count, font |
| `SCHEDULE` | Post times, timezone, platforms |
| `CONTENT_STYLE` | Tone, video styles, CTA text |

### Change Target Location

```python
# config.py
LOCATION = {
    "name": "Tokyo",          # ← Change this
    "country": "Japan",       # ← And this
    "language": "en",
    "hashtags": ["#Tokyo", "#Japan", "#VisitJapan", "#travel"],
    "keywords": ["Tokyo travel", "Japan tourism", "things to do Tokyo"],
    "local_attractions": ["Shibuya", "Asakusa", "Mount Fuji"],
}
```

---

## 🏗️ Architecture

Each agent is fully self-contained and can be tested independently:

```python
# Test trend discovery only
from agents.trend_agent import TrendDiscoveryAgent
import asyncio

agent = TrendDiscoveryAgent()
trends = asyncio.run(agent.discover_all_trends())
print(trends["ranked"])
```

```python
# Test script generation only
from agents.script_agent import ScriptWriterAgent
import asyncio

agent = ScriptWriterAgent()
script = asyncio.run(agent.generate_video_script(
    trend_topic="Top 5 hidden gems in Tunis",
    location={"name": "Tunis", "country": "Tunisia", "local_attractions": []},
    style="top 5 hidden gems"
))
print(script["hook"])
```

---

## 🔄 Pipeline Flow

```
┌─────────────────────────────────────────────────────┐
│                  run_full_pipeline()                 │
├──────┬──────────────────────────────────────────────┤
│  1   │  TrendDiscoveryAgent.discover_all_trends()   │
│  2   │  ScriptWriterAgent.generate_video_script()   │
│  3   │  ImageCollectorAgent.collect_all_images()    │
│  4   │  ImageCollectorAgent.add_text_overlay()      │
│  5   │  VoiceGeneratorAgent.generate_voice()        │
│  6   │  MusicAgent.search_pixabay_music()           │
│  7   │  MusicAgent.mix_audio()                      │
│  8   │  VideoCreatorAgent.create_image_slideshow()  │
│      │  VideoCreatorAgent.add_text_overlays()       │
│      │  VideoCreatorAgent.add_intro_animation()     │
│      │  VideoCreatorAgent.add_outro_animation()     │
│      │  VideoCreatorAgent.export_video()            │
│  9   │  PublisherAgent.publish_to_all_platforms()   │
│  10  │  AnalyticsAgent.log_content()                │
│      │  scheduler.schedule_analytics() (+24h)       │
└──────┴──────────────────────────────────────────────┘
```

---

## 🛡️ Error Handling

- Every API call is wrapped in try/except with fallbacks
- ElevenLabs → gTTS → pyttsx3 (voice fallback chain)
- Pixabay music → generated ambient drone (music fallback)
- Missing images → colour placeholder images
- YouTube API unavailable → skip YouTube, continue to other platforms
- Telegram notification on critical failure (if bot configured)
- Pipeline never crashes from a single agent failure

---

## 📊 Analytics

After 24 hours, the agent automatically fetches metrics and stores them in SQLite.

Run a report at any time:
```bash
python main.py --analytics
```

Output: `output/reports/report_YYYY_WW.html` — open in any browser.

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| `moviepy` not found | `pip install moviepy` + install ffmpeg |
| Video creation silent | Check `output/audio/` for generated audio files |
| Gemini returns empty | Verify `GEMINI_API_KEY` in `.env` |
| Images all placeholders | Check Unsplash/Pexels/Pixabay keys |
| YouTube upload fails | Re-run OAuth flow to refresh `YOUTUBE_REFRESH_TOKEN` |
| Instagram 400 error | Ensure you have an **Instagram Business** account linked to a Facebook Page |
| pytrends rate limit | Add longer `time.sleep()` in `trend_agent.py` |

---

## 📝 License

MIT – free to use, modify, and distribute.
