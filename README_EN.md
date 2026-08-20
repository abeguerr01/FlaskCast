# 📺 FlaskCast — Local Multimedia Platform

> **[📖 Leer en Español](README.md)**

<table>
  <tr>
    <td><img src="static/logo.png" alt="FlaskCast Logo" width="500"></td>
    <td style="vertical-align: middle; padding-left: 20px;">
      <p>FlaskCast is a personal and local multimedia streaming portal built with Python and Flask. It allows you to organize series and movie catalogs from folders, automatically generate thumbnails, transcode incompatible formats in the background with FFmpeg, save per-user watch progress, and manage content through a REST API.</p>
    </td>
  </tr>
</table>

---

> **⚠ Legal Notice and Disclaimer**
>
> FlaskCast is a private, local-use tool designed exclusively for organizing and playing multimedia content for which the user holds the legal rights. Under no circumstances does FlaskCast facilitate, promote, or allow the obtaining or distribution of copyrighted content without proper authorization.
>
> The user is solely responsible for the content they host, organize, and play through this application. The developer of FlaskCast declines all responsibility arising from misuse of this tool in relation to material for which the user does not have legal rights.
>
> Using FlaskCast implies acceptance of these conditions.

---

## Key Features

- **Folder-based catalog:** organize series, seasons, and episodes directly from the file system.
- **Movie/Series differentiation:** automatic detection by folder structure, with visual badge 🎬/📺 and catalog filter. Manual override via `_meta.json` or `content_metadata` table.
- **Continue Watching:** prominent section in the catalog showing in-progress episodes sorted by recency, with percentage bar.
- **Asynchronous transcoding:** converts `.avi`/`.mkv` to `.mp4` in the background using FFmpeg, with automatic detection of the best available H.264 encoder (`libx264`, `libopenh264`, `h264_nvenc`, etc.), real-time progress bar, and success/failure verification.
- **Dynamic thumbnails:** extracts `.jpg` frames for previews.
- **Per-user tracking:** saves exact position (seconds), marks "Watching" and "Watched" based on configurable thresholds.
- **Custom lists:** organize content into Favorites, Pending, Watching, and Watched with filterable tabs.
- **Catalog pagination:** 24 items per page with navigation controls.
- **Light/Dark theme:** toggle between dark (default) and light theme, saved per user.
- **SPA transitions:** page navigation with fade animations and AJAX fetch.
- **Complete REST API:** add, delete, list, download videos and manage progress through toggle-protected endpoints.
- **Live Streaming:** play live streams (HLS, iframes, videos) with M3U list support, SmartTV mode, and **automatic multi-source fallback**.
- **SmartTV Mode:** player optimized for TVs connected to the local network.
- **Auto-play:** the player automatically advances to the next episode in the season.
- **Responsive interface:** adaptable design with collapsible sidebar on mobile (hamburger menu), breakpoints at 900px, 768px and 480px.
- **Lightweight interface:** HTML5, CSS, and Vanilla JavaScript for playback and real-time search.
- **Multi-language (i18n):** Spanish/English support with per-user switching. OMDb genres and descriptions are auto-translated.
- **OMDb integration:** automatic fetching of covers, descriptions, ratings, and metadata from OMDb API. Key stored in `.env`.
- **Hero design:** detail view with blurred cover banner, visual metadata, and action buttons.
- **Admin panel GUI:** visual management of content, streams, configuration, and OMDb with tkinter interface (5 tabs, bilingual ES/EN).

---

## Technologies

- Backend: Python 3 + Flask
- Database: SQLite3 (`flaskcast.db`)
- Video processing: FFmpeg (automatic management with `static-ffmpeg`)
- Concurrency: `threading` to avoid conversion collisions
- Rate Limiting: Flask-Limiter (API abuse protection)
- Frontend: HTML5, CSS3 and JavaScript
- Template Engine: Jinja2 with template inheritance (`base.html`)
- Production servers: Waitress (Windows) / Gunicorn (Linux)
- Compression: py7zr (export/import content)
- Translation: MyMemory API (descriptions) + local dictionary (genres)

---

## Quick Installation

1. Clone or download the project and navigate to the root folder:

```bash
git clone <repo> && cd FlaskCast
```

2. Create and activate a virtual environment (recommended):

```bash
python -m venv venv
venv\Scripts\activate    # Windows
source venv/bin/activate # Linux / macOS
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the application:

```bash
python app.py
```

Access from your browser at `http://localhost:5000` or using your machine's IP on the local network.

### Dependency Notes

> **⚠️ Linux:** FFmpeg is **required**. The application will not start without it.

<details>
<summary>📥 Install FFmpeg on Linux (click to expand)</summary>

```bash
# Debian / Ubuntu / Linux Mint / Pop!_OS
sudo apt-get update && sudo apt-get install -y ffmpeg

# Fedora / RHEL / CentOS / Rocky / AlmaLinux
sudo dnf install -y ffmpeg

# Arch Linux / Manjaro / EndeavourOS
sudo pacman -S --noconfirm ffmpeg

# openSUSE / SUSE
sudo zypper install -y ffmpeg

# Alpine Linux
sudo apk add ffmpeg

# Void Linux
sudo xbps-install -Sy ffmpeg

# Gentoo
sudo emerge media-video/ffmpeg
```

