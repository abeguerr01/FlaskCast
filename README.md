# 📺 FlaskCast — Plataforma Multimedia Local

<table>
  <tr>
    <td><img src="static/logo.png" alt="FlaskCast Logo" width="500"></td>
    <td style="vertical-align: middle; padding-left: 20px;">
      <p>FlaskCast es un portal de streaming multimedia personal y local construido con Python y Flask. Permite organizar catálogos de series y películas por carpetas, generar miniaturas automáticamente, transcodificar formatos incompatibles en segundo plano con FFmpeg, guardar el progreso de reproducción por usuario y gestionar el contenido mediante una API REST.</p>
    </td>
  </tr>
</table>

---

> **⚠ Aviso Legal y Exención de Responsabilidad**
>
> FlaskCast es una herramienta de uso privado y local diseñada exclusivamente para organizar y reproducir contenido multimedia al que el usuario posee los derechos legales de uso. En ningún caso FlaskCast facilita, promueve ni permite la obtención o distribución de contenido protegido por derechos de autor sin la debida autorización.
>
> El usuario es el único responsable del contenido que alberga, organiza y reproduce mediante esta aplicación. El desarrollador de FlaskCast declina toda responsabilidad derivada del uso indebido de esta herramienta en relación con material sobre el que el usuario no tenga derechos legales.
>
> El uso de FlaskCast implica la aceptación de estas condiciones.

---

## Características principales

- **Catálogo por carpetas:** organiza series, temporadas y capítulos directamente desde el sistema de archivos.
- **Diferenciación Películas/Series:** detección automática por estructura de carpetas, con badge visual 🎬/📺 y filtro en catálogo. Soporte para override manual vía `_meta.json` o tabla `content_metadata`.
- **Continuar viendo:** sección destacada en el catálogo que muestra los capítulos en progreso ordenados por recencia, con barra de porcentaje.
- **Transcodificación asíncrona:** convierte `.avi`/`.mkv` a `.mp4` (H.264) en segundo plano usando FFmpeg (`static-ffmpeg`).
- **Miniaturas dinámicas:** extrae fotogramas como `.jpg` para previsualizaciones.
- **Seguimiento por usuario:** guarda la posición exacta (segundos), marca "En progreso" y "Visto" según umbrales configurables.
- **Listas personalizadas:** organiza contenido en Favoritos, Pendiente, Viendo y Visto con pestañas filtrables.
- **Paginación del catálogo:** 24 elementos por página con controles de navegación.
- **Tema claro/oscuro:** toggle entre tema oscuro (por defecto) y claro, guardado por usuario.
- **Transiciones SPA:** navegación entre páginas con fade animations y fetch AJAX.
- **API REST completa:** añade, elimina, lista, descarga vídeos y gestiona el progreso mediante endpoints protegidos por toggle.
- **Streaming en Vivo:** reproduce streams en directo (HLS, iframes, vídeos) con soporte para listas M3U, modo SmartTV y **fallback automático con múltiples fuentes**.
- **Modo SmartTV:** reproductor optimizado para televisores conectados a la red local.
- **Auto-reproducción:** el reproductor avanza automáticamente al siguiente capítulo de la temporada.
- **Interfaz responsive:** diseño adaptable con sidebar colapsable en móvil (hamburger menu), breakpoints a 900px, 768px y 480px.
- **Interfaz ligera:** HTML5, CSS y JavaScript Vanilla para reproducción y búsqueda en tiempo real.
- **Multi-idioma (i18n):** soporte español/inglés con cambio por usuario. Géneros y descripciones de OMDb se traducen automáticamente.
- **Integración OMDb:** obtención automática de portadas, descripciones, valoraciones y metadatos desde OMDb API. Clave guardada en `.env`.
- **Diseño hero:** vista detalle con banner de portada difuminada, metadata visual y botones de acción.
- **Panel de administración GUI:** gestión visual de contenido, streams, configuración y OMDb con interfaz en tkinter (5 pestañas, bilingual ES/EN).

---

## Tecnologías

