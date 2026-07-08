# 📺 FlaskCast — Plataforma Multimedia Local

FlaskCast es un portal de streaming multimedia personal y local construido con Python y Flask. Permite organizar catálogos de series por carpetas, generar miniaturas automáticamente, transcodificar formatos incompatibles en segundo plano con FFmpeg, guardar el progreso de reproducción por usuario y gestionar el contenido mediante una API REST.

---

**Características principales**

- **Catálogo por carpetas:** organiza series, temporadas y capítulos directamente desde el sistema de archivos.
- **Transcodificación asíncrona:** convierte `.avi`/`.mkv` a `.mp4` (H.264) en segundo plano usando FFmpeg (`static-ffmpeg`).
- **Miniaturas dinámicas:** extrae fotogramas como `.jpg` para previsualizaciones.
- **Seguimiento por usuario:** guarda la posición exacta (segundos), marca "En progreso" y "Visto" según umbrales configurables.
- **API REST:** añade, elimina, lista y descarga vídeos mediante endpoints protegidos por toggle.
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
git clone <repo> && cd PlataformaMultimediaOnline
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
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── data/
│   ├── flaskcast.db         # Base de datos SQLite (usuarios, progreso)
│   └── media/               # Contenido multimedia (series / portadas / capítulos)
├── static/
│   ├── css/
│   │   └── estilos.css
│   └── js/
│       └── reproductor.js
└── templates/
    ├── index.html
    ├── serie.html
    ├── player_tv.html
    ├── usuarios.html
    └── ajustes.html
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

**Ajustes**

Desde el panel de ajustes (`/ajustes`) puedes configurar:

- **Marcado automático:** activa o desactiva el cambio automático de estado "Viendo"/"Visto" según el progreso de reproducción.
- **Habilitar API:** activa o desactiva los endpoints REST. Al activarla, los endpoints requieren sesión de usuario. Un botón informativo (`i`) muestra la documentación completa de la API en un modal.

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

### 🗑️ Eliminar Video

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