</details>

> **🪟 Windows/macOS:** `static-ffmpeg` will download and configure FFmpeg binaries automatically the first time the application runs. No manual installation needed.

- **`py7zr`** is used for the export/import multimedia content functions in the admin panel.
- **`Flask-Limiter`** provides rate limiting to protect against API abuse.
- **`waitress`** (Windows) and **`gunicorn`** (Linux) are used as production WSGI servers.

### Production Deployment

On Windows, FlaskCast uses **Waitress** (6 threads). On Linux/Unix, it uses **Gunicorn** (1 worker, 6 threads) to share conversion state in memory. The port is configured in `data/config.json` or through the admin panel.

### Docker

```bash
docker-compose up --build
```

> **Docker Note:** if you run FlaskCast via `docker-compose`, port changes from `config_admin.py` will not take effect. The port is defined in the `docker-compose.yml` file via the `ports:` mapping.

---

## Environment Variables

FlaskCast uses a `.env` file in the project root to store sensitive credentials. This file is included in `.gitignore` and **is not uploaded to the repository**.

| Variable | Description |
|----------|-------------|
| `OMDB_API_KEY` | OMDb API key for fetching metadata and covers. Automatically saved when validated from the admin panel or can be configured with `--omdb-key`. |

---

## Project Structure

```
.
├── app.py                   # Flask application (routes, API, DB, FFmpeg)
├── config_admin.py          # Admin panel (GUI tkinter + CLI)
├── translations.py          # i18n system (ES/EN), metadata translation
├── requirements.txt
├── .env                     # Environment variables (OMDB_API_KEY) — gitignored
├── Dockerfile
├── docker-compose.yml
├── data/
│   ├── config.json          # Server configuration
│   ├── flaskcast.db         # SQLite database
│   ├── live_streams.json    # Live streams configuration
│   └── media/               # Multimedia content
├── static/
│   ├── css/
│   │   └── estilos.css      # Global styles (theme, responsive, skeletons, badges, hero)
│   ├── js/
│   │   └── reproductor.js   # Video player logic
│   └── logo.png
└── templates/
    ├── base.html            # Base template (sidebar, SPA transitions, layout)
    ├── index.html           # Main catalog with pagination, filters and continue watching
    ├── serie.html           # Series/movie detail with hero banner and episodes
    ├── listas.html          # Personal lists (Favorites, Pending, Watching, Watched)
    ├── player_tv.html       # SmartTV player (no sidebar)
    ├── live.html            # Live streams listing
    ├── live_tv.html         # SmartTV player for streams (no sidebar)
    ├── usuarios.html        # User management panel
    └── ajustes.html         # Settings panel (theme, language, auto-marking)
```

### Data Files (not versioned)

| File | Content |
|------|---------|
| `.env` | `OMDB_API_KEY` — OMDb API key |
| `data/config.json` | Port, shutdown buttons, API enabled, admin language |
| `data/flaskcast.db` | SQLite: users, progress, favorites, lists, content_metadata |
| `data/live_streams.json` | Live channel definitions |
| `data/media/` | Series/movie folders, covers, thumbnails |

---

## Database

FlaskCast uses SQLite with WAL mode for concurrency. Tables are created automatically when the application starts.

| Table | Description |
|-------|-------------|
| `usuarios` | User profiles (name, emoji, theme, language, auto_mark, show_progress) |
| `progreso` | Watch position per user and video (seconds, watched, duration) |
| `favoritos` | Series/movies marked as favorites by user |
| `listas` | List status per user and series (0=Pending, 1=Watching, 2=Watched) |
| `content_metadata` | Manual content type override (movie/series) |

---

## Template Inheritance

All templates inherit from `base.html` using Jinja2:

```html
{% extends 'base.html' %}

{% block title %}My Page{% endblock %}

{% block head %}
    <style>/* Specific styles */</style>
{% endblock %}

{% block content %}
    <!-- Page content -->
{% endblock %}
```

`base.html` includes:
- Navigation sidebar (hidden in SmartTV players)
- Extensible blocks: `title`, `head`, `content`, `body_class`, `sidebar`

---

## Multimedia Catalog Structure (required)

Place your content in `data/media/` following this pattern:

```
data/
└── media/
    ├── Series Name A/
    │   ├── _img.png                 <-- Cover (required to show image)
    │   ├── _meta.json               <-- Metadata (optional, manual override)
    │   ├── Season 1/
    │   │   ├── Episode_01.mp4
    │   │   └── Episode_02.avi
    │   └── Season 2/
    │       ├── Episode_01.mkv
    │       └── Episode_02.mp4
    ├── Series Name B (No Seasons)/
    │   ├── _img.png
    │   ├── Video_01.mp4
    │   └── Video_02.mp4
    └── My Movie/
        ├── _img.png
        └── movie.mp4
```

