# 📺 FlaskCast — Plataforma Multimedia Local

FlaskCast es un portal de streaming multimedia personal y local construido con Python y Flask. Permite organizar catálogos de series por carpetas, generar miniaturas automáticamente, transcodificar formatos incompatibles en segundo plano con FFmpeg, guardar el progreso de reproducción por usuario y gestionar el contenido mediante una API REST.

---

**Características principales**

- **Catálogo por carpetas:** organiza series, temporadas y capítulos directamente desde el sistema de archivos.
- **Transcodificación asíncrona:** convierte `.avi`/`.mkv` a `.mp4` (H.264) en segundo plano usando FFmpeg (`static-ffmpeg`).
- **Miniaturas dinámicas:** extrae fotogramas como `.jpg` para previsualizaciones.
- **Seguimiento por usuario:** guarda la posición exacta (segundos), marca "En progreso" y "Visto" según umbrales configurables.
- **API REST completa:** añade, elimina, lista, descarga vídeos y gestiona el progreso mediante endpoints protegidos por toggle.
- **Streaming en Vivo:** reproduce streams en directo (HLS, iframes, vídeos) con soporte para listas M3U, modo SmartTV y **fallback automático con múltiples fuentes**.
- **Modo SmartTV:** reproductor optimizado para televisores conectados a la red local.
- **Auto-reproducción:** el reproductor avanza automáticamente al siguiente capítulo de la temporada.
- **Interfaz ligera:** HTML5, CSS y JavaScript Vanilla para reproducción y búsqueda en tiempo real.

---

**Tecnologías**

- Backend: Python 3 + Flask
- Base de datos: SQLite3 (`flaskcast.db`)
- Procesamiento de vídeo: FFmpeg (gestión automática con `static-ffmpeg`)
- Concurrencia: `threading` para evitar colisiones en conversiones
- Frontend: HTML5, CSS3 y JavaScript

---

**Instalación rápida**

1. Clona o descarga el proyecto y sitúate en la carpeta raíz:

```bash
git clone <repo> && cd FlaskCast
```

2. Crea y activa un entorno virtual (recomendado):

```bash
python -m venv venv
venv\Scripts\activate    # Windows
source venv/bin/activate # Linux / macOS
```

3. Instala las dependencias:

```bash
pip install -r requirements.txt
```

Nota: `static-ffmpeg` descargará y configurará los binarios de FFmpeg la primera vez que se ejecute la aplicación. Si prefieres, puedes instalar FFmpeg globalmente en tu sistema.

4. Ejecuta la aplicación:

```bash
python app.py
```

Accede desde el navegador en `http://localhost:5000` o usando la IP de tu equipo en la red local.

Opcional (Docker):

```bash
docker-compose up --build
```

---

**Estructura del proyecto**

```
.
├── app.py                   # Aplicación Flask (rutas, API, BD, FFmpeg)
├── config_gui.py            # Interfaz gráfica para editar config.json
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── data/
│   ├── config.json          # Configuración del servidor (puerto, botones de apagado)
│   ├── flaskcast.db         # Base de datos SQLite (usuarios, progreso)
│   ├── live_streams.json    # Configuración de streams en vivo
│   └── media/               # Contenido multimedia (series / portadas / capítulos)
├── static/
│   ├── css/
│   │   └── estilos.css
│   └── js/
│       └── reproductor.js
└── templates/
    ├── index.html           # Catálogo principal
    ├── serie.html           # Detalle de serie con capítulos
    ├── player_tv.html       # Reproductor SmartTV
    ├── live.html            # Lista de streams en vivo
    ├── live_tv.html         # Reproductor SmartTV para streams
    ├── usuarios.html        # Panel de gestión de usuarios
    ├── ajustes.html         # Panel de configuración
    └── base.html            # Plantilla base
```

---

**Estructura del catálogo multimedia (requerida)**

Coloca tus series en `data/media/` siguiendo este patrón:

```
data/
└── media/
    ├── Nombre de la Serie A/
    │   ├── _img.png                 <-- Portada (obligatoria para mostrar imagen)
    │   ├── Temporada 1/
    │   │   ├── Capitulo_01.mp4
    │   │   └── Capitulo_02.avi
    │   └── Temporada 2/
    │       ├── Capitulo_01.mkv
    │       └── Capitulo_02.mp4
    └── Nombre de la Serie B (Sin Temporadas)/
        ├── _img.png
        ├── Video_Suelto_01.mp4
        └── Video_Suelto_02.mp4
```

- El archivo de portada debe llamarse exactamente `_img.png`. Si no existe, la interfaz mostrará un icono genérico.
- Si no usas subcarpetas de temporada, los vídeos en la raíz de la serie aparecerán bajo "Contenido Disponible".

---

**Gestión de formatos y transcodificación**

- Formatos web nativos (`.mp4`, `.webm`, `.ogg`) se reproducen directamente.
- Formatos no nativos (`.avi`, `.mkv`) aparecen como "Pendiente" y pueden convertirse a `.mp4` mediante un botón en la interfaz.
- La conversión se realiza de forma asíncrona; la app usa `threading` y bloqueos para evitar conflictos en conversiones simultáneas.

---

**Usuarios y seguimiento de progreso**

- Puedes crear perfiles de usuario con nombre y emoji desde el panel de usuarios.
- El reproductor envía actualizaciones periódicas al servidor guardando la marca de tiempo actual en la base de datos.
- Umbrales:
  - >10% reproducido → estado "Viendo" (azul).
  - >85% reproducido → estado "Visto" (verde).
- También puedes marcar manualmente un capítulo como "Visto" desde la UI.

---

**Streaming en Vivo (Contenido en Directo)**

FlaskCast incluye una sección de streaming en vivo que permite reproducir canales de televisión, radios o cualquier stream en directo desde la interfaz web.

### Configuración de streams

Los streams se configuran en el archivo `data/live_streams.json`. Si el archivo no existe, créalo manualmente con el siguiente formato:

```json
[
  {
    "titulo": "Canal de Ejemplo",
    "url": "http://ejemplo.com/stream.m3u8",
    "tipo": "auto"
  },
  {
    "titulo": "Canal HLS con Fallback",
    "urls": [
      "https://principal.com/stream.m3u8",
      "https://backup1.com/stream.m3u8",
      "https://backup2.com/stream.m3u8"
    ],
    "tipo": "hls"
  },
  {
    "titulo": "Canal HLS Simple",
    "url": "https://ejemplo.com/live/playlist.m3u8",
    "tipo": "hls"
  },
  {
    "titulo": "Canal Iframe",
    "url": "https://ejemplo.com/embebed-player",
    "tipo": "iframe"
  },
  {
    "titulo": "Lista M3U Completa",
    "url": "https://ejemplo.com/canales.m3u",
    "tipo": "m3u"
  }
]
```

### Múltiples URLs y fallback automático

Cada stream puede definir múltiples fuentes de reproducción mediante el campo `urls` (array). Cuando una fuente falla (caída del servidor, problemas de red, etc.), el reproductor **salta automáticamente a la siguiente** sin intervención del usuario.

**Formatos soportados (retrocompatibles):**

```json
// Una sola URL (formato simple, retrocompatible)
{
  "titulo": "Canal A",
  "url": "https://stream.com/live.m3u8",
  "tipo": "hls"
}

// Múltiples URLs (fallback automático)
{
  "titulo": "Canal B",
  "url": "https://principal.com/live.m3u8",
  "urls": [
    "https://principal.com/live.m3u8",
    "https://backup1.com/live.m3u8",
    "https://backup2.com/live.m3u8"
  ],
  "tipo": "hls"
}
```

- Si solo se usa `"url"` (string), se comporta como una única fuente.
- Si se usa `"urls"` (array), el player intentará cada fuente en orden hasta encontrar una que funcione.
- El campo `"url"` se mantiene para retrocompatibilidad; si se proporciona `"urls"`, este tiene prioridad.

**¿Cuándo es útil?**

