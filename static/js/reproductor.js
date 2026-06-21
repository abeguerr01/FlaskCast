const serieContainer = document.getElementById('serieContainer');
const NOMBRE_SERIE = serieContainer ? serieContainer.getAttribute('data-serie') : '';

function playVideo(rutaRelativa) {
    const container = document.getElementById('playerContainer');
    const player = document.getElementById('mainPlayer');
    const title = document.getElementById('currentTitle');

    // Construimos la URL codificando limpiamente los directorios internos
    player.src = '/video/' + encodeURIComponent(NOMBRE_SERIE) + '/' + encodeURIComponent(rutaRelativa);
    
    // Obtenemos solo el nombre final del archivo para el título limpio
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
                const rutaRelativa = card.getAttribute('data-filename'); // Ej: "Temporada 1/capitulo.avi"
                const identificadorUnico = NOMBRE_SERIE + '/' + rutaRelativa;
                
                if (activos.includes(identificadorUnico)) {
                    card.classList.add('converting');
                } else if (card.classList.contains('converting')) {
                    // MÁGIA AQUÍ: El hilo terminó. Modificamos el DOM en vivo sin recargar la página entera
                    card.classList.remove('converting', 'incompatible');
                    
                    // 1. Limpiamos las etiquetas y paneles de la versión incompatible
                    const badge = card.querySelector('.badge');
                    if (badge) badge.remove();
                    
                    const actionsOverlay = card.querySelector('.actions-overlay');
                    if (actionsOverlay) actionsOverlay.remove();
                    
                    const loaderTxt = card.querySelector('.loader-txt');
                    if (loaderTxt) loaderTxt.remove();
                    
                    // 2. Transmutamos visualmente el icono de bloqueo por el de Play clásico
                    const lockOverlay = card.querySelector('.lock-overlay');
                    if (lockOverlay) {
                        lockOverlay.className = 'play-overlay';
                        lockOverlay.innerText = '▶';
                    }
                    
                    // 3. Calculamos dinámicamente la string de la nueva ruta .mp4
                    const posPunto = rutaRelativa.lastIndexOf('.');
                    const rutaMp4 = rutaRelativa.substring(0, posPunto) + '.mp4';
                    
                    // 4. Convertimos la tarjeta en un elemento almacén reproducible normal
                    card.removeAttribute('data-filename');
                    card.onclick = function() {
                        playVideo(rutaMp4);
                    };
                }
            });
        });
}

// Consultas automáticas de fondo cada 4 segundos
setInterval(verificarEstados, 4000);