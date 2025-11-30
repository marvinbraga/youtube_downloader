/**
 * YouTube Downloader - Web Client
 * Frontend application for downloading and playing audio/video from YouTube
 */

$(document).ready(function() {
    // ========================================
    // Configuration
    // ========================================
    const API_BASE_URL = 'http://localhost:8000';
    const CLIENT_ID = 'your_client_id';
    const CLIENT_SECRET = 'your_client_secret';

    // ========================================
    // State
    // ========================================
    let authToken = null;
    let currentAudios = [];
    let currentVideos = [];
    let currentAudioId = null;
    let currentVideoId = null;
    let activeDownloads = new Map();

    // ========================================
    // Bootstrap Components
    // ========================================
    const toastEl = document.getElementById('liveToast');
    const toast = new bootstrap.Toast(toastEl, { delay: 5000 });
    const loadingModal = new bootstrap.Modal(document.getElementById('loadingModal'));

    // ========================================
    // Utility Functions
    // ========================================
    function showToast(message, type = 'info') {
        const iconMap = {
            'success': 'bi-check-circle-fill text-success',
            'error': 'bi-exclamation-circle-fill text-danger',
            'warning': 'bi-exclamation-triangle-fill text-warning',
            'info': 'bi-info-circle-fill text-info'
        };

        $('#toastIcon').attr('class', `bi ${iconMap[type]} me-2`);
        $('#toastTitle').text(type === 'error' ? 'Erro' : type === 'success' ? 'Sucesso' : 'Informação');
        $('#toastBody').text(message);
        toast.show();
    }

    function showLoading(message = 'Processando...') {
        $('#loadingModalText').text(message);
        loadingModal.show();
    }

    function hideLoading() {
        loadingModal.hide();
    }

    function formatFileSize(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return (bytes / Math.pow(1024, i)).toFixed(2) + ' ' + sizes[i];
    }

    function formatDate(dateString) {
        if (!dateString) return '-';
        const date = new Date(dateString);
        return date.toLocaleDateString('pt-BR') + ' ' + date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    }

    function formatDuration(seconds) {
        if (!seconds) return '-';
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        if (hrs > 0) {
            return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    function getAuthHeaders() {
        return {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
        };
    }

    function validateYouTubeUrl(url) {
        return url && (url.includes('youtube.com/') || url.includes('youtu.be/'));
    }

    // ========================================
    // Authentication
    // ========================================
    async function authenticate() {
        try {
            console.log('Authenticating...');
            const response = await $.ajax({
                url: `${API_BASE_URL}/auth/token`,
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    client_id: CLIENT_ID,
                    client_secret: CLIENT_SECRET
                })
            });

            authToken = response.access_token;
            updateAuthStatus(true);
            console.log('Authentication successful');

            // Refresh token before expiration
            setTimeout(authenticate, 25 * 60 * 1000);

            // Load initial data
            loadAudioList();
            loadVideoList();

        } catch (error) {
            console.error('Authentication error:', error);
            updateAuthStatus(false);
            showToast('Erro de autenticação. Verifique se o servidor está rodando.', 'error');
        }
    }

    function updateAuthStatus(connected) {
        const badge = $('#authBadge');
        const status = $('#authStatus');

        if (connected) {
            badge.removeClass('bg-danger').addClass('bg-success');
            status.text('Conectado');
        } else {
            badge.removeClass('bg-success').addClass('bg-danger');
            status.text('Desconectado');
        }
    }

    // ========================================
    // Audio Functions
    // ========================================
    async function loadAudioList() {
        if (!authToken) {
            await authenticate();
            return;
        }

        try {
            const response = await $.ajax({
                url: `${API_BASE_URL}/audio/list`,
                method: 'GET',
                headers: getAuthHeaders()
            });

            currentAudios = response.audio_files || [];
            renderAudioList(currentAudios);

        } catch (error) {
            console.error('Error loading audios:', error);
            if (error.status === 401) {
                authenticate();
            } else {
                renderAudioList([]);
                showToast('Erro ao carregar lista de áudios', 'error');
            }
        }
    }

    function renderAudioList(audios, searchTerm = '') {
        const container = $('#audioList');
        container.empty();

        if (audios.length === 0) {
            container.html(`
                <div class="text-center py-5 text-body-secondary">
                    <i class="bi bi-music-note-beamed fs-1 mb-3 d-block opacity-50"></i>
                    <p class="mb-0">Nenhum áudio encontrado</p>
                </div>
            `);
            return;
        }

        audios.forEach(audio => {
            const isActive = audio.id === currentAudioId;
            const statusBadge = getStatusBadge(audio.download_status);

            const item = $(`
                <a href="#" class="list-group-item list-group-item-action media-item ${isActive ? 'active' : ''}"
                   data-id="${audio.id}">
                    <div class="d-flex w-100 align-items-center">
                        <div class="me-3">
                            <div class="bg-body-tertiary rounded d-flex align-items-center justify-content-center"
                                 style="width: 48px; height: 48px;">
                                <i class="bi bi-music-note-beamed text-danger fs-5"></i>
                            </div>
                        </div>
                        <div class="flex-grow-1 min-width-0">
                            <h6 class="mb-1 text-truncate">${highlightText(audio.title || audio.name, searchTerm)}</h6>
                            <small class="text-body-tertiary">
                                <span class="me-3"><i class="bi bi-hdd me-1"></i>${formatFileSize(audio.filesize)}</span>
                                <span><i class="bi bi-calendar me-1"></i>${formatDate(audio.modified_date)}</span>
                            </small>
                        </div>
                        <div class="ms-2 d-flex align-items-center gap-2">
                            ${statusBadge}
                            <button class="btn btn-sm btn-danger play-audio-btn" data-id="${audio.id}">
                                <i class="bi bi-play-fill"></i>
                            </button>
                        </div>
                    </div>
                </a>
            `);

            item.find('.play-audio-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                playAudio(audio);
            });

            item.on('click', (e) => {
                e.preventDefault();
                playAudio(audio);
            });

            container.append(item);
        });
    }

    async function playAudio(audio) {
        if (!authToken) {
            showToast('Não autenticado', 'error');
            return;
        }

        try {
            currentAudioId = audio.id;
            $('#currentAudioTitle').text(audio.title || audio.name);

            // Update active state in list
            $('.media-item').removeClass('active');
            $(`.media-item[data-id="${audio.id}"]`).addClass('active');

            // Load audio
            const audioPlayer = document.getElementById('audioPlayer');
            audioPlayer.src = `${API_BASE_URL}/audio/stream/${audio.id}?token=${authToken}`;
            audioPlayer.load();
            audioPlayer.play();

        } catch (error) {
            console.error('Error playing audio:', error);
            showToast('Erro ao reproduzir áudio', 'error');
        }
    }

    // ========================================
    // Video Functions
    // ========================================
    async function loadVideoList() {
        if (!authToken) {
            await authenticate();
            return;
        }

        try {
            const response = await $.ajax({
                url: `${API_BASE_URL}/video/list-downloads`,
                method: 'GET',
                headers: getAuthHeaders()
            });

            currentVideos = response.videos || [];
            renderVideoList(currentVideos);

        } catch (error) {
            console.error('Error loading videos:', error);
            if (error.status === 401) {
                authenticate();
            } else {
                renderVideoList([]);
            }
        }
    }

    function renderVideoList(videos, searchTerm = '') {
        const container = $('#videoList');
        container.empty();

        if (videos.length === 0) {
            container.html(`
                <div class="text-center py-5 text-body-secondary">
                    <i class="bi bi-camera-video fs-1 mb-3 d-block opacity-50"></i>
                    <p class="mb-0">Nenhum vídeo encontrado</p>
                </div>
            `);
            return;
        }

        videos.forEach(video => {
            const isActive = video.id === currentVideoId;
            const statusBadge = getStatusBadge(video.download_status);

            const item = $(`
                <a href="#" class="list-group-item list-group-item-action media-item ${isActive ? 'active' : ''}"
                   data-id="${video.id}">
                    <div class="d-flex w-100 align-items-center">
                        <div class="me-3">
                            <div class="bg-body-tertiary rounded d-flex align-items-center justify-content-center"
                                 style="width: 48px; height: 48px;">
                                <i class="bi bi-camera-video text-danger fs-5"></i>
                            </div>
                        </div>
                        <div class="flex-grow-1 min-width-0">
                            <h6 class="mb-1 text-truncate">${highlightText(video.title || video.name, searchTerm)}</h6>
                            <small class="text-body-tertiary">
                                <span class="me-3"><i class="bi bi-hdd me-1"></i>${formatFileSize(video.filesize)}</span>
                                <span class="me-3"><i class="bi bi-aspect-ratio me-1"></i>${video.resolution || '-'}</span>
                                <span><i class="bi bi-clock me-1"></i>${formatDuration(video.duration)}</span>
                            </small>
                        </div>
                        <div class="ms-2 d-flex align-items-center gap-2">
                            ${statusBadge}
                            <button class="btn btn-sm btn-danger play-video-btn" data-id="${video.id}"
                                    ${video.download_status !== 'ready' ? 'disabled' : ''}>
                                <i class="bi bi-play-fill"></i>
                            </button>
                        </div>
                    </div>
                </a>
            `);

            item.find('.play-video-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (video.download_status === 'ready') {
                    playVideo(video);
                }
            });

            item.on('click', (e) => {
                e.preventDefault();
                if (video.download_status === 'ready') {
                    playVideo(video);
                }
            });

            container.append(item);
        });
    }

    async function playVideo(video) {
        if (!authToken) {
            showToast('Não autenticado', 'error');
            return;
        }

        try {
            currentVideoId = video.id;
            $('#currentVideoTitle').text(video.title || video.name);

            // Update active state in list
            $('.media-item').removeClass('active');
            $(`.media-item[data-id="${video.id}"]`).addClass('active');

            // Show loading overlay
            $('#videoLoadingOverlay').removeClass('d-none').addClass('d-flex');

            // Load video stream
            const videoPlayer = document.getElementById('videoPlayer');

            const response = await fetch(`${API_BASE_URL}/video/stream/${video.youtube_id || video.id}`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);

            videoPlayer.src = url;
            videoPlayer.onloadeddata = () => {
                $('#videoLoadingOverlay').removeClass('d-flex').addClass('d-none');
            };
            videoPlayer.onerror = () => {
                $('#videoLoadingOverlay').removeClass('d-flex').addClass('d-none');
                showToast('Erro ao carregar vídeo', 'error');
            };
            videoPlayer.onended = () => {
                URL.revokeObjectURL(url);
            };

            videoPlayer.load();
            videoPlayer.play();

        } catch (error) {
            console.error('Error playing video:', error);
            $('#videoLoadingOverlay').removeClass('d-flex').addClass('d-none');
            showToast('Erro ao reproduzir vídeo', 'error');
        }
    }

    // ========================================
    // Download Functions
    // ========================================
    async function downloadAudio() {
        const url = $('#audioUrl').val().trim();
        const highQuality = $('#highQuality').is(':checked');

        if (!validateYouTubeUrl(url)) {
            showToast('Por favor, insira uma URL válida do YouTube', 'warning');
            return;
        }

        if (!authToken) {
            showToast('Não autenticado', 'error');
            return;
        }

        try {
            showLoading('Iniciando download de áudio...');

            const response = await $.ajax({
                url: `${API_BASE_URL}/audio/download`,
                method: 'POST',
                headers: getAuthHeaders(),
                data: JSON.stringify({
                    url: url,
                    high_quality: highQuality
                })
            });

            hideLoading();

            if (response.status === 'processando') {
                showToast('Download de áudio iniciado com sucesso!', 'success');
                $('#audioUrl').val('');

                // Add to active downloads
                addActiveDownload(response.audio_id, 'audio', response.title || 'Áudio');

                // Start polling for status
                pollDownloadStatus(response.audio_id, 'audio');
            } else {
                showToast('Falha ao iniciar download', 'error');
            }

        } catch (error) {
            hideLoading();
            console.error('Error downloading audio:', error);
            const message = error.responseJSON?.detail || 'Erro ao fazer download';
            showToast(message, 'error');
        }
    }

    async function downloadVideo() {
        const url = $('#videoUrl').val().trim();
        const resolution = $('#videoResolution').val();

        if (!validateYouTubeUrl(url)) {
            showToast('Por favor, insira uma URL válida do YouTube', 'warning');
            return;
        }

        if (!authToken) {
            showToast('Não autenticado', 'error');
            return;
        }

        try {
            showLoading('Iniciando download de vídeo...');

            const response = await $.ajax({
                url: `${API_BASE_URL}/video/download`,
                method: 'POST',
                headers: getAuthHeaders(),
                data: JSON.stringify({
                    url: url,
                    resolution: resolution
                })
            });

            hideLoading();

            if (response.status === 'processando') {
                showToast(`Download de vídeo iniciado (${resolution})!`, 'success');
                $('#videoUrl').val('');

                // Add to active downloads
                addActiveDownload(response.video_id, 'video', 'Vídeo');

                // Start polling for status
                pollDownloadStatus(response.video_id, 'video');
            } else {
                showToast('Falha ao iniciar download', 'error');
            }

        } catch (error) {
            hideLoading();
            console.error('Error downloading video:', error);
            const message = error.responseJSON?.detail || 'Erro ao fazer download';
            showToast(message, 'error');
        }
    }

    function addActiveDownload(id, type, title) {
        // Não adicionar se já existe
        if (activeDownloads.has(id)) {
            return;
        }
        activeDownloads.set(id, { type, title, progress: 0, status: 'downloading' });
        updateProgressUI();
    }

    function updateProgressUI() {
        const container = $('#progressContainer');
        const card = $('#progressCard');

        if (activeDownloads.size === 0) {
            card.hide();
            return;
        }

        card.show();
        container.empty();

        activeDownloads.forEach((download, id) => {
            const icon = download.type === 'video' ? 'bi-camera-video' : 'bi-music-note';
            const statusClass = download.status === 'ready' ? 'bg-success' :
                               download.status === 'error' ? 'bg-danger' : 'bg-danger';

            // Determinar o label baseado no progresso
            // 0-94% = Baixando, 95-99% = Convertendo, 100% = Concluído
            let statusLabel = 'Baixando...';
            let statusIcon = 'bi-arrow-down-circle';
            if (download.progress >= 95 && download.progress < 100) {
                statusLabel = 'Convertendo...';
                statusIcon = 'bi-gear';
            } else if (download.progress >= 100) {
                statusLabel = 'Concluído';
                statusIcon = 'bi-check-circle';
            }

            const progressItem = $(`
                <div class="mb-3" data-download-id="${id}">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="d-flex align-items-center gap-2">
                            <i class="bi ${icon} text-danger"></i>
                            <span class="text-truncate" style="max-width: 300px;">${download.title}</span>
                        </span>
                        <span class="d-flex align-items-center gap-2">
                            <span class="badge bg-secondary"><i class="bi ${statusIcon} me-1"></i>${statusLabel}</span>
                            <span class="badge ${statusClass}">${download.progress}%</span>
                        </span>
                    </div>
                    <div class="progress" style="height: 6px;">
                        <div class="progress-bar ${statusClass} progress-bar-striped progress-bar-animated"
                             style="width: ${download.progress}%"></div>
                    </div>
                </div>
            `);

            container.append(progressItem);
        });
    }

    async function pollDownloadStatus(id, type) {
        if (!authToken) return;

        const endpoint = type === 'video' ?
            `${API_BASE_URL}/video/download-status/${id}` :
            `${API_BASE_URL}/audio/download-status/${id}`;

        try {
            const response = await $.ajax({
                url: endpoint,
                method: 'GET',
                headers: getAuthHeaders()
            });

            const download = activeDownloads.get(id);
            if (download) {
                download.progress = response.download_progress || 0;
                download.status = response.download_status;
                updateProgressUI();

                if (response.download_status === 'ready') {
                    showToast(`Download concluído: ${download.title}`, 'success');
                    // Remover imediatamente
                    activeDownloads.delete(id);
                    updateProgressUI();

                    // Reload appropriate list
                    if (type === 'video') loadVideoList();
                    else loadAudioList();

                } else if (response.download_status === 'error') {
                    showToast(`Erro no download: ${download.title}`, 'error');
                    // Remover imediatamente
                    activeDownloads.delete(id);
                    updateProgressUI();

                } else {
                    // Continue polling
                    setTimeout(() => pollDownloadStatus(id, type), 2000);
                }
            }

        } catch (error) {
            console.error('Error polling status:', error);
        }
    }

    // ========================================
    // Helper Functions
    // ========================================
    function getStatusBadge(status) {
        const badges = {
            'ready': '<span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>Pronto</span>',
            'downloading': '<span class="badge bg-warning"><i class="bi bi-arrow-down-circle me-1"></i>Baixando</span>',
            'pending': '<span class="badge bg-secondary"><i class="bi bi-clock me-1"></i>Pendente</span>',
            'error': '<span class="badge bg-danger"><i class="bi bi-x-circle me-1"></i>Erro</span>'
        };
        return badges[status] || '';
    }

    function highlightText(text, searchTerm) {
        if (!searchTerm || !text) return text || '';
        const regex = new RegExp(`(${searchTerm})`, 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }

    function filterList(items, searchTerm, renderFn) {
        if (!searchTerm) {
            renderFn(items);
            return;
        }

        const term = searchTerm.toLowerCase();
        const filtered = items.filter(item =>
            (item.title && item.title.toLowerCase().includes(term)) ||
            (item.name && item.name.toLowerCase().includes(term))
        );

        renderFn(filtered, searchTerm);
    }

    // ========================================
    // Event Listeners
    // ========================================

    // Download buttons
    $('#downloadAudioBtn').on('click', downloadAudio);
    $('#downloadVideoBtn').on('click', downloadVideo);

    // Refresh buttons
    $('#refreshAudioBtn').on('click', () => {
        loadAudioList();
        showToast('Lista de áudios atualizada', 'info');
    });

    $('#refreshVideoBtn').on('click', () => {
        loadVideoList();
        showToast('Lista de vídeos atualizada', 'info');
    });

    // Search inputs
    let audioSearchTimeout;
    $('#searchAudioInput').on('input', function() {
        clearTimeout(audioSearchTimeout);
        const searchTerm = $(this).val();
        audioSearchTimeout = setTimeout(() => {
            filterList(currentAudios, searchTerm, renderAudioList);
        }, 300);
    });

    let videoSearchTimeout;
    $('#searchVideoInput').on('input', function() {
        clearTimeout(videoSearchTimeout);
        const searchTerm = $(this).val();
        videoSearchTimeout = setTimeout(() => {
            filterList(currentVideos, searchTerm, renderVideoList);
        }, 300);
    });

    // Tab change events
    $('button[data-bs-toggle="pill"]').on('shown.bs.tab', function(e) {
        const target = $(e.target).attr('data-bs-target');
        if (target === '#audio-pane') {
            loadAudioList();
        } else if (target === '#video-pane') {
            loadVideoList();
        }
    });

    // Prevent video right-click
    $('#videoPlayer').on('contextmenu', (e) => e.preventDefault());

    // Enter key on URL inputs
    $('#audioUrl').on('keypress', function(e) {
        if (e.which === 13) downloadAudio();
    });

    $('#videoUrl').on('keypress', function(e) {
        if (e.which === 13) downloadVideo();
    });

    // ========================================
    // Initialize
    // ========================================
    authenticate();
});
