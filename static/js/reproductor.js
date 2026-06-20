// Obtener el nombre de la serie actual desde el marcado HTML
const serieContainer = document.getElementById('serieContainer');
const NOMBRE_SERIE = serieContainer ? serieContainer.getAttribute('data-serie') : '';

function playVideo(filename) {
    const container = document.getElementById('playerContainer');
    const player = document.getElementById('mainPlayer');
    const title = document.getElementById('currentTitle');

    player.src = '/video/' + encodeURIComponent(NOMBRE_SERIE) + '/' + encodeURIComponent(filename);
    title.innerText = filename;
    
    container.style.display = 'block';
    container.scrollIntoView({ behavior: 'smooth' });
    player.play();
}

function convertirVideo(filename, button) {
    const card = button.closest('.video-card');
    card.classList.add('converting');

    fetch('/api/convertir/' + encodeURIComponent(NOMBRE_SERIE) + '/' + encodeURIComponent(filename), { method: 'POST' })
        .then(res => res.json())
        .catch(err => console.error("Error al convertir:", err));
}

function eliminarVideo(filename, button) {
    if (!confirm(`¿Estás seguro de que quieres eliminar físicamente el archivo:\n${filename}?`)) return;

    const card = button.closest('.video-card');

    fetch('/api/eliminar/' + encodeURIComponent(NOMBRE_SERIE) + '/' + encodeURIComponent(filename), { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'eliminado') card.remove();
        })
        .catch(err => console.error("Error al eliminar:", err));
}

function verificarEstados() {
    if (!NOMBRE_SERIE) return; // Si estamos en el catálogo general, no ejecutar polling

    fetch('/api/estados')
        .then(res => res.json())
        .then(data => {
            const activos = data.activos;
            
            document.querySelectorAll('.video-card.incompatible').forEach(card => {
                const filename = card.getAttribute('data-filename');
                const identificadorUnico = NOMBRE_SERIE + '/' + filename;
                
                if (activos.includes(identificadorUnico)) {
                    card.classList.add('converting');
                } else if (card.classList.contains('converting')) {
                    // Si estaba convirtiendo y ya terminó, recargamos la vista de capítulos
                    window.location.reload();
                }
            });
        });
}

// Consultar cambios asíncronos cada 4 segundos
setInterval(verificarEstados, 4000);