- **Redundancia:** si un servidor CDN cae, el player usa el siguiente automáticamente.
- **Carga balanceada:** distribuir la conexión entre diferentes servidores.
- **Calidad adaptativa:** diferentes enlaces pueden apuntar a distintas calidades (1080p, 720p, 480p).
- **Reducción de latencia:** enlaces de diferentes regiones para usuarios en distintas ubicaciones.

### Tipos de streams soportados

| Tipo | Descripción | Ejemplo |
|------|-------------|---------|
| `auto` | Detecta automáticamente el tipo por extensión (.mp4, .m3u8, etc.) | `http://server/video.mp4` |
| `hls` | Stream HLS (m3u8) con soporte nativo o mediante HLS.js | `https://server/live.m3u8` |
| `video` | Archivo de vídeo directo (mp4, webm, ogg) | `http://server/film.mp4` |
| `iframe` | Página embebida en iframe (reproductores de terceros) | `https://tv.com/player/123` |
| `m3u` | Lista M3U que se parsea automáticamente en múltiples canales | `https://list.com/channels.m3u` |

### Formato M3U

El parser soporta tanto listas M3U remotas (HTTP/HTTPS) como locales. Formato esperado:

```
#EXTM3U
#EXTINF:-1 tvg-name="Canal 1",Canal 1
http://server/canal1/stream.m3u8
#EXTINF:-1 tvg-name="Canal 2",Canal 2
http://server/canal2/stream.m3u8
```

### Acceso

- **Lista de canales:** `http://localhost:5000/live`
- **Reproductor SmartTV:** `http://localhost:5000/live/tv/<indice>` (donde `<indice>` es la posición del canal en la lista, empezando por 0)

### Funcionalidades del reproductor en vivo

- **Modal en PC:** al hacer clic en "Ver", se abre un reproductor modal superpuesto.
- **Modo SmartTV:** vista optimizada con pantalla completa y controles grandes para televisores.
- **Soporte HLS:** usa HLS.js como fallback cuando el navegador no soporta HLS nativo (todos excepto Safari).
- **Fallback automático:** si un stream falla, el player intenta la siguiente URL disponible sin intervención del usuario.
- **SmartTV con HLS.js:** el reproductor SmartTV ahora incluye HLS.js desde CDN, permitiendo reproducción HLS en navegadores sin soporte nativo.
- **Tecla Escape:** cierra el reproductor modal.

---

**Modo SmartTV**

FlaskCast incluye un reproductor optimizado para Smart TV que permite ver tanto vídeos del catálogo como streams en vivo.

### Reproductor de vídeos (SmartTV)

```
http://localhost:5000/tv/reproducir/<nombre_serie>/<temporada>/<archivo.mp4>
```

Características:
- Reproducción automática al cargar
- Pantalla completa por defecto
- Barra de información con título del vídeo
- Botón para volver a la lista de streams

### Reproductor de streams en vivo (SmartTV)

```
http://localhost:5000/live/tv/<indice>
```

- Soporta vídeo directo, HLS (con HLS.js) e iframes
- Fallback automático entre múltiples fuentes
- Diseñado para ser controlado con el mando del televisor

---

**Ajustes**

Desde el panel de ajustes (`/ajustes`) puedes configurar:

- **Marcado automático:** activa o desactiva el cambio automático de estado "Viendo"/"Visto" según el progreso de reproducción.
- **Habilitar API:** activa o desactiva los endpoints REST. Al activarla, los endpoints requieren sesión de usuario. Un botón informativo (`i`) muestra la documentación completa de la API en un modal.

---

## Configuración avanzada (config_gui.py)

FlaskCast incluye un panel de configuración gráfico (`config_gui.py`) que permite modificar en tiempo real ciertos parámetros del servidor sin necesidad de editar archivos manualmente.

### Opciones

- **Mostrar botón "Apagar Servidor":** activa/desactiva la visibilidad del botón que apaga solo el proceso de Flask.
- **Mostrar botón "Apagar Todo":** activa/desactiva la visibilidad del botón que apaga todo el sistema operativo.
- **Puerto:** cambia el puerto en el que escucha el servidor (requiere reiniciar la aplicación).

