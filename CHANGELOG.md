# Changelog

## [Unreleased]

### Added
- Multi-channel YouTube OAuth management (connect/disconnect multiple channels)
- `channels_manager.py` — single source of truth for channel manifest and token I/O
- `GET /api/channels` — list connected channels
- `POST /api/channels/connect` — start OAuth flow (non-daemon background thread)
- `GET /api/channels/connect/status` — poll OAuth flow status
- `DELETE /api/channels/<channel_id>` — disconnect channel
- Dashboard header shows connected channels side by side with avatars
- Platform picker on "Add Channel" button (YouTube active, Instagram/TikTok coming soon)
- Per-schedule channel selector dropdown
- Setup wizard banner — shown on first launch when required config is missing
- `GET /api/setup/status` endpoint — checks OAuth credentials and API keys
- Full README with installation guide, Google Cloud Console step-by-step, troubleshooting

### Changed
- Settings > CHANNEL section replaced with YouTube OAuth channel manager
- New BRANDING section for CTA text and accent color
- `get_youtube_client()` now accepts `channel_id` parameter
- `upload_video()` now accepts `channel_id` parameter
- `start_pipeline_async()` and `_run_pipeline()` propagate `channel_id` through pipeline
- Scheduler reads `channel_id` from each schedule record
- `api_schedules_toggle` PATCH endpoint handles `channel_id` field
- Legacy `youtube_token.json` automatically migrated to `channels/` structure on startup
- Removed all hardcoded personal channel identifiers from source code
- `config.py` — added `CHANNELS_DIR`, `CHANNELS_FILE` constants

### Security
- Cleared hardcoded ElevenLabs voice ID from config, settings, and providers
- Removed channel-specific tags and names from upload_youtube.py and generate_content.py
- `.gitignore` updated to exclude `channels/`, `channels.json`, tool dirs, internal docs