- Backend: Python 3 + Flask
- Base de datos: SQLite3 (`flaskcast.db`)
- Procesamiento de vídeo: FFmpeg (gestión automática con `static-ffmpeg`)
- Concurrencia: `threading` para evitar colisiones en conversiones
- Rate Limiting: Flask-Limiter (protección contra abuso de API)
- Frontend: HTML5, CSS3 y JavaScript
- Template Engine: Jinja2 con herencia de plantillas (`base.html`)
- Servidores de producción: Waitress (Windows) / Gunicorn (Linux)
- Compresión: py7zr (exportar/importar contenido)
- Traducción: MyMemory API (descripciones) + diccionario local (géneros)

---

## Instalación rápida

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

4. Ejecuta la aplicación:

```bash
python app.py
```

Accede desde el navegador en `http://localhost:5000` o usando la IP de tu equipo en la red local.

### Notas sobre dependencias

- **`static-ffmpeg`** descargará y configurará los binarios de FFmpeg la primera vez que se ejecute la aplicación. Si prefieres, puedes instalar FFmpeg globalmente en tu sistema.
- **`py7zr`** se usa para las funciones de exportar/importar contenido multimedia en el panel de administración.
- **`Flask-Limiter`** proporciona rate limiting para proteger contra abuso de la API.
- **`waitress`** (Windows) y **`gunicorn`** (Linux) se usan como servidores WSGI de producción.

### Despliegue en producción

En Windows, FlaskCast usa **Waitress** (6 threads). En Linux/Unix, usa **Gunicorn** (4 workers). El puerto se configura en `data/config.json` o mediante el panel de administración.

### Docker

```bash
docker-compose up --build
```

> **Nota para Docker:** si ejecutas FlaskCast mediante `docker-compose`, el cambio de puerto desde `config_admin.py` no tendrá efecto. El puerto se define en el archivo `docker-compose.yml` mediante el mapeo `ports:`.

---

## Variables de entorno

FlaskCast utiliza un archivo `.env` en la raíz del proyecto para almacenar credenciales sensibles. Este archivo está incluido en `.gitignore` y **no se sube al repositorio**.

| Variable | Descripción |
|----------|-------------|
| `OMDB_API_KEY` | Clave de API de OMDb para obtención de metadatos y portadas. Se guarda automáticamente al validar desde el panel de administración o se puede configurar con `--omdb-key`. |

---

## Estructura del proyecto

```
.
├── app.py                   # Aplicación Flask (rutas, API, BD, FFmpeg)
├── config_admin.py          # Panel de administración (GUI tkinter + CLI)
├── translations.py          # Sistema i18n (ES/EN), traducción de metadatos
├── requirements.txt
├── .env                     # Variables de entorno (OMDB_API_KEY) — gitignored
├── Dockerfile
├── docker-compose.yml
├── data/
│   ├── config.json          # Configuración del servidor
│   ├── flaskcast.db         # Base de datos SQLite
│   ├── live_streams.json    # Configuración de streams en vivo
│   └── media/               # Contenido multimedia
├── static/
│   ├── css/
│   │   └── estilos.css      # Estilos globales (tema, responsive, skeletons, badges, hero)
│   ├── js/
│   │   └── reproductor.js   # Lógica del reproductor de vídeo
│   └── logo.png
└── templates/
    ├── base.html            # Plantilla base (sidebar, SPA transitions, layout)
    ├── index.html           # Catálogo principal con paginación, filtros y continuar viendo
    ├── serie.html           # Detalle de serie/película con hero banner y capítulos
    ├── listas.html          # Listas personales (Favoritos, Pendiente, Viendo, Visto)
    ├── player_tv.html       # Reproductor SmartTV (sin sidebar)
    ├── live.html            # Lista de streams en vivo
    ├── live_tv.html         # Reproductor SmartTV para streams (sin sidebar)
    ├── usuarios.html        # Panel de gestión de usuarios
    └── ajustes.html         # Panel de configuración (tema, idioma, marcado automático)
```

### Archivos de datos (no versionados)

