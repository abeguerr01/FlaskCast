function playVideo(filename) {
    const container = document.getElementById('playerContainer');
    const player = document.getElementById('mainPlayer');
    const title = document.getElementById('currentTitle');

    player.src = '/video/' + encodeURIComponent(filename);
    title.innerText = filename;
    
    container.style.display = 'block';
    container.scrollIntoView({ behavior: 'smooth' });
    player.play();
}

function convertirVideo(filename, button) {
    const card = button.closest('.video-card');
    card.classList.add('converting');

    fetch('/api/convertir/' + encodeURIComponent(filename), { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            console.log("Conversión iniciada para: " + filename, data);
        })
        .catch(err => console.error("Error al solicitar conversión:", err));
}

function eliminarVideo(filename, button) {
    if (!confirm(`¿Estás seguro de que quieres eliminar físicamente el archivo:\n${filename}?`)) return;

    const card = button.closest('.video-card');

    fetch('/api/eliminar/' + encodeURIComponent(filename), { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'eliminado') {
                card.remove(); // Quitamos la tarjeta de la interfaz visualmente
            }
        })
        .catch(err => console.error("Error al eliminar:", err));
}

// Mecanismo de Polling (Consulta paralela continua)
function verificarEstados() {
    fetch('/api/estados')
        .then(res => res.json())
        .then(data => {
            const activos = data.activos;
            
            // Buscamos todas las tarjetas incompatibles del HTML
            document.querySelectorAll('.video-card.incompatible').forEach(card => {
                const filename = card.getAttribute('data-filename');
                
                if (activos.includes(filename)) {
                    // Si el servidor reporta que sigue procesándose, aseguramos su animación
                    card.classList.add('converting');
                } else if (card.classList.contains('converting')) {
                    // Si tenía la animación pero ya no está activo en el backend... ¡ha terminado!
                    // Forzamos una recarga rápida para que aparezca el nuevo .mp4 generado
                    window.location.reload();
                }
            });
        });
}

// Consultar el estado del backend cada 4 segundos
setInterval(verificarEstados, 4000);