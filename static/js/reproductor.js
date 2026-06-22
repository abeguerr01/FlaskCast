const serieContainer = document.getElementById('serieContainer');
const NOMBRE_SERIE = serieContainer ? serieContainer.getAttribute('data-serie') : '';

function playVideo(rutaRelativa) {
    const container = document.getElementById('playerContainer');
    const player = document.getElementById('mainPlayer');
    const title = document.getElementById('currentTitle');

    player.src = '/video/' + encodeURIComponent(NOMBRE_SERIE) + '/' + encodeURIComponent(rutaRelativa);
    title.innerText = rutaRelativa.substring(rutaRelativa.lastIndexOf('/') + 1);
    
    container.style.display = 'block';
    container.scrollIntoView({ behavior: 'smooth' });
    player.play();
}

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
                    // El vídeo ha terminado de convertirse en segundo plano. Mutamos la tarjeta en vivo.
                    card.classList.remove('converting', 'incompatible');
                    
                    // Eliminamos los overlays y badges de incompatibilidad
                    const badge = card.querySelector('.badge');
                    if (badge) badge.remove();
                    const actionsOverlay = card.querySelector('.actions-overlay');
                    if (actionsOverlay) actionsOverlay.remove();
                    const loaderTxt = card.querySelector('.loader-txt');
                    if (loaderTxt) loaderTxt.remove();
                    
                    // Transmutamos el icono a Play
                    const lockOverlay = card.querySelector('.lock-overlay');
                    if (lockOverlay) {
                        lockOverlay.className = 'play-overlay';
                        lockOverlay.innerText = '▶';
                    }
                    
                    // Calculamos la nueva ruta .mp4
                    const posPunto = rutaRelativa.lastIndexOf('.');
                    const rutaMp4 = rutaRelativa.substring(0, posPunto) + '.mp4';
                    
                    card.removeAttribute('data-filename');
                    
                    // Extraemos los elementos visuales base
                    const thumb = card.querySelector('.thumb');
                    const title = card.querySelector('.card-title');
                    
                    // Encapsulamos la zona superior para el click de PC/Móvil
                    const clickArea = document.createElement('div');
                    clickArea.className = 'card-click-area';
                    clickArea.onclick = function() {
                        playVideo(rutaMp4);
                    };
                    
                    card.insertBefore(clickArea, thumb);
                    clickArea.appendChild(thumb);
                    clickArea.appendChild(title);
                    
                    // Inyectamos el botón para SmartTV
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