| Archivo | Contenido |
|---------|-----------|
| `.env` | `OMDB_API_KEY` — clave de API de OMDb |
| `data/config.json` | Puerto, botones de apagado, API habilitada, idioma del admin |
| `data/flaskcast.db` | SQLite: usuarios, progreso, favoritos, listas, content_metadata |
| `data/live_streams.json` | Definición de canales en vivo |
| `data/media/` | Carpetas de series/películas, portadas, miniaturas |

---

## Base de datos

FlaskCast usa SQLite con modo WAL para concurrencia. Las tablas se crean automáticamente al iniciar la aplicación.

| Tabla | Descripción |
|-------|-------------|
| `usuarios` | Perfiles de usuario (nombre, emoji, tema, idioma, auto_marcar, mostrar_progreso) |
| `progreso` | Posición de reproducción por usuario y vídeo (segundos, visto, duración) |
| `favoritos` | Series/películas marcadas como favoritas por usuario |
| `listas` | Estado en lista por usuario y serie (0=Pendiente, 1=Viendo, 2=Visto) |
| `content_metadata` | Override manual de tipo de contenido (pelicula/serie) |

---

## Herencia de Plantillas

Todas las plantillas heredan de `base.html` usando Jinja2:

```html
{% extends 'base.html' %}

{% block title %}Mi Página{% endblock %}

{% block head %}
    <style>/* Estilos específicos */</style>
{% endblock %}

{% block content %}
    <!-- Contenido de la página -->
{% endblock %}
```

`base.html` incluye:
- Sidebar de navegación (se oculta en reproductores SmartTV)
- Bloques extensibles: `title`, `head`, `content`, `body_class`, `sidebar`

---

## Estructura del catálogo multimedia (requerida)

Coloca tu contenido en `data/media/` siguiendo este patrón:

```
data/
└── media/
    ├── Nombre de la Serie A/
    │   ├── _img.png                 <-- Portada (obligatoria para mostrar imagen)
    │   ├── _meta.json               <-- Metadatos (opcional, override manual)
    │   ├── Temporada 1/
    │   │   ├── Capitulo_01.mp4
    │   │   └── Capitulo_02.avi
    │   └── Temporada 2/
    │       ├── Capitulo_01.mkv
    │       └── Capitulo_02.mp4
    ├── Nombre de la Serie B (Sin Temporadas)/
    │   ├── _img.png
    │   ├── Video_Suelto_01.mp4
    │   └── Video_Suelto_02.mp4
    └── Mi Pelicula/
        ├── _img.png
        └── pelicula.mp4
```

- El archivo de portada debe llamarse exactamente `_img.png`. Si no existe, la interfaz mostrará un icono genérico (🎬 o 📺 según el tipo).
- Si no usas subcarpetas de temporada, los vídeos en la raíz aparecerán bajo "Contenido Disponible".

### Archivo `_meta.json`

El archivo `_meta.json` permite definir metadatos y forzar el tipo de contenido. Formato completo:

```json
{
  "tipo": "pelicula",
  "titulo": "Mi Película",
  "descripcion": "Una descripción de la película.",
  "anio": "2024",
  "genero": ["Acción", "Aventura"],
  "director": "Nombre del Director",
  "valoracion": "8.5",
  "duracion_min": 120,
  "temporadas": 1
}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `tipo` | string | `"pelicula"` o `"serie"` — fuerza el tipo detectado |
| `titulo` | string | Título display del contenido |
| `descripcion` | string | Descripción (se traduce automáticamente al español si el usuario tiene idioma ES) |
| `anio` | string | Año de estreno |
| `genero` | array | Lista de géneros en inglés (se traducen automáticamente) |
| `director` | string | Nombre del director |
| `valoracion` | string | Puntuación (ej: `"8.5"`) |
| `duracion_min` | integer | Duración en minutos (películas) |
| `temporadas` | integer | Número de temporadas (series) |

Los campos `titulo`, `descripcion`, `anio`, `genero`, `director`, `valoracion`, `duracion_min` y `temporadas` se rellenan automáticamente al aplicar metadatos de OMDb.

### Diferenciación Películas / Series

FlaskCast detecta automáticamente si una carpeta es una película o una serie mediante un sistema de 3 niveles:

| Prioridad | Fuente | Descripción |
|-----------|--------|-------------|
| 1 | Tabla `content_metadata` (BD) | Override manual guardado en la base de datos |
| 2 | Archivo `_meta.json` | Campo `tipo` en el archivo de metadatos |
| 3 | Estructura de carpetas | Subcarpetas = serie, solo vídeos = película |

**Diferencias en la UI:**

- **Catálogo:** badge 🎬 (dorado) o 📺 (azul) en cada card, con filtro "Todo / Películas / Series"
- **Vista detalle:** las películas muestran "🎬 Película" como título de sección y ocultan el acordeón de temporadas; las series muestran "Temporadas Disponibles" con acordeón expandible
- **Hero banner:** vista detalle con banner de portada difuminada, metadata visual (año, género, director, valoración, duración) y botones de acción

---

## Traducción de metadatos (i18n)

FlaskCast traduce automáticamente los metadatos de OMDb según el idioma del usuario:

- **Géneros:** se traducen localmente mediante un diccionario de 26 géneros (inglés → español) en `translations.py`.
- **Descripciones:** se traducen en tiempo real mediante la API gratuita de [MyMemory](https://mymemory.translated.net/) sin necesidad de clave de API.
- **Fallback:** si la traducción falla, se muestra el texto original en inglés.

---

## Gestión de formatos y transcodificación

- Formatos web nativos (`.mp4`, `.webm`, `.ogg`) se reproducen directamente.
- Formatos no nativos (`.avi`, `.mkv`) aparecen como "Pendiente" y pueden convertirse a `.mp4` mediante un botón en la interfaz.
- La conversión se realiza de forma asíncrona; la app usa `threading` y bloqueos para evitar conflictos en conversiones simultáneas.
- Conversión: FFmpeg con códec libx264 (vídeo) + AAC (audio), CRF 23.

---

## Usuarios y seguimiento de progreso

- Puedes crear perfiles de usuario con nombre y emoji desde el panel de usuarios.
- El reproductor envía actualizaciones periódicas al servidor guardando la marca de tiempo actual en la base de datos.
- **Umbrales de marcado automático:**
  - >10% reproducido → estado "Viendo" (azul).
  - >85% reproducido → estado "Visto" (verde).
- También puedes marcar manualmente un capítulo como "Visto" desde la UI.
- Cada usuario tiene sus propias preferencias: tema, idioma, marcado automático, mostrar progreso.

---

## Continuar viendo

El catálogo principal incluye una sección **"▶ Continuar viendo"** que muestra hasta 12 capítulos en progreso (estado `visto = 1`), ordenados por los más recientemente vistos. Cada card muestra una barra de progreso porcentual. Al hacer clic, el reproductor retoma la posición guardada.

---

## Listas personales

FlaskCast incluye una página de listas (`/listas`) donde los usuarios pueden organizar su contenido:

### Pestañas de filtrado

| Pestaña | Color | Descripción |
|---------|-------|-------------|
| ⭐ Favoritos | Dorado (#f5a623) | Series/películas marcadas como favoritas |
| 📋 Pendiente | Gris (#888) | Contenido pendiente de ver |
| 👁️ Viendo | Azul (#0d6efd) | Contenido en progreso |
| ✅ Visto | Verde (#1fcc72) | Contenido completado |

- Al abrir la página, la pestaña "Favoritos" se muestra seleccionada por defecto.
- Clic en una pestaña muestra solo esa sección; clic de nuevo la oculta (toggle).
- Cada card muestra un badge de tipo (🎬/📺) según el contenido.
- La favoritos se gestionan desde el botón ⭐ en la vista de detalle de cada serie.
- Pendiente/Viendo/Visto se gestionan desde el botón "＋ Añadir" en la vista de detalle.

---

## Paginación del catálogo

El catálogo principal muestra 24 elementos por página con controles de navegación:

- Botones de página con ellipsis (`...`) para saltos largos.
- Botones "Anterior" / "Siguiente" para navegación secuencial.
- Indicador de rango: "Mostrando X–Y de Z elementos".
- La paginación es server-side; cada página carga su propio subset de datos.

---

## Diseño responsive

FlaskCast se adapta automáticamente al tamaño de pantalla:

| Breakpoint | Comportamiento |
|------------|----------------|
| > 900px | Layout completo con sidebar fijo |
| ≤ 900px | Sidebar colapsable con hamburger menu |
| ≤ 768px | Grid de cards ajustado, header compacto |
| ≤ 480px | Grid de 2 columnas, controles apilados |

- **Hamburger menu:** botón de 3 líneas que abre/cierra el sidebar en móvil.
- **Overlay:** al abrir el sidebar, se muestra un overlay oscuro que lo cierra al hacer clic.
- **Transiciones SPA:** la navegación entre páginas usa fade animations con skeleton loading durante la carga.

---

## Transiciones SPA (Single Page Application)

FlaskCast simula navegación SPA usando AJAX:

1. Al hacer clic en un enlace interno, el contenido actual hace fade-out.
2. Se muestra un skeleton placeholder mientras se carga la nueva página.
3. El nuevo contenido se inyecta con fade-in animation.
4. La URL se actualiza con `history.pushState()`.
5. El sidebar se actualiza para reflejar la sección activa.

Excluidos de las transiciones: enlaces externos, `#` anchors, modales, reproductores, y elementos con `data-no-transition`.