Los cambios en los botones de apagado se aplican inmediatamente sin necesidad de reiniciar el servidor.

```bash
python config_gui.py
```

> **Nota para Linux:** `config_gui.py` usa `tkinter`, que no siempre viene incluido por defecto en algunas distribuciones Linux. Si al ejecutarlo obtienes un error como `ModuleNotFoundError: No module named 'tkinter'`, instálalo con:
>
> ```bash
> sudo apt install python3-tk    # Debian / Ubuntu
> sudo dnf install python3-tkinter  # Fedora
> sudo pacman -S tk              # Arch Linux
> ```

> **Nota para Docker:** si ejecutas FlaskCast mediante `docker-compose`, el cambio de puerto desde `config_gui.py` no tendrá efecto. El puerto se define en el archivo `docker-compose.yml` mediante el mapeo `ports:`. Para cambiar el puerto en Docker, edita el archivo `docker-compose.yml` y modifica el lado izquierdo del mapeo (ej: `"8080:5000"` para usar el puerto 8080).

---

**API REST**

FlaskCast incluye una API REST protegida por sesión de usuario y un toggle en Ajustes. Todos los endpoints requieren el encabezado de cookie de sesión y que el usuario tenga la API habilitada.

### 📤 Agregar Video

```
POST /api/videos/add
Content-Type: multipart/form-data
```

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `serie` | string (obligatorio) | Nombre de la serie |
| `temporada` | string | Obligatorio si la serie tiene subcarpetas. No usar si no las tiene. |
| `archivo` | file (obligatorio) | Archivo de vídeo a subir |

```bash
curl -X POST http://localhost:5000/api/videos/add \
  -b "session=TU_SESSION" \
  -F "serie=Mi Serie" \
  -F "temporada=Temporada 1" \
  -F "archivo=@/ruta/al/video.mp4"
```

### 📋 Listar Estructura

```
GET /api/videos             → Todas las series y sus capítulos
GET /api/videos/Mi%20Serie  → Una serie específica
```

```bash
curl http://localhost:5000/api/videos -b "session=TU_SESSION"
```

### 🎬 Obtener Video

```
GET /api/video/<serie>/<ruta/al/archivo.mp4>
```

```bash
curl http://localhost:5000/api/video/Mi%20Serie/Temporada%201/cap1.mp4 \
  -b "session=TU_SESSION" -o cap1.mp4
```

### 🗑️ Eliminar Video (API)

```
POST /api/videos/rm
Content-Type: application/json
```

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `serie` | string (obligatorio) | Nombre de la serie |
| `filename` | string (obligatorio) | Ruta del archivo dentro de la serie |

```bash
curl -X POST http://localhost:5000/api/videos/rm \
  -b "session=TU_SESSION" \
  -H "Content-Type: application/json" \
  -d '{"serie": "Mi Serie", "filename": "Temporada 1/video.mp4"}'
```

### 🎥 Obtener Archivo de Vídeo (API)

Descarga directa de un archivo de vídeo específico.

```
GET /api/video/<serie>/<ruta/archivo.mp4>
```

```bash
curl http://localhost:5000/api/video/Mi%20Serie/Temporada%201/cap1.mp4 \
  -b "session=TU_SESSION" -o cap1.mp4
```

### 🔄 Convertir Vídeo (API)

Inicia la conversión de un vídeo incompatible (`.avi`, `.mkv`) a `.mp4` en segundo plano.

```
POST /api/convertir/<serie>/<ruta/archivo.avi>
```

**Respuesta:**
```json
{"status": "procesando"}
```

Si ya existe un archivo `.mp4` con el mismo nombre:
```json
{"status": "ya_existe_mp4"}
```

Si ya hay una conversión en curso:
```json
{"status": "ya_en_progreso"}
```

```bash
curl -X POST http://localhost:5000/api/convertir/Mi%20Serie/Temporada%201/cap1.avi \
  -b "session=TU_SESSION"
```

### 🗑️ Eliminar Archivo Directo (API)

Elimina un archivo específico sin necesidad de usar el endpoint de "videos/rm".

