const serieContainer = document.getElementById('serieContainer');
const NOMBRE_SERIE = serieContainer ? serieContainer.getAttribute('data-serie') : '';
const USUARIO_ACTIVO = serieContainer ? (serieContainer.getAttribute('data-user-active') === 'true') : false;
const MOSTRAR_PROGRESO = serieContainer ? (serieContainer.getAttribute('data-mostrar-progreso') === '1') : true;

let archivoActualRelativo = '';
let ultimoTiempoReportado = 0;

// --- VELOCIDAD DE REPRODUCCIÓN ---
function cambiarVelocidad(valor) {
    var player = document.getElementById('mainPlayer');
    if (player) {
        player.playbackRate = parseFloat(valor);
    }
    localStorage.setItem('flaskcast_speed', valor);
}

function cargarVelocidadGuardada() {
    var guardada = localStorage.getItem('flaskcast_speed');
    if (guardada) {
        var select = document.getElementById('speedSelector');
        if (select) {
            select.value = guardada;
        }
    }
    return guardada ? parseFloat(guardada) : 1;
}

function playVideo(rutaRelativa, segundoInicio, element) {
    const container = document.getElementById('playerContainer');
    const player = document.getElementById('mainPlayer');
    const title = document.getElementById('currentTitle');

    archivoActualRelativo = rutaRelativa;
    ultimoTiempoReportado = 0;

    player.src = '/video/' + encodeURIComponent(NOMBRE_SERIE) + '/' + encodeURIComponent(rutaRelativa);
    title.innerText = rutaRelativa.substring(rutaRelativa.lastIndexOf('/') + 1);
    
    container.style.display = 'block';
    container.scrollIntoView({ behavior: 'smooth' });

    var velocidadGuardada = cargarVelocidadGuardada();
    player.playbackRate = velocidadGuardada;
    
    if (segundoInicio && parseFloat(segundoInicio) > 5) {
        player.addEventListener('loadedmetadata', function onMetadata() {
            player.currentTime = parseFloat(segundoInicio);
            player.removeEventListener('loadedmetadata', onMetadata);
        });
    }

    // Si el marcado automático está activado y el vídeo está a 0 (No visto), lo pasamos provisionalmente a "Viendo" en la UI
    const autoMarcar = (serieContainer && serieContainer.getAttribute('data-auto-marcar') === 'true');
    if (USUARIO_ACTIVO && autoMarcar) {
        const badge = document.querySelector(`.visto-badge[data-filename="${rutaRelativa}"]`);
        if (badge && badge.getAttribute('data-estado') === '0') {
            actualizarBadgeUI(rutaRelativa, 1);
        }
    }

    player.play();
}

// --- FUNCIÓN REACTIVA PARA ACTUALIZAR EL BADGE Y LA TARJETA EN CALIENTE ---
function actualizarBadgeUI(filename, estado) {
    const badge = document.querySelector(`.visto-badge[data-filename="${filename}"]`);
    if (!badge) return;

    let texto = '';
    let clasesBadge = ['badge-novisto', 'badge-viendo', 'badge-visto'];
    let clasesCard = ['capitulo-novisto', 'capitulo-viendo', 'capitulo-visto'];
    
    let añadirClaseBadge = '';
    let añadirClaseCard = '';

    if (estado === 0) {
        texto = '👁️ No visto';
        añadirClaseBadge = 'badge-novisto';
        añadirClaseCard = 'capitulo-novisto';
    } else if (estado === 1) {
        texto = '⏳ Viendo';
        añadirClaseBadge = 'badge-viendo';
        añadirClaseCard = 'capitulo-viendo';
    } else if (estado === 2) {
        texto = '✔️ Visto';
        añadirClaseBadge = 'badge-visto';
        añadirClaseCard = 'capitulo-visto';
    }

    badge.setAttribute('data-estado', estado);
    badge.innerText = texto;
    clasesBadge.forEach(c => badge.classList.remove(c));
    badge.classList.add(añadirClaseBadge);

    const card = badge.closest('.video-card');
    if (card) {
        clasesCard.forEach(c => card.classList.remove(c));
        card.classList.add(añadirClaseCard);

        // Actualizar barra de progreso
        const barra = card.querySelector('.episode-progress-bar');
        if (barra && MOSTRAR_PROGRESO) {
            if (estado === 0) {
                barra.style.width = '0%';
            } else {
                var porcentajeOriginal = parseInt(card.getAttribute('data-porcentaje')) || 0;
                barra.style.width = porcentajeOriginal + '%';
            }
        }
    }
}