---

## Streaming en Vivo (Contenido en Directo)

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

Los streams también se pueden gestionar visualmente desde la pestaña **"Streamings"** del panel de administración (`config_admin.py`).

### Múltiples URLs y fallback automático

Cada stream puede definir múltiples fuentes de reproducción mediante el campo `urls` (array). Cuando una fuente falla, el reproductor **salta automáticamente a la siguiente** sin intervención del usuario.

- Si solo se usa `"url"` (string), se comporta como una única fuente.
- Si se usa `"urls"` (array), el player intentará cada fuente en orden hasta encontrar una que funcione.
- El campo `"url"` se mantiene para retrocompatibilidad; si se proporciona `"urls"`, este tiene prioridad.

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
- **SmartTV con HLS.js:** el reproductor SmartTV incluye HLS.js desde CDN, permitiendo reproducción HLS en navegadores sin soporte nativo.
- **Tecla Escape:** cierra el reproductor modal.

---

## Modo SmartTV

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

## Ajustes

Desde el panel de ajustes (`/ajustes`) puedes configurar:

- **Idioma:** alterna entre español e inglés. La preferencia se guarda por usuario en la BD y se aplica a toda la interfaz y a los metadatos de OMDb.
- **Tema:** alterna entre tema oscuro (por defecto) y tema claro. La preferencia se guarda por usuario en la BD.
- **Marcado automático:** activa o desactiva el cambio automático de estado "Viendo"/"Visto" según el progreso de reproducción.
- **Mostrar progreso:** activa o desactiva la barra de progreso en las cards de capítulos.
- **Habilitar API:** activa o desactiva los endpoints REST. Al activarla, los endpoints requieren sesión de usuario. Un botón informativo (`i`) muestra la documentación completa de la API en un modal. Esta opción se gestiona desde el panel de administración (`config_admin.py`).

---

## Multi-idioma (i18n)

FlaskCast soporta español e inglés en toda la interfaz:

- **Web:** ~160 cadenas traducidas en `translations.py` (sección `TRANSLATIONS`). Cambio por usuario desde ajustes.
- **Panel de administración:** ~140 cadenas traducidas (sección `ADMIN_TRANSLATIONS`). Cambio desde la pestaña "Language".
- **Géneros:** 26 géneros traducidos localmente (inglés → español) en `GENRE_TRANSLATIONS`.
- **Descripciones:** traducción automática en tiempo real vía API de MyMemory (gratuita, sin clave).
- **Fallback:** si el idioma es inglés, los metadatos se muestran sin traducir; si falla la traducción, se muestra el texto original.