- The cover file must be named exactly `_img.png`. If it doesn't exist, the interface will show a generic icon (🎬 or 📺 depending on the type).
- If you don't use season subfolders, videos in the root will appear under "Available Content".

### `_meta.json` File

The `_meta.json` file allows defining metadata and forcing the content type. Full format:

```json
{
  "tipo": "pelicula",
  "titulo": "My Movie",
  "descripcion": "A movie description.",
  "anio": "2024",
  "genero": ["Action", "Adventure"],
  "director": "Director Name",
  "valoracion": "8.5",
  "duracion_min": 120,
  "temporadas": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `tipo` | string | `"pelicula"` or `"serie"` — forces the detected type |
| `titulo` | string | Display title of the content |
| `descripcion` | string | Description (auto-translated to Spanish if user has ES language) |
| `anio` | string | Release year |
| `genero` | array | List of genres in English (auto-translated) |
| `director` | string | Director name |
| `valoracion` | string | Rating (e.g. `"8.5"`) |
| `duracion_min` | integer | Duration in minutes (movies) |
| `temporadas` | integer | Number of seasons (series) |

The fields `titulo`, `descripcion`, `anio`, `genero`, `director`, `valoracion`, `duracion_min` and `temporadas` are automatically filled when applying OMDb metadata.

### Movie / Series Differentiation

FlaskCast automatically detects whether a folder is a movie or a series through a 3-level system:

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | `content_metadata` table (DB) | Manual override saved in the database |
| 2 | `_meta.json` file | `tipo` field in the metadata file |
| 3 | Folder structure | Subfolders = series, videos only = movie |

**UI Differences:**

- **Catalog:** 🎬 (gold) or 📺 (blue) badge on each card, with "All / Movies / Series" filter
- **Detail view:** movies show "🎬 Movie" as section title and hide the seasons accordion; series show "Available Seasons" with expandable accordion
- **Hero banner:** detail view with blurred cover banner, visual metadata (year, genre, director, rating, duration) and action buttons

---

## Metadata Translation (i18n)

FlaskCast automatically translates OMDb metadata based on the user's language:

- **Genres:** translated locally using a dictionary of 26 genres (English → Spanish) in `translations.py`.
- **Descriptions:** translated in real-time using the free [MyMemory](https://mymemory.translated.net/) API with no API key needed.
- **Fallback:** if translation fails, the original English text is shown.

---

## Format Management and Transcoding

- Native web formats (`.mp4`, `.webm`, `.ogg`) play directly.
- Non-native formats (`.avi`, `.mkv`) appear as "Pending" and can be converted to `.mp4` via a button in the interface.
- Conversion is performed asynchronously; the app uses `threading` and locks to avoid conflicts in simultaneous conversions.
- **Automatic codec detection:** on startup, the app runs `ffmpeg -encoders` and selects the best available H.264 encoder. Compatible with `libx264` (Windows), `libopenh264` (Linux/Fedora), `h264_nvenc`, `h264_amf`, `h264_qsv`, `h264_vaapi`.
- **Real-time progress:** the conversion bar shows the advance percentage by parsing FFmpeg's stderr output.
- **Success verification:** FFmpeg's exit code and the existence of the `.mp4` file are checked before marking as completed.
- **Hidden during conversion:** the `.mp4` file does not appear in the interface until the conversion reaches 100%.
- **Process isolation:** FFmpeg runs in a new session to survive `Ctrl+C` without aborting the conversion.
- Conversion: FFmpeg with detected codec (video) + AAC (audio), CRF 23.

---

## Users and Progress Tracking

- You can create user profiles with name and emoji from the user panel.
- The player sends periodic updates to the server, saving the current timestamp to the database.
- **Auto-marking thresholds:**
  - >10% played → "Watching" state (blue).
  - >85% played → "Watched" state (green).
- You can also manually mark an episode as "Watched" from the UI.
- Each user has their own preferences: theme, language, auto-marking, show progress.

---

## Continue Watching

The main catalog includes a **"▶ Continue Watching"** section showing up to 12 in-progress episodes (state `visto = 1`), sorted by most recently watched. Each card shows a percentage progress bar. Clicking resumes playback from the saved position.

---

## Personal Lists

FlaskCast includes a lists page (`/listas`) where users can organize their content:

### Filter Tabs

| Tab | Color | Description |
|-----|-------|-------------|
| ⭐ Favorites | Gold (#f5a623) | Series/movies marked as favorites |
| 📋 Pending | Gray (#888) | Content pending to watch |
| 👁️ Watching | Blue (#0d6efd) | Content in progress |
| ✅ Watched | Green (#1fcc72) | Completed content |

- When opening the page, the "Favorites" tab is shown by default.
- Clicking a tab shows only that section; clicking again hides it (toggle).
- Each card shows a type badge (🎬/📺) according to the content.
- Favorites are managed from the ⭐ button in the detail view of each series.
- Pending/Watching/Watched are managed from the "＋ Add" button in the detail view.

---

## Catalog Pagination

The main catalog shows 24 items per page with navigation controls:

- Page buttons with ellipsis (`...`) for long jumps.
- "Previous" / "Next" buttons for sequential navigation.
- Range indicator: "Showing X–Y of Z items".
- Pagination is server-side; each page loads its own subset of data.

---

## Responsive Design

FlaskCast automatically adapts to screen size:

| Breakpoint | Behavior |
|------------|----------|
| > 900px | Full layout with fixed sidebar |
| ≤ 900px | Collapsible sidebar with hamburger menu |
| ≤ 768px | Adjusted card grid, compact header |
| ≤ 480px | 2-column grid, stacked controls |

- **Hamburger menu:** 3-line button that opens/closes the sidebar on mobile.
- **Overlay:** when opening the sidebar, a dark overlay appears that closes it on click.
- **SPA transitions:** page navigation uses fade animations with skeleton loading during load.

---

## SPA Transitions (Single Page Application)

FlaskCast simulates SPA navigation using AJAX:

1. When clicking an internal link, the current content fades out.
2. A skeleton placeholder is shown while the new page loads.
3. The new content is injected with fade-in animation.
4. The URL is updated with `history.pushState()`.
5. The sidebar is updated to reflect the active section.

Excluded from transitions: external links, `#` anchors, modals, players, and elements with `data-no-transition`.