```
POST /api/eliminar/<serie>/<ruta/archivo.mp4>
```

```bash
curl -X POST http://localhost:5000/api/eliminar/Mi%20Serie/Temporada%201/cap1.mp4 \
  -b "session=TU_SESSION"
```

### 📊 Consultar Conversiones Activas (API)

Devuelve la lista de identificadores de vídeos que se están convirtiendo actualmente.

```
GET /api/estados
```

**Respuesta:**
```json
{"activos": ["Mi Serie/Temporada 1/cap1.avi", "Otra Serie/video.mkv"]}
```

```bash
curl http://localhost:5000/api/estados -b "session=TU_SESSION"
```

### 💾 Guardar Progreso de Reproducción (API)

Guarda la posición de reproducción de un vídeo para el usuario actual.

```
POST /api/progreso/guardar
Content-Type: application/json
```

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `serie` | string (obligatorio) | Nombre de la serie |
| `filename` | string (obligatorio) | Ruta del archivo (ej: `Temporada 1/cap1.mp4`) |
| `segundos` | number | Posición actual en segundos |
| `duracion` | number | Duración total del vídeo |
| `visto` | number | Estado forzado (0=Sin ver, 1=Viendo, 2=Visto) - opcional |

**Nota:** Si se envía el campo `visto`, se ignora el cálculo automático y se fuerza ese estado.

```bash
curl -X POST http://localhost:5000/api/progreso/guardar \
  -b "session=TU_SESSION" \
  -H "Content-Type: application/json" \
  -d '{"serie": "Mi Serie", "filename": "Temporada 1/cap1.mp4", "segundos": 1250, "duracion": 3600}'
```

### 📥 Obtener Progreso de Reproducción (API)

Obtiene la posición guardada y el estado de un vídeo para el usuario actual.

```
GET /api/progreso/obtener?serie=<serie>&filename=<archivo>
```

**Respuesta:**
```json
{"segundos": 1250, "visto": 1}
```

```bash
curl "http://localhost:5000/api/progreso/obtener?serie=Mi%20Serie&filename=Temporada%201/cap1.mp4" \
  -b "session=TU_SESSION"
```

### 🏓 Ping (API)

Verifica que el servidor está activo.

```
GET /api/ping
```

**Respuesta:**
```json
{"status": "servidor en linea"}
```

```bash
curl http://localhost:5000/api/ping
```

### ⏻ Apagar Servidor (API)

Detiene únicamente el proceso de FlaskCast. Solo funciona si está habilitado en `config_gui.py`.

```
GET /api/off
```

**Respuesta:**
```json
{"status": "Apagando servidor..."}
```

```bash
curl http://localhost:5000/api/off
```

### ⏻ Apagar Sistema (API)

Apaga todo el sistema operativo. Solo funciona si está habilitado en `config_gui.py`.

```
GET /api/off/all
```

**Respuesta:**
```json
{"status": "Apagando sistema..."}
```

```bash
curl http://localhost:5000/api/off/all
```

---

**Endpoints de Servicio Multimedia**

Estos endpoints sirven el contenido audiovisual directamente desde el navegador. No requieren autenticación.

| Endpoint | Descripción |
|----------|-------------|
| `GET /video/<serie>/<archivo>` | Sirve un archivo de vídeo para reproducción en el navegador |
| `GET /thumbnail/<serie>/<archivo>` | Sirve o genera automáticamente una miniatura del vídeo (fotograma a los 3 segundos) |
| `GET /portada/<serie>` | Sirve la imagen de portada `_img.png` de una serie |
| `GET /serie/<nombre_serie>` | Página web con el catálogo de capítulos de una serie |
| `GET /tv/reproducir/<serie>/<archivo>` | Reproductor optimizado para SmartTV |

### Ejemplos

```
http://localhost:5000/video/Mi%20Serie/Temporada%201/cap1.mp4
http://localhost:5000/thumbnail/Mi%20Serie/Temporada%201/cap1.mp4
http://localhost:5000/portada/Mi%20Serie
http://localhost:5000/serie/Mi%20Serie
http://localhost:5000/tv/reproducir/Mi%20Serie/Temporada%201/cap1.mp4
```