---

## Rate Limiting (Protección contra abuso)

FlaskCast incluye rate limiting mediante `Flask-Limiter` para proteger la API y las rutas web contra floods de requests y abuso.

### Límites configurados

| Endpoint | Límite | Razón |
|----------|--------|-------|
| General (todas las rutas) | 200/min | Protección base |
| `POST /api/videos/add` | 10/min | Evitar uploads masivos |
| `POST /api/videos/rm` | 10/min | Evitar eliminaciones masivas |
| `POST /api/convertir/...` | 5/min | Las conversiones son pesadas |
| `POST /api/eliminar/...` | 10/min | Evitar eliminaciones masivas |
| `POST /api/progreso/guardar` | 60/min | Se llama frecuentemente durante reproducción |
| `POST /api/favoritos/toggle` | 30/min | Operación moderada |
| `POST /api/lista/guardar` | 30/min | Operación moderada |
| `POST /usuarios/crear` | 5/min | Evitar creación masiva de usuarios |
| `POST /usuarios/editar` | 10/min | Moderado |
| `POST /usuarios/eliminar` | 5/min | Operación destructiva |
| `GET /api/off` | 2/min | Crítico |
| `GET /api/off/all` | 1/min | Crítico |

### Respuesta cuando se supera el límite

```json
{
  "error": "Too Many Requests",
  "message": "You have exceeded the rate limit. Please slow down.",
  "retry_after": 42
}
```

Código de estado HTTP: `429 Too Many Requests`

---

## Panel de administración (config_admin.py)

FlaskCast incluye un panel de administración (`config_admin.py`) con interfaz gráfica (GUI) en tkinter y modo línea de comandos (CLI). Tiene **5 pestañas** y soporte bilingüe (ES/EN).

### Modo gráfico (GUI)

Se abre la ventana de administración sin pasar ningún argumento:

```bash
python config_admin.py
```

#### Pestaña General

- **Mostrar botón "Apagar Servidor":** activa/desactiva la visibilidad del botón que apaga solo el proceso de Flask.
- **Mostrar botón "Apagar Todo":** activa/desactiva la visibilidad del botón que apaga todo el sistema operativo.
- **Habilitar API REST:** activa/desactiva los endpoints de la API REST.
- **Puerto:** cambia el puerto en el que escucha el servidor (requiere reiniciar la aplicación).
- **Exportar media (.fkmedia):** comprime toda la carpeta `data/media/` en un archivo `.fkmedia` (formato 7z internamente).
- **Importar media (.fkmedia):** selecciona un archivo `.fkmedia` previamente exportado y lo extrae en `data/media/`.
- **Guardar y Cerrar:** aplica los cambios y cierra la ventana.

#### Pestaña OMDb

- Campo de entrada para la **clave de API de OMDb** con validación en tiempo real.
- La clave se guarda automáticamente en el archivo `.env` al validar con éxito.
- **Árbol de biblioteca** que muestra todas las carpetas multimedia con columnas: nombre, tipo (película/serie), tiene metadatos, tiene portada.
- Botón **"Aplicar OMDb"** que busca y aplica metadatos automáticamente (título, descripción, año, género, director, valoración, duración/temporadas) y descarga la portada como `_img.png`.

#### Pestaña Biblioteca

- **Árbol jerárquico** con toda la estructura multimedia (Series → Temporadas → Vídeos, Películas → Vídeos).
- Muestra tamaños de archivo en MB.
- **Acciones disponibles:**
  - Añadir película o serie (diálogo único con campos de metadata: título, descripción, año, género, director, valoración, tipo, duración, temporadas).
  - Añadir temporada.
  - Añadir vídeo (copia desde máquina local).
  - Editar metadata (actualiza `_meta.json` y tabla `content_metadata` de la BD).
  - Renombrar (cascada en BD: content_metadata, favoritos, progreso, listas).
  - Eliminar (con confirmación, limpia miniaturas y progreso).
- **Menú contextual** (clic derecho) con opciones según el nivel del nodo seleccionado.