---

## Live Streaming (Live Content)

FlaskCast includes a live streaming section for playing TV channels, radios, or any live stream from the web interface.

### Stream Configuration

Streams are configured in the `data/live_streams.json` file. If the file doesn't exist, create it manually with the following format:

```json
[
  {
    "titulo": "Example Channel",
    "url": "http://example.com/stream.m3u8",
    "tipo": "auto"
  },
  {
    "titulo": "HLS Channel with Fallback",
    "urls": [
      "https://primary.com/stream.m3u8",
      "https://backup1.com/stream.m3u8",
      "https://backup2.com/stream.m3u8"
    ],
    "tipo": "hls"
  },
  {
    "titulo": "Iframe Channel",
    "url": "https://example.com/embedded-player",
    "tipo": "iframe"
  },
  {
    "titulo": "Full M3U List",
    "url": "https://example.com/channels.m3u",
    "tipo": "m3u"
  }
]
```

Streams can also be managed visually from the **"Streamings"** tab of the admin panel (`config_admin.py`).

### Multiple URLs and Automatic Fallback

Each stream can define multiple playback sources using the `urls` field (array). When a source fails, the player **automatically jumps to the next** without user intervention.

- If only `"url"` (string) is used, it behaves as a single source.
- If `"urls"` (array) is used, the player will try each source in order until one works.
- The `"url"` field is kept for backward compatibility; if `"urls"` is provided, it takes priority.

### Supported Stream Types

| Type | Description | Example |
|------|-------------|---------|
| `auto` | Automatically detects type by extension (.mp4, .m3u8, etc.) | `http://server/video.mp4` |
| `hls` | HLS stream (m3u8) with native support or via HLS.js | `https://server/live.m3u8` |
| `video` | Direct video file (mp4, webm, ogg) | `http://server/film.mp4` |
| `iframe` | Embedded page in iframe (third-party players) | `https://tv.com/player/123` |
| `m3u` | M3U list that is automatically parsed into multiple channels | `https://list.com/channels.m3u` |

### M3U Format

The parser supports both remote (HTTP/HTTPS) and local M3U lists. Expected format:

```
#EXTM3U
#EXTINF:-1 tvg-name="Channel 1",Channel 1
http://server/channel1/stream.m3u8
#EXTINF:-1 tvg-name="Channel 2",Channel 2
http://server/channel2/stream.m3u8
```

### Access

- **Channel list:** `http://localhost:5000/live`
- **SmartTV player:** `http://localhost:5000/live/tv/<index>` (where `<index>` is the channel position in the list, starting at 0)

### Live Player Features

- **PC Modal:** clicking "Watch" opens an overlapped modal player.
- **SmartTV Mode:** optimized view with full screen and large controls for TVs.
- **HLS Support:** uses HLS.js as a fallback when the browser doesn't support native HLS (all except Safari).
- **Automatic Fallback:** if a stream fails, the player tries the next available URL without user intervention.
- **SmartTV with HLS.js:** the SmartTV player includes HLS.js from CDN, enabling HLS playback in browsers without native support.
- **Escape Key:** closes the modal player.

---

## SmartTV Mode

FlaskCast includes a player optimized for Smart TVs that allows watching both catalog videos and live streams.

### Video Player (SmartTV)

```
http://localhost:5000/tv/reproducir/<series_name>/<season>/<file.mp4>
```

Features:
- Auto-play on load
- Full screen by default
- Info bar with video title
- Button to return to streams list

### Live Stream Player (SmartTV)

```
http://localhost:5000/live/tv/<index>
```

- Supports direct video, HLS (with HLS.js) and iframes
- Automatic fallback between multiple sources
- Designed to be controlled with the TV remote

---

## Settings

From the settings panel (`/ajustes`) you can configure:

- **Language:** switch between Spanish and English. The preference is saved per user in the DB and applies to the entire interface and OMDb metadata.
- **Theme:** switch between dark (default) and light theme. The preference is saved per user in the DB.
- **Auto-marking:** enable or disable automatic state changes "Watching"/"Watched" based on playback progress.
- **Show progress:** enable or disable the progress bar on episode cards.
- **Enable API:** enable or disable REST endpoints. When enabled, endpoints require a user session. An informational button (`i`) shows the complete API documentation in a modal. This option is managed from the admin panel (`config_admin.py`).

---

## Multi-language (i18n)

FlaskCast supports Spanish and English across the entire interface:

- **Web:** ~160 translated strings in `translations.py` (section `TRANSLATIONS`). Per-user switching from settings.
- **Admin panel:** ~140 translated strings (section `ADMIN_TRANSLATIONS`). Switch from the "Language" tab.
- **Genres:** 26 locally translated genres (English → Spanish) in `GENRE_TRANSLATIONS`.
- **Descriptions:** automatic real-time translation via MyMemory API (free, no key needed).
- **Fallback:** if the language is English, metadata is shown untranslated; if translation fails, the original text is shown.

---

## Rate Limiting (Abuse Protection)

FlaskCast includes rate limiting via `Flask-Limiter` to protect the API and web routes from request floods and abuse.

### Configured Limits

| Endpoint | Limit | Reason |
|----------|-------|--------|
| General (all routes) | 200/min | Base protection |
| `POST /api/videos/add` | 10/min | Prevent mass uploads |
| `POST /api/videos/rm` | 10/min | Prevent mass deletions |
| `POST /api/convertir/...` | 5/min | Conversions are heavy |
| `POST /api/eliminar/...` | 10/min | Prevent mass deletions |
| `POST /api/progreso/guardar` | 60/min | Called frequently during playback |
| `POST /api/favoritos/toggle` | 30/min | Moderate operation |
| `POST /api/lista/guardar` | 30/min | Moderate operation |
| `POST /usuarios/crear` | 5/min | Prevent mass user creation |
| `POST /usuarios/editar` | 10/min | Moderate |
| `POST /usuarios/eliminar` | 5/min | Destructive operation |
| `GET /api/off` | 2/min | Critical |
| `GET /api/off/all` | 1/min | Critical |

### Response When Limit Is Exceeded

```json
{
  "error": "Too Many Requests",
  "message": "You have exceeded the rate limit. Please slow down.",
  "retry_after": 42
}
```

HTTP status code: `429 Too Many Requests`

---

## Admin Panel (config_admin.py)

FlaskCast includes an admin panel (`config_admin.py`) with a graphical interface (GUI) in tkinter and command-line mode (CLI). It has **5 tabs** and bilingual support (ES/EN).

### Graphical Mode (GUI)

Open the admin window without passing any arguments:

```bash
python config_admin.py
```

#### General Tab

- **Show "Shutdown Server" button:** toggles visibility of the button that stops only the Flask process.
- **Show "Shutdown All" button:** toggles visibility of the button that shuts down the entire operating system.
- **Enable REST API:** toggles REST API endpoints.
- **Port:** changes the port the server listens on (requires restarting the application).
- **Export media (.fkmedia):** compresses the entire `data/media/` folder into a `.fkmedia` file (7z format internally).
- **Import media (.fkmedia):** selects a previously exported `.fkmedia` file and extracts it to `data/media/`.
- **Save and Close:** applies changes and closes the window.

#### OMDb Tab

- Input field for the **OMDb API key** with real-time validation.
- The key is automatically saved to the `.env` file on successful validation.
- **Library tree** showing all multimedia folders with columns: name, type (movie/series), has metadata, has cover.
- **"Apply OMDb" button** that searches and applies metadata automatically (title, description, year, genre, director, rating, duration/seasons) and downloads the cover as `_img.png`.

#### Library Tab

- **Hierarchical tree** with the entire multimedia structure (Series → Seasons → Videos, Movies → Videos).
- Shows file sizes in MB.
- **Available actions:**
  - Add movie or series (single dialog with metadata fields: title, description, year, genre, director, rating, type, duration, seasons).
  - Add season.
  - Add video (copy from local machine).
  - Edit metadata (updates `_meta.json` and `content_metadata` table in DB).
  - Rename (cascade in DB: content_metadata, favorites, progress, lists).
  - Delete (with confirmation, cleans thumbnails and progress).
- **Context menu** (right-click) with options depending on the selected node level.

#### Streamings Tab

- **Complete CRUD** for live streams stored in `data/live_streams.json`.
- Tree with columns: title, main URL, type.
- **Actions:** add, edit, delete, move up/down (reorder), refresh.
- Each stream has: title, main URL, backup URLs (one per line), type (hls/iframe/video).

#### Language Tab

- Radio buttons for Spanish (ES) and English (EN).
- When changing the language, the entire interface rebuilds in the selected language.
- The preference is saved in `data/config.json` (`admin_idioma`).

#### Linux Note

`config_admin.py` uses `tkinter`, which is not always included by default in some Linux distributions. If you get an error like `ModuleNotFoundError: No module named 'tkinter'` when running it, install it with:

```bash
sudo apt install python3-tk    # Debian / Ubuntu
sudo dnf install python3-tkinter  # Fedora
sudo pacman -S tk              # Arch Linux
```

### Command-Line Mode (CLI)

Useful for headless servers without a graphical interface. Allows modifying configuration and managing multimedia files directly from the terminal.

```bash
python config_admin.py [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `--status` | Shows current server configuration (includes OMDb key status) |
| `--toggle-server` | Toggles the "Shutdown Server" button |
| `--toggle-all` | Toggles the "Shutdown All" button |
| `--api` | Toggles the REST API |
| `--port PORT` | Changes the server port (1-65535) |
| `--omdb-key API_KEY` | Saves an OMDb API key to the `.env` file |
| `--export FILE` | Exports `data/media/` to a `.fkmedia` file |
| `--import FILE` | Imports a `.fkmedia` file to `data/media/` |

Multiple flags can be combined in a single run:

```bash
python config_admin.py --api --toggle-all --port 8080
```

Practical examples:

```bash
# View current configuration
python config_admin.py --status

# Enable the REST API
python config_admin.py --api

# Change port to 8080
python config_admin.py --port 8080

# Save OMDb key
python config_admin.py --omdb-key your_key_here

# Export all multimedia content
python config_admin.py --export backup.fkmedia

# Import content from a backup
python config_admin.py --import backup.fkmedia
```

---

## REST API

FlaskCast includes a REST API protected by user session and activated from the admin panel. All endpoints require the session cookie header and that the user has the API enabled. **All endpoints are protected with rate limiting.**

### 📤 Add Video

```
POST /api/videos/add
Content-Type: multipart/form-data
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `serie` | string (required) | Series name |
| `temporada` | string | Required if the series has subfolders. Don't use if it doesn't. |
| `archivo` | file (required) | Video file to upload |

```bash
curl -X POST http://localhost:5000/api/videos/add \
  -b "session=YOUR_SESSION" \
  -F "serie=My Series" \
  -F "temporada=Season 1" \
  -F "archivo=@/path/to/video.mp4"
```

### 📋 List Structure

```
GET /api/videos             → All series and their episodes
GET /api/videos/My%20Series → A specific series
```

```bash
curl http://localhost:5000/api/videos -b "session=YOUR_SESSION"
```

### 🎬 Get Video

```
GET /api/video/<series>/<path/to/file.mp4>
```

```bash
curl http://localhost:5000/api/video/My%20Series/Season%201/ep1.mp4 \
  -b "session=YOUR_SESSION" -o ep1.mp4
```

### 🗑️ Delete Video (API)

```
POST /api/videos/rm
Content-Type: application/json
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `serie` | string (required) | Series name |
| `filename` | string (required) | File path within the series |

```bash
curl -X POST http://localhost:5000/api/videos/rm \
  -b "session=YOUR_SESSION" \
  -H "Content-Type: application/json" \
  -d '{"serie": "My Series", "filename": "Season 1/video.mp4"}'
```

### 🔄 Convert Video (API)

Starts the conversion of an incompatible video (`.avi`, `.mkv`) to `.mp4` in the background.

```
POST /api/convertir/<series>/<path/file.avi>
```

**Response:**
```json
{"status": "procesando"}
```

If a `.mp4` file with the same name already exists:
```json
{"status": "ya_existe_mp4"}
```

If a conversion is already in progress:
```json
{"status": "ya_en_progreso"}
```

```bash
curl -X POST http://localhost:5000/api/convertir/My%20Series/Season%201/ep1.avi \
  -b "session=YOUR_SESSION"
```

### 🗑️ Delete File Directly (API)

Deletes a specific file without needing the "videos/rm" endpoint.

```
POST /api/eliminar/<series>/<path/file.mp4>
```

```bash
curl -X POST http://localhost:5000/api/eliminar/My%20Series/Season%201/ep1.mp4 \
  -b "session=YOUR_SESSION"
```

### 📊 Check Active Conversions (API)

Returns the list of video identifiers currently being converted, along with the progress percentage of each.

```
GET /api/estados
```

**Response:**
```json
{"activos": ["My Series/Season 1/ep1.avi"], "progreso": {"My Series/Season 1/ep1.avi": 42}}
```

```bash
curl http://localhost:5000/api/estados -b "session=YOUR_SESSION"
```

### 🔍 Check Conversion Result (API)

Returns the result of a completed conversion (success or failure).

```
GET /api/conversion_result/<series>/<file>
```

**Response:**
```json
{"status": "ok", "mp4_exists": true}
```

```bash
curl http://localhost:5000/api/conversion_result/My%20Series/Season%201/ep1.avi \
  -b "session=YOUR_SESSION"
```

### 💾 Save Watch Progress (API)

Saves the playback position of a video for the current user.

```
POST /api/progreso/guardar
Content-Type: application/json
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `serie` | string (required) | Series name |
| `filename` | string (required) | File path (e.g. `Season 1/ep1.mp4`) |
| `segundos` | number | Current position in seconds |
| `duracion` | number | Total video duration |
| `visto` | number | Forced state (0=Unwatched, 1=Watching, 2=Watched) — optional |