### Generación automática de miniaturas

Cuando se solicita una miniatura que no existe, FlaskCast genera automáticamente un fotograma extraído a los 3 segundos del vídeo usando FFmpeg. Las miniaturas se almacenan en:

```
data/media/<Serie>/.thumbnails/<nombre_archivo>.jpg
```

---

**Reproductor y Auto-reproducción**

El reproductor de FlaskCast incluye funciones avanzadas de seguimiento y auto-reproducción.

### Seguimiento automático

- Cada 10 segundos, el reproductor envía la posición actual al servidor.
- Si el usuario tiene activada la opción "Marcado automático" en Ajustes:
  - **>10% reproducido** → Estado cambia a "Viendo" (badge azul)
  - **>85% reproducido** → Estado cambia a "Visto" (badge verde)
- Si se desactiva el marcado automático, los estados solo cambian al hacer clic manualmente sobre la etiqueta del capítulo.

### Auto-reproducción del siguiente capítulo

Al finalizar un vídeo, el reproductor carga automáticamente el siguiente capítulo de la misma temporada (si existe). Esta función:

- Solo aplica a vídeos en formatos web (`.mp4`, `.webm`, `.ogg`)
- No avanza si es el último capítulo de la temporada
- Muestra un botón "Siguiente" al finalizar

### Formatos soportados en el reproductor

| Formato | Soporte nativo | Conversión necesaria |
|---------|---------------|---------------------|
| `.mp4` (H.264) | ✅ Sí | No |
| `.webm` | ✅ Sí | No |
| `.ogg` | ✅ Sí | No |
| `.avi` | ❌ No | Sí (a .mp4) |
| `.mkv` | ❌ No | Sí (a .mp4) |

---

**Resumen de Endpoints**

### Rutas web (requieren navegador)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Catálogo principal de series |
| GET | `/serie/<nombre>` | Detalle de una serie con sus capítulos |
| GET | `/tv/reproducir/<serie>/<archivo>` | Reproductor SmartTV |
| GET | `/live` | Lista de streams en vivo |
| GET | `/live/tv/<indice>` | Reproductor SmartTV para streams en vivo |
| GET | `/usuarios_panel` | Panel de gestión de usuarios |
| GET | `/ajustes` | Panel de configuración |

### API REST (requieren sesión + API habilitada)

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/videos/add` | Subir vídeo a una serie |
| POST | `/api/videos/rm` | Eliminar vídeo por nombre |
| GET | `/api/videos` | Listar todas las series |
| GET | `/api/videos/<serie>` | Obtener estructura de una serie |
| GET | `/api/video/<serie>/<archivo>` | Descargar/archivo de vídeo |
| POST | `/api/convertir/<serie>/<archivo>` | Convertir vídeo incompatible a MP4 |
| POST | `/api/eliminar/<serie>/<archivo>` | Eliminar archivo directo |
| GET | `/api/estados` | Consultar conversiones activas |
| POST | `/api/progreso/guardar` | Guardar posición de reproducción |
| GET | `/api/progreso/obtener` | Obtener posición guardada |
| GET | `/api/ping` | Verificar estado del servidor |
| GET | `/api/off` | Apagar servidor (si habilitado) |
| GET | `/api/off/all` | Apagar sistema (si habilitado) |

### Endpoints de contenido

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/video/<serie>/<archivo>` | Servir archivo de vídeo |
| GET | `/thumbnail/<serie>/<archivo>` | Servir/generar miniatura |
| GET | `/portada/<serie>` | Servir portada de serie |

---

**Comandos útiles**

- Ejecutar localmente: `python app.py`
- Entorno virtual (Windows): `venv\Scripts\activate`
- Docker: `docker-compose up --build`

---

**Contribuir y soporte**

Si quieres contribuir, abre un issue o crea un pull request. Para cambios mayores, escribe primero un issue describiendo la propuesta.

---

**Licencia**

Revisa el archivo `LICENSE` incluido en el repositorio.