#### Pestaña Streamings

- **CRUD completo** de streams en vivo almacenados en `data/live_streams.json`.
- Árbol con columnas: título, URL principal, tipo.
- **Acciones:** añadir, editar, eliminar, mover arriba/abajo (reordenar), actualizar.
- Cada stream tiene: título, URL principal, URLs de backup (una por línea), tipo (hls/iframe/video).

#### Pestaña Language (Idioma)

- Botones de radio para Español (ES) y English (EN).
- Al cambiar el idioma, toda la interfaz se reconstruye en el idioma seleccionado.
- La preferencia se guarda en `data/config.json` (`admin_idioma`).

#### Nota para Linux

`config_admin.py` usa `tkinter`, que no siempre viene incluido por defecto en algunas distribuciones Linux. Si al ejecutarlo obtienes un error como `ModuleNotFoundError: No module named 'tkinter'`, instálalo con:

```bash
sudo apt install python3-tk    # Debian / Ubuntu
sudo dnf install python3-tkinter  # Fedora
sudo pacman -S tk              # Arch Linux
```

### Modo línea de comandos (CLI)

Útil para servidores sin interfaz gráfica (headless). Permite modificar la configuración y gestionar archivos multimedia directamente desde la terminal.

```bash
python config_admin.py [OPCIONES]
```

| Bandera | Descripción |
|---------|-------------|
| `--status` | Muestra la configuración actual del servidor (incluye estado de la clave OMDb) |
| `--toggle-server` | Activa/desactiva el botón "Apagar Servidor" |
| `--toggle-all` | Activa/desactiva el botón "Apagar Todo" |
| `--api` | Activa/desactiva la API REST |
| `--port PUERTO` | Cambia el puerto del servidor (1-65535) |
| `--omdb-key API_KEY` | Guarda una clave de API de OMDb en el archivo `.env` |
| `--export ARCHIVO` | Exporta `data/media/` a un archivo `.fkmedia` |
| `--import ARCHIVO` | Importa un archivo `.fkmedia` en `data/media/` |

Se pueden combinar varias banderas en una sola ejecución:

```bash
python config_admin.py --api --toggle-all --port 8080
```

Ejemplos prácticos:

```bash
# Ver configuración actual
python config_admin.py --status

# Activar la API REST
python config_admin.py --api

# Cambiar puerto a 8080
python config_admin.py --port 8080

# Guardar clave de OMDb
python config_admin.py --omdb-key tu_clave_aqui

# Exportar todo el contenido multimedia
python config_admin.py --export backup.fkmedia

# Importar contenido desde un backup
python config_admin.py --import backup.fkmedia
```

---

## API REST

FlaskCast incluye una API REST protegida por sesión de usuario y activada desde el panel de administración. Todos los endpoints requieren el encabezado de cookie de sesión y que el usuario tenga la API habilitada. **Todos los endpoints están protegidos con rate limiting.**

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
| `visto` | number | Estado forzado (0=Sin ver, 1=Viendo, 2=Visto) — opcional |

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

### ⭐ Toggle Favoritos (API)

Añade o elimina una serie/película de la lista de favoritos.

```
POST /api/favoritos/toggle
Content-Type: application/json
```

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `serie` | string (obligatorio) | Nombre de la serie/película |

**Respuesta:**
```json
{"favorito": true}
```

### 📋 Guardar Estado de Lista (API)

Guarda el estado de una serie en la lista del usuario.

```
POST /api/lista/guardar
Content-Type: application/json
```

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `serie` | string (obligatorio) | Nombre de la serie |
| `estado` | integer | 0=Pendiente, 1=Viendo, 2=Visto |

### 📥 Obtener Estado de Lista (API)

```
GET /api/lista/estado?serie=<serie>
```

### 📥 Obtener Todas las Listas (API)

```
GET /api/lista/obtener
```

### 🖥️ Abrir Panel de Administración (API)

Abre la ventana de `config_admin.py` (solo accesible desde localhost).