**Note:** If the `visto` field is sent, automatic calculation is ignored and that state is forced.

```bash
curl -X POST http://localhost:5000/api/progreso/guardar \
  -b "session=YOUR_SESSION" \
  -H "Content-Type: application/json" \
  -d '{"serie": "My Series", "filename": "Season 1/ep1.mp4", "segundos": 1250, "duracion": 3600}'
```

### 📥 Get Watch Progress (API)

Gets the saved position and state of a video for the current user.

```
GET /api/progreso/obtener?serie=<series>&filename=<file>
```

**Response:**
```json
{"segundos": 1250, "visto": 1}
```

```bash
curl "http://localhost:5000/api/progreso/obtener?serie=My%20Series&filename=Season%201/ep1.mp4" \
  -b "session=YOUR_SESSION"
```

### ⭐ Toggle Favorites (API)

Adds or removes a series/movie from the favorites list.

```
POST /api/favoritos/toggle
Content-Type: application/json
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `serie` | string (required) | Series/movie name |

**Response:**
```json
{"favorito": true}
```

### 📋 Save List State (API)

Saves the state of a series in the user's list.

```
POST /api/lista/guardar
Content-Type: application/json
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `serie` | string (required) | Series name |
| `estado` | integer | 0=Pending, 1=Watching, 2=Watched |

### 📥 Get List State (API)

```
GET /api/lista/estado?serie=<series>
```

### 📥 Get All Lists (API)

```
GET /api/lista/obtener
```

### 🖥️ Open Admin Panel (API)

Opens the `config_admin.py` window (only accessible from localhost).

```
GET /api/abrir_config_admin
```

### 🏓 Ping (API)

Checks if the server is active.

```
GET /api/ping
```

**Response:**
```json
{"status": "servidor en linea"}
```

```bash
curl http://localhost:5000/api/ping
```

### ⏻ Shutdown Server (API)

Stops only the FlaskCast process. Only works if enabled in `config_admin.py`.

```
GET /api/off
```

**Response:**
```json
{"status": "Apagando servidor..."}
```

### ⏻ Shutdown System (API)

Shuts down the entire operating system. Only works if enabled in `config_admin.py`.

```
GET /api/off/all
```

**Response:**
```json
{"status": "Apagando sistema..."}
```

---

## Multimedia Service Endpoints

These endpoints serve audiovisual content directly from the browser. No authentication required.

| Endpoint | Description |
|----------|-------------|
| `GET /video/<series>/<file>` | Serves a video file for browser playback |
| `GET /thumbnail/<series>/<file>` | Serves or auto-generates a video thumbnail (frame at 3 seconds) |
| `GET /portada/<series>` | Serves the `_img.png` cover image of a series |
| `GET /serie/<series_name>` | Web page with the series episode catalog |
| `GET /tv/reproducir/<series>/<file>` | SmartTV-optimized player |

### Examples

```
http://localhost:5000/video/My%20Series/Season%201/ep1.mp4
http://localhost:5000/thumbnail/My%20Series/Season%201/ep1.mp4
http://localhost:5000/portada/My%20Series
http://localhost:5000/serie/My%20Series
http://localhost:5000/tv/reproducir/My%20Series/Season%201/ep1.mp4
```

### Automatic Thumbnail Generation

When a thumbnail is requested that doesn't exist, FlaskCast automatically generates a frame extracted at 3 seconds of the video using FFmpeg. Thumbnails are stored in:

```
data/media/<Series>/.thumbnails/<filename>.jpg
```

---

## Player and Auto-play

FlaskCast's player includes advanced tracking and auto-play features.

### Automatic Tracking

- Every 10 seconds, the player sends the current position to the server.
- If the user has enabled "Auto-marking" in Settings:
  - **>10% played** → State changes to "Watching" (blue badge)
  - **>85% played** → State changes to "Watched" (green badge)
- If auto-marking is disabled, states only change when manually clicking the episode label.

### Auto-play Next Episode

When a video finishes, the player automatically loads the next episode in the same season (if available). This feature:

- Only applies to videos in web formats (`.mp4`, `.webm`, `.ogg`)
- Does not advance if it's the last episode of the season
- Shows a "Next" button when finished

### Supported Formats in Player

| Format | Native Support | Conversion Needed |
|--------|---------------|-------------------|
| `.mp4` (H.264) | ✅ Yes | No |
| `.webm` | ✅ Yes | No |
| `.ogg` | ✅ Yes | No |
| `.avi` | ❌ No | Yes (to .mp4) |
| `.mkv` | ❌ No | Yes (to .mp4) |

---

## Endpoint Summary

### Web Routes (require browser)

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Main catalog with pagination, filters and continue watching |
| GET | `/page/<n>` | Paginated catalog |
| GET | `/serie/<name>` | Series/movie detail with hero banner and episodes |
| GET | `/listas` | Personal lists (Favorites, Pending, Watching, Watched) |
| GET | `/tv/reproducir/<series>/<file>` | SmartTV player |
| GET | `/live` | Live streams listing |
| GET | `/live/tv/<index>` | SmartTV player for live streams |
| GET | `/usuarios_panel` | User management panel |
| GET | `/ajustes` | Settings panel (theme, language, auto-marking) |
| GET/POST | `/ajustes` | Save user settings |