// --- CLIC INTERACTIVO EN EL BADGE (CAMBIO CÍCLICO MANUAL) ---
function toggleBadgeEstado(event, element) {
    event.stopPropagation(); // Evita que se abra o reproduzca el vídeo al tocar la etiqueta
    if (!USUARIO_ACTIVO) return;

    let estadoActual = parseInt(element.getAttribute('data-estado')) || 0;
    let nuevoEstado = (estadoActual + 1) % 3; // Ciclo rotativo: 0 -> 1 -> 2 -> 0
    const filename = element.getAttribute('data-filename');

    // Cambiamos el estado en el DOM inmediatamente
    actualizarBadgeUI(filename, nuevoEstado);

    // Persistimos el estado exacto en SQLite indicando la propiedad "visto"
    fetch('/api/progreso/guardar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            serie: NOMBRE_SERIE,
            filename: filename,
            segundos: nuevoEstado === 2 ? 0 : 0, 
            visto: nuevoEstado
        })
    });
}

// --- MONITOREO AUTOMÁTICO DE PROGRESO DE REPRODUCCIÓN ---
const mainPlayer = document.getElementById('mainPlayer');
if (mainPlayer) {
    mainPlayer.addEventListener('timeupdate', () => {
        if (!USUARIO_ACTIVO || !archivoActualRelativo) return;

        const tiempoActual = Math.floor(mainPlayer.currentTime);
        const duracion = mainPlayer.duration;
        if (!duracion) return;

        // Guardar cada 5 segundos de reproducción real
        if (tiempoActual % 5 === 0 && tiempoActual !== ultimoTiempoReportado) {
            ultimoTiempoReportado = tiempoActual;

            fetch('/api/progreso/guardar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    serie: NOMBRE_SERIE,
                    filename: archivoActualRelativo,
                    segundos: mainPlayer.currentTime,
                    duracion: duracion
                })
            })
            .then(res => res.json())
            .then(data => {
                // Si el servidor calculó un cambio de estado automático, refrescar UI
                if (data.nuevo_visto !== undefined) {
                    actualizarBadgeUI(archivoActualRelativo, data.nuevo_visto);
                }
            });
        }
    });

    mainPlayer.addEventListener('ended', () => {
        if (!USUARIO_ACTIVO || !archivoActualRelativo) return;

        fetch('/api/progreso/guardar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                serie: NOMBRE_SERIE,
                filename: archivoActualRelativo,
                segundos: mainPlayer.duration || 0,
                duracion: mainPlayer.duration || 0
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.nuevo_visto !== undefined) {
                actualizarBadgeUI(archivoActualRelativo, data.nuevo_visto);
            }
        });
    });
}

// --- LÓGICA DE SEGUIMIENTO FFMPEG ---
function convertirVideo(rutaRelativa, button) {
    const card = button.closest('.video-card');
    card.classList.add('converting');

    fetch('/api/convertir/' + encodeURIComponent(NOMBRE_SERIE) + '/' + encodeURIComponent(rutaRelativa), { method: 'POST' })
        .then(res => res.json())
        .catch(err => console.error("Error al iniciar conversión:", err));
}

function eliminarVideo(rutaRelativa, button) {
    const nombreArchivo = rutaRelativa.substring(rutaRelativa.lastIndexOf('/') + 1);
    if (!confirm(`¿Estás seguro de que quieres eliminar físicamente el archivo:\n${nombreArchivo}?`)) return;

    const card = button.closest('.video-card');

    fetch('/api/eliminar/' + encodeURIComponent(NOMBRE_SERIE) + '/' + encodeURIComponent(rutaRelativa), { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'eliminado') card.remove();
        })
        .catch(err => console.error("Error al eliminar archivo:", err));
}