```
GET /api/abrir_config_admin
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

Detiene únicamente el proceso de FlaskCast. Solo funciona si está habilitado en `config_admin.py`.

```
GET /api/off
```

**Respuesta:**
```json
{"status": "Apagando servidor..."}
```

### ⏻ Apagar Sistema (API)

Apaga todo el sistema operativo. Solo funciona si está habilitado en `config_admin.py`.

```
GET /api/off/all
```

**Respuesta:**
```json
{"status": "Apagando sistema..."}
```

---

## Endpoints de Servicio Multimedia

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

## Reproductor y Auto-reproducción

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

## Resumen de Endpoints

### Rutas web (requieren navegador)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Catálogo principal con paginación, filtros y continuar viendo |
| GET | `/page/<n>` | Catálogo paginado |
| GET | `/serie/<nombre>` | Detalle de una serie/película con hero banner y capítulos |
| GET | `/listas` | Listas personales (Favoritos, Pendiente, Viendo, Visto) |
| GET | `/tv/reproducir/<serie>/<archivo>` | Reproductor SmartTV |
| GET | `/live` | Lista de streams en vivo |
| GET | `/live/tv/<indice>` | Reproductor SmartTV para streams en vivo |
| GET | `/usuarios_panel` | Panel de gestión de usuarios |
| GET | `/ajustes` | Panel de configuración (tema, idioma, marcado automático) |
| GET/POST | `/ajustes` | Guardar ajustes del usuario |

### API REST (requieren sesión + API habilitada)

| Método | Ruta | Descripción | Rate Limit |
|--------|------|-------------|------------|
| POST | `/api/videos/add` | Subir vídeo a una serie | 10/min |
| POST | `/api/videos/rm` | Eliminar vídeo por nombre | 10/min |
| GET | `/api/videos` | Listar todas las series | 200/min |
| GET | `/api/videos/<serie>` | Obtener estructura de una serie | 200/min |
| GET | `/api/video/<serie>/<archivo>` | Descargar/archivo de vídeo | 200/min |
| POST | `/api/convertir/<serie>/<archivo>` | Convertir vídeo incompatible a MP4 | 5/min |
| POST | `/api/eliminar/<serie>/<archivo>` | Eliminar archivo directo | 10/min |
| GET | `/api/estados` | Consultar conversiones activas | 200/min |
| POST | `/api/progreso/guardar` | Guardar posición de reproducción | 60/min |
| GET | `/api/progreso/obtener` | Obtener posición guardada | 200/min |
| POST | `/api/favoritos/toggle` | Añadir/quitar de favoritos | 30/min |
| GET | `/api/favoritos` | Obtener lista de favoritos | 200/min |
| GET | `/api/lista/estado` | Obtener estado de lista de una serie | 200/min |
| POST | `/api/lista/guardar` | Guardar estado en lista (Pendiente/Viendo/Visto) | 30/min |
| GET | `/api/lista/obtener` | Obtener todas las listas del usuario | 200/min |
| GET | `/api/abrir_config_admin` | Abrir panel de administración (solo localhost) | 200/min |
| GET | `/api/ping` | Verificar estado del servidor | 200/min |
| GET | `/api/off` | Apagar servidor (si habilitado) | 2/min |
| GET | `/api/off/all` | Apagar sistema (si habilitado) | 1/min |

### Endpoints de contenido

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/video/<serie>/<archivo>` | Servir archivo de vídeo |
| GET | `/thumbnail/<serie>/<archivo>` | Servir/generar miniatura |
| GET | `/portada/<serie>` | Servir portada de serie/película |

---

## Comandos útiles

- Ejecutar localmente: `python app.py`
- Entorno virtual (Windows): `venv\Scripts\activate`
- Docker: `docker-compose up --build`
- Ver config del admin: `python config_admin.py --status`
- Guardar clave OMDb: `python config_admin.py --omdb-key tu_clave`

---

## Contribuir y soporte

Si quieres contribuir, abre un issue o crea un pull request. Para cambios mayores, escribe primero un issue describiendo la propuesta.

---

## Licencia

Revisa el archivo `LICENSE` incluido en el repositorio.