### REST API (require session + API enabled)

| Method | Route | Description | Rate Limit |
|--------|-------|-------------|------------|
| POST | `/api/videos/add` | Upload video to a series | 10/min |
| POST | `/api/videos/rm` | Delete video by name | 10/min |
| GET | `/api/videos` | List all series | 200/min |
| GET | `/api/videos/<series>` | Get series structure | 200/min |
| GET | `/api/video/<series>/<file>` | Download/video file | 200/min |
| POST | `/api/convertir/<series>/<file>` | Convert incompatible video to MP4 | 5/min |
| POST | `/api/eliminar/<series>/<file>` | Delete file directly | 10/min |
| GET | `/api/estados` | Check active conversions with progress | 200/min |
| GET | `/api/conversion_result/<series>/<file>` | Check conversion result | 200/min |
| POST | `/api/progreso/guardar` | Save watch position | 60/min |
| GET | `/api/progreso/obtener` | Get saved position | 200/min |
| POST | `/api/favoritos/toggle` | Add/remove from favorites | 30/min |
| GET | `/api/favoritos` | Get favorites list | 200/min |
| GET | `/api/lista/estado` | Get list state for a series | 200/min |
| POST | `/api/lista/guardar` | Save list state (Pending/Watching/Watched) | 30/min |
| GET | `/api/lista/obtener` | Get all user lists | 200/min |
| GET | `/api/abrir_config_admin` | Open admin panel (localhost only) | 200/min |
| GET | `/api/ping` | Check server status | 200/min |
| GET | `/api/off` | Shutdown server (if enabled) | 2/min |
| GET | `/api/off/all` | Shutdown system (if enabled) | 1/min |

### Content Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/video/<series>/<file>` | Serve video file |
| GET | `/thumbnail/<series>/<file>` | Serve/generate thumbnail |
| GET | `/portada/<series>` | Serve series/movie cover |

---

## Useful Commands

- Run locally: `python app.py`
- Virtual environment (Windows): `venv\Scripts\activate`
- Docker: `docker-compose up --build`
- View admin config: `python config_admin.py --status`
- Save OMDb key: `python config_admin.py --omdb-key your_key`

---

## Changelog

### v2.1 — Transcoding Fix and Improvements (2026-08-21)

**Critical Fixes:**

- **Fixed: conversion failing on Linux** — The `libx264` encoder was hardcoded but unavailable on Linux distributions (Fedora/RHEL). The app now auto-detects the best available H.264 encoder on startup: `libx264` → `libopenh264` → `h264_nvenc` → `h264_amf` → `h264_qsv` → `h264_vaapi` → `h264_v4l2m2m`.
- **Fixed: Ctrl+C aborting conversions** — FFmpeg ran as a direct child of the Python process and received SIGINT on Ctrl+C (returncode=255). Now uses `start_new_session=True` to isolate FFmpeg in a separate process session.
- **Fixed: inconsistent state between Gunicorn workers** — With `--workers 4`, each worker had its own `conversiones_activas` in memory. The frontend received "unknown" when querying a worker that didn't have the conversion. Solution: `--workers 1 --threads 6` to share state.
- **Fixed: conversion success verification** — Previously assumed that if the identifier disappeared from `conversiones_activas`, the conversion succeeded. Now verifies `returncode == 0`, `os.path.exists(mp4)`, and `getsize > 0`.

**New Features:**

- **Real-time progress bar** — During conversion, a progress bar with percentage is shown on the chapter card, parsing FFmpeg's `time=HH:MM:SS` stderr output.
- **MP4 hidden during conversion** — Generated `.mp4` files do not appear in the interface until conversion reaches 100%.
- **`/api/conversion_result` endpoint** — New endpoint to check the result of a completed conversion (success/failure + mp4 existence).
- **Detailed logging** — Every step of the conversion is logged to the console: start, FFmpeg PID, progress every 10%, final result with file size, and errors with the last lines of stderr.

**Technical Changes:**

- `hilo_conversion()` rewritten with `subprocess.Popen()` instead of `subprocess.run()`
- `resultados_conversiones` dict stores success/failure per identifier
- `progreso_conversiones` dict stores current percentage per conversion
- `GET /api/estados` now returns `{"activos": [...], "progreso": {...}}`
- Frontend (`verificarEstados()`) branches between success and failure when checking result
- Helper functions `_obtener_duracion()` (ffprobe) and `_parsear_progreso_ffmpeg()`
- CSS: `.conversion-progress`, `.conversion-progress-bar`, `.conversion-progress-text`
- Template `serie.html`: progress bar added to incompatible cards

---

## Contributing and Support

If you want to contribute, open an issue or create a pull request. For major changes, first open an issue describing the proposal.

---

## License

See the `LICENSE` file included in the repository.