function verificarEstados() {
    if (!NOMBRE_SERIE) return;

    fetch('/api/estados')
        .then(res => res.json())
        .then(data => {
            const activos = data.activos;
            
            document.querySelectorAll('.video-card.incompatible').forEach(card => {
                const rutaRelativa = card.getAttribute('data-filename');
                const identificadorUnico = NOMBRE_SERIE + '/' + rutaRelativa;
                
                if (activos.includes(identificadorUnico)) {
                    card.classList.add('converting');
                } else if (card.classList.contains('converting')) {
                    card.classList.remove('converting', 'incompatible');
                    
                    const badge = card.querySelector('.badge');
                    if (badge) badge.remove();
                    const actionsOverlay = card.querySelector('.actions-overlay');
                    if (actionsOverlay) actionsOverlay.remove();
                    const loaderTxt = card.querySelector('.loader-txt');
                    if (loaderTxt) loaderTxt.remove();
                    
                    const lockOverlay = card.querySelector('.lock-overlay');
                    if (lockOverlay) {
                        lockOverlay.className = 'play-overlay';
                        lockOverlay.innerText = '▶';
                    }
                    
                    const posPunto = rutaRelativa.lastIndexOf('.');
                    const rutaMp4 = rutaRelativa.substring(0, posPunto) + '.mp4';
                    
                    card.removeAttribute('data-filename');
                    
                    const thumb = card.querySelector('.thumb');
                    const title = card.querySelector('.card-title');
                    
                    const clickArea = document.createElement('div');
                    clickArea.className = 'card-click-area';
                    clickArea.onclick = function() {
                        playVideo(rutaMp4, 0, clickArea);
                    };
                    
                    card.insertBefore(clickArea, thumb);
                    clickArea.appendChild(thumb);
                    clickArea.appendChild(title);
                    
                    const tvLink = document.createElement('a');
                    tvLink.className = 'btn-tv-fallback';
                    tvLink.innerText = '📺 Modo SmartTV';
                    tvLink.href = '/tv/reproducir/' + encodeURIComponent(NOMBRE_SERIE) + '/' + encodeURIComponent(rutaMp4);
                    card.appendChild(tvLink);
                }
            });
        });
}

setInterval(verificarEstados, 4000);

// --- ATAJOS DE TECLADO ---
(function() {
    var indicador = null;

    function mostrarIndicador(texto) {
        if (!indicador) {
            indicador = document.createElement('div');
            indicador.className = 'keyboard-indicator';
            document.body.appendChild(indicador);
        }
        indicador.textContent = texto;
        indicador.classList.add('show');
        clearTimeout(indicador._timer);
        indicador._timer = setTimeout(function() {
            indicador.classList.remove('show');
        }, 800);
    }

    document.addEventListener('keydown', function(e) {
        var player = document.getElementById('mainPlayer');
        var container = document.getElementById('playerContainer');
        if (!player || !container || container.style.display === 'none') return;

        var tag = e.target.tagName.toLowerCase();
        if (tag === 'input' || tag === 'textarea' || tag === 'select') return;

        switch(e.key) {
            case ' ':
                e.preventDefault();
                if (player.paused) {
                    player.play();
                    mostrarIndicador('▶ Play');
                } else {
                    player.pause();
                    mostrarIndicador('⏸ Pausa');
                }
                break;
            case 'ArrowLeft':
                e.preventDefault();
                player.currentTime = Math.max(0, player.currentTime - 10);
                mostrarIndicador('⏪ -10s');
                break;
            case 'ArrowRight':
                e.preventDefault();
                player.currentTime = Math.min(player.duration || 0, player.currentTime + 10);
                mostrarIndicador('⏩ +10s');
                break;
            case 'f':
            case 'F':
                e.preventDefault();
                if (document.fullscreenElement) {
                    document.exitFullscreen();
                    mostrarIndicador('Salida pantalla completa');
                } else {
                    container.requestFullscreen();
                    mostrarIndicador('📺 Pantalla completa');
                }
                break;
            case 'm':
            case 'M':
                e.preventDefault();
                player.muted = !player.muted;
                mostrarIndicador(player.muted ? '🔇 Mutear' : '🔊 Sonido');
                break;
        }
    });
})();