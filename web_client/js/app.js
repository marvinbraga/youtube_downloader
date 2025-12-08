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
    let currentTranscription = null;
    let currentTranscriptionId = null;

    // Folder state
    let currentFolders = [];
    let currentFolderId = null;  // null = root folder
    let folderPath = [];  // breadcrumb path
    let selectedItems = [];  // {id, type} - itens selecionados para mover em lote

    // ========================================
    // Bootstrap Components
    // ========================================
    const toastEl = document.getElementById('liveToast');
    const toast = new bootstrap.Toast(toastEl, { delay: 5000 });
    const loadingModal = new bootstrap.Modal(document.getElementById('loadingModal'));
    const transcriptionModal = new bootstrap.Modal(document.getElementById('transcriptionModal'));
    const folderModal = new bootstrap.Modal(document.getElementById('folderModal'));
    const moveItemModal = new bootstrap.Modal(document.getElementById('moveItemModal'));

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
        try {
            loadingModal.hide();
        } catch (e) {
            console.error('Error hiding modal:', e);
        }
        // Limpeza imediata
        cleanupModals();
        // Limpeza adicional após delay para garantir
        setTimeout(cleanupModals, 100);
        setTimeout(cleanupModals, 300);
    }

    function cleanupModals() {
        // Limpar o modal de loading
        const modalEl = document.getElementById('loadingModal');
        if (modalEl) {
            modalEl.classList.remove('show');
            modalEl.style.display = 'none';
            modalEl.setAttribute('aria-hidden', 'true');
            modalEl.removeAttribute('aria-modal');
            modalEl.removeAttribute('role');
        }
        // Remover TODOS os backdrops (pode haver múltiplos)
        document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
            backdrop.remove();
        });
        // Limpar estilos do body
        document.body.classList.remove('modal-open');
        document.body.style.removeProperty('padding-right');
        document.body.style.removeProperty('overflow');
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
                            <button class="btn btn-sm btn-danger play-audio-btn" data-id="${audio.id}" title="Reproduzir">
                                <i class="bi bi-play-fill"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger delete-audio-btn" data-id="${audio.id}" title="Excluir">
                                <i class="bi bi-trash"></i>
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

            item.find('.delete-audio-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                confirmDeleteAudio(audio);
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
                                    ${video.download_status !== 'ready' ? 'disabled' : ''} title="Reproduzir">
                                <i class="bi bi-play-fill"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger delete-video-btn" data-id="${video.id}" title="Excluir">
                                <i class="bi bi-trash"></i>
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

            item.find('.delete-video-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                confirmDeleteVideo(video);
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
    // Delete Functions
    // ========================================
    const deleteModalEl = document.getElementById('deleteModal');
    const deleteModal = new bootstrap.Modal(deleteModalEl);
    let pendingDeleteItem = null;
    let pendingDeleteType = null;

    function confirmDeleteAudio(audio) {
        const title = audio.title || audio.name || audio.id;
        pendingDeleteItem = audio;
        pendingDeleteType = 'audio';
        $('#deleteItemTitle').text(`"${title}"`);
        $('#deleteModalLabel').html('<i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>Excluir Áudio');
        deleteModal.show();
    }

    function confirmDeleteVideo(video) {
        const title = video.title || video.name || video.id;
        pendingDeleteItem = video;
        pendingDeleteType = 'video';
        $('#deleteItemTitle').text(`"${title}"`);
        $('#deleteModalLabel').html('<i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>Excluir Vídeo');
        deleteModal.show();
    }

    // Handle confirm delete button click
    $('#confirmDeleteBtn').on('click', function() {
        deleteModal.hide();
        if (pendingDeleteTranscriptionId) {
            deleteTranscription(pendingDeleteTranscriptionId);
            pendingDeleteTranscriptionId = null;
            pendingDeleteTranscriptionTitle = null;
        } else if (pendingDeleteFolder && pendingDeleteType === 'folder') {
            deleteFolder(pendingDeleteFolder.id);
            pendingDeleteFolder = null;
            pendingDeleteType = null;
        } else if (pendingDeleteItem && pendingDeleteType) {
            if (pendingDeleteType === 'audio') {
                deleteAudio(pendingDeleteItem.id);
            } else if (pendingDeleteType === 'video') {
                deleteVideo(pendingDeleteItem.id);
            }
            pendingDeleteItem = null;
            pendingDeleteType = null;
        }
    });

    // Clear pending delete on modal close
    deleteModalEl.addEventListener('hidden.bs.modal', function() {
        pendingDeleteItem = null;
        pendingDeleteType = null;
        pendingDeleteTranscriptionId = null;
        pendingDeleteTranscriptionTitle = null;
        pendingDeleteFolder = null;
    });

    async function deleteAudio(audioId) {
        if (!authToken) {
            showToast('Não autenticado', 'error');
            return;
        }

        try {
            showLoading('Excluindo áudio...');

            await $.ajax({
                url: `${API_BASE_URL}/audio/${audioId}`,
                method: 'DELETE',
                headers: getAuthHeaders(),
                timeout: 30000 // 30 segundos
            });

            // Se o áudio excluído estava tocando, parar o player
            if (currentAudioId === audioId) {
                const audioPlayer = document.getElementById('audioPlayer');
                audioPlayer.pause();
                audioPlayer.src = '';
                currentAudioId = null;
                $('#currentAudioTitle').text('Selecione um áudio para reproduzir');
            }

            // Atualiza a lista e depois fecha o loading
            await loadAudioList();
            hideLoading();
            showToast('Áudio excluído com sucesso!', 'success');

        } catch (error) {
            hideLoading();
            console.error('Error deleting audio:', error);
            const message = error.responseJSON?.detail || 'Erro ao excluir áudio';
            showToast(message, 'error');
        }
    }

    async function deleteVideo(videoId) {
        if (!authToken) {
            showToast('Não autenticado', 'error');
            return;
        }

        try {
            showLoading('Excluindo vídeo...');

            await $.ajax({
                url: `${API_BASE_URL}/video/${videoId}`,
                method: 'DELETE',
                headers: getAuthHeaders(),
                timeout: 30000 // 30 segundos
            });

            // Se o vídeo excluído estava tocando, parar o player
            if (currentVideoId === videoId) {
                const videoPlayer = document.getElementById('videoPlayer');
                videoPlayer.pause();
                videoPlayer.src = '';
                currentVideoId = null;
                $('#currentVideoTitle').text('Selecione um vídeo para reproduzir');
            }

            // Atualiza a lista e depois fecha o loading
            await loadVideoList();
            hideLoading();
            showToast('Vídeo excluído com sucesso!', 'success');

        } catch (error) {
            hideLoading();
            console.error('Error deleting video:', error);
            const message = error.responseJSON?.detail || 'Erro ao excluir vídeo';
            showToast(message, 'error');
        }
    }

    // ========================================
    // Transcription Functions
    // ========================================
    async function loadTranscriptionMediaList() {
        if (!authToken) {
            await authenticate();
            return;
        }

        try {
            // Load both audios and videos
            const [audioResponse, videoResponse] = await Promise.all([
                $.ajax({
                    url: `${API_BASE_URL}/audio/list`,
                    method: 'GET',
                    headers: getAuthHeaders()
                }),
                $.ajax({
                    url: `${API_BASE_URL}/video/list-downloads`,
                    method: 'GET',
                    headers: getAuthHeaders()
                })
            ]);

            const audios = (audioResponse.audio_files || []).map(a => ({ ...a, mediaType: 'audio' }));
            const videos = (videoResponse.videos || []).filter(v => v.download_status === 'ready').map(v => ({ ...v, mediaType: 'video' }));

            const allMedia = [...audios, ...videos].sort((a, b) => {
                const dateA = new Date(a.modified_date || 0);
                const dateB = new Date(b.modified_date || 0);
                return dateB - dateA;
            });

            renderTranscriptionMediaList(allMedia);

        } catch (error) {
            console.error('Error loading transcription media list:', error);
            if (error.status === 401) {
                authenticate();
            } else {
                renderTranscriptionMediaList([]);
                showToast('Erro ao carregar lista de mídias', 'error');
            }
        }
    }

    function renderTranscriptionMediaList(mediaList) {
        const container = $('#transcriptionMediaList');
        container.empty();

        if (mediaList.length === 0) {
            container.html(`
                <div class="text-center py-5 text-body-secondary">
                    <i class="bi bi-collection fs-1 mb-3 d-block opacity-50"></i>
                    <p class="mb-0">Nenhuma mídia encontrada</p>
                </div>
            `);
            return;
        }

        mediaList.forEach(media => {
            const isAudio = media.mediaType === 'audio';
            const icon = isAudio ? 'bi-music-note-beamed' : 'bi-camera-video';
            const typeBadge = isAudio ?
                '<span class="badge bg-info"><i class="bi bi-music-note me-1"></i>Áudio</span>' :
                '<span class="badge bg-primary"><i class="bi bi-camera-video me-1"></i>Vídeo</span>';

            const transcriptionStatus = getTranscriptionStatusBadge(media.transcription_status);

            const item = $(`
                <div class="list-group-item list-group-item-action transcription-media-item" data-id="${media.id}" data-type="${media.mediaType}">
                    <div class="d-flex w-100 align-items-center">
                        <div class="me-3">
                            <div class="bg-body-tertiary rounded d-flex align-items-center justify-content-center"
                                 style="width: 48px; height: 48px;">
                                <i class="bi ${icon} text-danger fs-5"></i>
                            </div>
                        </div>
                        <div class="flex-grow-1 min-width-0">
                            <h6 class="mb-1 text-truncate">${media.title || media.name}</h6>
                            <small class="text-body-tertiary">
                                ${typeBadge}
                                <span class="ms-2"><i class="bi bi-hdd me-1"></i>${formatFileSize(media.filesize)}</span>
                                <span class="ms-2"><i class="bi bi-calendar me-1"></i>${formatDate(media.modified_date)}</span>
                            </small>
                        </div>
                        <div class="ms-2 d-flex align-items-center gap-2">
                            ${transcriptionStatus}
                            <button class="btn btn-sm btn-outline-info view-transcription-btn" data-id="${media.id}"
                                    title="Ver Transcrição" ${media.transcription_status !== 'ended' ? 'disabled' : ''}>
                                <i class="bi bi-eye"></i>
                            </button>
                            <button class="btn btn-sm btn-danger start-transcription-btn" data-id="${media.id}"
                                    title="Transcrever" ${media.transcription_status === 'started' ? 'disabled' : ''}>
                                <i class="bi bi-file-text"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger delete-transcription-btn" data-id="${media.id}"
                                    title="Excluir Transcrição" ${media.transcription_status !== 'ended' ? 'disabled' : ''}>
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `);

            item.find('.start-transcription-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                startTranscription(media.id);
            });

            item.find('.view-transcription-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                viewTranscription(media.id, media.title || media.name);
            });

            item.find('.delete-transcription-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                confirmDeleteTranscription(media.id, media.title || media.name);
            });

            container.append(item);
        });
    }

    function getTranscriptionStatusBadge(status) {
        const badges = {
            'ended': '<span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>Transcrito</span>',
            'started': '<span class="badge bg-warning"><i class="bi bi-hourglass-split me-1"></i>Em andamento</span>',
            'error': '<span class="badge bg-danger"><i class="bi bi-x-circle me-1"></i>Erro</span>',
            'none': '<span class="badge bg-secondary"><i class="bi bi-dash-circle me-1"></i>Não transcrito</span>'
        };
        return badges[status] || badges['none'];
    }

    async function startTranscription(fileId) {
        if (!authToken) {
            showToast('Não autenticado', 'error');
            return;
        }

        const provider = $('#transcriptionProvider').val();
        const language = $('#transcriptionLanguage').val();

        try {
            showLoading('Iniciando transcrição...');

            const response = await $.ajax({
                url: `${API_BASE_URL}/audio/transcribe`,
                method: 'POST',
                headers: getAuthHeaders(),
                data: JSON.stringify({
                    file_id: fileId,
                    provider: provider,
                    language: language
                })
            });

            hideLoading();

            if (response.status === 'processing' || response.status === 'success') {
                showToast('Transcrição iniciada! Este processo pode levar alguns minutos.', 'success');
                // Start polling for status
                pollTranscriptionStatus(fileId);
            } else if (response.message && response.message.includes('já existe')) {
                showToast('Transcrição já existe para este arquivo.', 'info');
                viewTranscription(fileId);
            } else {
                showToast(response.message || 'Transcrição iniciada', 'info');
            }

            // Reload list to update status
            loadTranscriptionMediaList();

        } catch (error) {
            hideLoading();
            console.error('Error starting transcription:', error);
            const message = error.responseJSON?.detail || 'Erro ao iniciar transcrição';
            showToast(message, 'error');
        }
    }

    async function pollTranscriptionStatus(fileId) {
        if (!authToken) return;

        try {
            const response = await $.ajax({
                url: `${API_BASE_URL}/audio/transcription_status/${fileId}`,
                method: 'GET',
                headers: getAuthHeaders()
            });

            if (response.status === 'ended') {
                showToast('Transcrição concluída!', 'success');
                loadTranscriptionMediaList();
            } else if (response.status === 'error') {
                showToast('Erro na transcrição', 'error');
                loadTranscriptionMediaList();
            } else if (response.status === 'started') {
                // Continue polling
                setTimeout(() => pollTranscriptionStatus(fileId), 5000);
            }

        } catch (error) {
            console.error('Error polling transcription status:', error);
        }
    }

    async function viewTranscription(fileId, title = '') {
        if (!authToken) {
            showToast('Não autenticado', 'error');
            return;
        }

        try {
            showLoading('Carregando transcrição...');

            const response = await fetch(`${API_BASE_URL}/audio/transcription/${fileId}`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const text = await response.text();
            currentTranscription = text;
            currentTranscriptionId = fileId;

            hideLoading();

            // Update transcription pane
            $('#currentTranscriptionTitle').text(title || fileId);
            $('#transcriptionContent').html(`<pre class="transcription-text mb-0">${escapeHtml(text)}</pre>`);
            $('#copyTranscriptionBtn').prop('disabled', false);
            $('#downloadTranscriptionBtn').prop('disabled', false);
            $('#deleteTranscriptionBtn').prop('disabled', false);

            // Also update modal
            $('#transcriptionModalLabel').html(`<i class="bi bi-file-text text-danger me-2"></i>${title || 'Transcrição'}`);
            $('#transcriptionModalContent').html(`<pre class="transcription-text mb-0">${escapeHtml(text)}</pre>`);
            transcriptionModal.show();

        } catch (error) {
            hideLoading();
            console.error('Error loading transcription:', error);
            showToast('Erro ao carregar transcrição', 'error');
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function copyTranscription() {
        if (!currentTranscription) {
            showToast('Nenhuma transcrição para copiar', 'warning');
            return;
        }

        navigator.clipboard.writeText(currentTranscription).then(() => {
            showToast('Transcrição copiada para a área de transferência!', 'success');
        }).catch(err => {
            console.error('Error copying:', err);
            showToast('Erro ao copiar transcrição', 'error');
        });
    }

    function downloadTranscription() {
        if (!currentTranscription) {
            showToast('Nenhuma transcrição para baixar', 'warning');
            return;
        }

        const blob = new Blob([currentTranscription], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `transcription_${currentTranscriptionId || 'unknown'}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showToast('Download iniciado!', 'success');
    }

    let pendingDeleteTranscriptionId = null;
    let pendingDeleteTranscriptionTitle = null;

    function confirmDeleteTranscription(fileId, title) {
        pendingDeleteTranscriptionId = fileId;
        pendingDeleteTranscriptionTitle = title;
        $('#deleteItemTitle').text(`Transcrição de "${title}"`);
        $('#deleteModalLabel').html('<i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>Excluir Transcrição');
        deleteModal.show();
    }

    async function deleteTranscription(fileId) {
        if (!authToken) {
            showToast('Não autenticado', 'error');
            return;
        }

        try {
            showLoading('Excluindo transcrição...');

            await $.ajax({
                url: `${API_BASE_URL}/audio/transcription/${fileId}`,
                method: 'DELETE',
                headers: getAuthHeaders()
            });

            hideLoading();
            showToast('Transcrição excluída com sucesso!', 'success');

            // Limpa a visualização se era a transcrição atual
            if (currentTranscriptionId === fileId) {
                currentTranscription = null;
                currentTranscriptionId = null;
                $('#currentTranscriptionTitle').text('Selecione um item para ver a transcrição');
                $('#transcriptionContent').html(`
                    <p class="text-body-secondary text-center py-5">
                        <i class="bi bi-file-text fs-1 d-block mb-3 opacity-50"></i>
                        Selecione um áudio ou vídeo e clique em "Transcrever" para gerar a transcrição.
                    </p>
                `);
                $('#copyTranscriptionBtn').prop('disabled', true);
                $('#downloadTranscriptionBtn').prop('disabled', true);
                $('#deleteTranscriptionBtn').prop('disabled', true);
            }

            // Recarrega a lista
            loadTranscriptionMediaList();

        } catch (error) {
            hideLoading();
            console.error('Error deleting transcription:', error);
            const message = error.responseJSON?.detail || 'Erro ao excluir transcrição';
            showToast(message, 'error');
        }
    }

    // ========================================
    // Folder Functions
    // ========================================
    async function loadFolders(parentId = null) {
        if (!authToken) {
            await authenticate();
            return;
        }

        try {
            let url = `${API_BASE_URL}/folders`;
            if (parentId) {
                url = `${API_BASE_URL}/folders/${parentId}/children`;
            } else {
                url = `${API_BASE_URL}/folders/root`;
            }

            const response = await $.ajax({
                url: url,
                method: 'GET',
                headers: getAuthHeaders()
            });

            currentFolders = response || [];
            currentFolderId = parentId;
            renderFolderList(currentFolders);

            // Update back button state
            $('#backToParentBtn').prop('disabled', !parentId);

            // Load folder items
            if (parentId) {
                loadFolderItems(parentId);
            } else {
                renderFolderItems([], []);
            }

            // Load unorganized items
            loadUnorganizedItems();

        } catch (error) {
            console.error('Error loading folders:', error);
            if (error.status === 401) {
                authenticate();
            } else {
                renderFolderList([]);
            }
        }
    }

    function renderFolderList(folders) {
        const container = $('#folderList');
        container.empty();

        if (folders.length === 0) {
            container.html(`
                <div class="text-center py-4 text-body-secondary">
                    <i class="bi bi-folder2 fs-1 mb-3 d-block opacity-50"></i>
                    <p class="mb-0">Nenhuma pasta encontrada</p>
                    <small>Clique em "Nova Pasta" para criar</small>
                </div>
            `);
            return;
        }

        folders.forEach(folder => {
            const iconClass = folder.icon || 'folder2';
            const colorStyle = folder.color ? `color: ${folder.color}` : 'color: var(--bs-warning)';

            const item = $(`
                <a href="#" class="list-group-item list-group-item-action folder-item" data-id="${folder.id}">
                    <div class="d-flex w-100 align-items-center">
                        <div class="me-3">
                            <i class="bi bi-${iconClass} fs-4" style="${colorStyle}"></i>
                        </div>
                        <div class="flex-grow-1 min-width-0">
                            <h6 class="mb-0 text-truncate">${folder.name}</h6>
                            ${folder.description ? `<small class="text-body-tertiary">${folder.description}</small>` : ''}
                        </div>
                        <div class="ms-2 d-flex align-items-center gap-1">
                            <button class="btn btn-sm btn-outline-secondary edit-folder-btn" data-id="${folder.id}" title="Editar">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger delete-folder-btn" data-id="${folder.id}" title="Excluir">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                </a>
            `);

            // Navigate into folder
            item.on('click', (e) => {
                if ($(e.target).closest('.edit-folder-btn, .delete-folder-btn').length === 0) {
                    e.preventDefault();
                    navigateToFolder(folder);
                }
            });

            // Edit folder
            item.find('.edit-folder-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                openEditFolderModal(folder);
            });

            // Delete folder
            item.find('.delete-folder-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                confirmDeleteFolder(folder);
            });

            container.append(item);
        });
    }

    async function navigateToFolder(folder) {
        folderPath.push(folder);
        updateBreadcrumb();
        await loadFolders(folder.id);
        await loadFolderItems(folder.id);
    }

    async function navigateToRoot() {
        folderPath = [];
        currentFolderId = null;
        updateBreadcrumb();
        await loadFolders(null);
    }

    async function navigateBack() {
        if (folderPath.length > 0) {
            folderPath.pop();
            const parentFolder = folderPath.length > 0 ? folderPath[folderPath.length - 1] : null;
            currentFolderId = parentFolder ? parentFolder.id : null;
            updateBreadcrumb();
            await loadFolders(currentFolderId);
        }
    }

    function updateBreadcrumb() {
        const container = $('#folderBreadcrumb');
        container.empty();

        // Root
        const rootItem = $(`
            <li class="breadcrumb-item ${folderPath.length === 0 ? 'active' : ''}">
                <a href="#" class="text-decoration-none breadcrumb-link">
                    <i class="bi bi-house-fill me-1"></i>Raiz
                </a>
            </li>
        `);
        if (folderPath.length > 0) {
            rootItem.find('a').on('click', (e) => {
                e.preventDefault();
                navigateToRoot();
            });
        }
        container.append(rootItem);

        // Folder path
        folderPath.forEach((folder, index) => {
            const isLast = index === folderPath.length - 1;
            const pathItem = $(`
                <li class="breadcrumb-item ${isLast ? 'active' : ''}">
                    ${isLast ? folder.name : `<a href="#" class="text-decoration-none breadcrumb-link">${folder.name}</a>`}
                </li>
            `);
            if (!isLast) {
                pathItem.find('a').on('click', (e) => {
                    e.preventDefault();
                    // Navigate to this folder
                    folderPath = folderPath.slice(0, index + 1);
                    currentFolderId = folder.id;
                    updateBreadcrumb();
                    loadFolders(folder.id);
                });
            }
            container.append(pathItem);
        });
    }

    async function loadFolderItems(folderId) {
        if (!authToken) return;

        try {
            const response = await $.ajax({
                url: `${API_BASE_URL}/folders/${folderId}/items`,
                method: 'GET',
                headers: getAuthHeaders()
            });

            renderFolderItems(response.audios || [], response.videos || []);
            $('#folderItemCount').text(`${response.item_count || 0} itens`);

        } catch (error) {
            console.error('Error loading folder items:', error);
            renderFolderItems([], []);
        }
    }

    function renderFolderItems(audios, videos) {
        const container = $('#folderItemList');
        container.empty();

        const allItems = [
            ...audios.map(a => ({ ...a, itemType: 'audio' })),
            ...videos.map(v => ({ ...v, itemType: 'video' }))
        ];

        if (allItems.length === 0) {
            container.html(`
                <div class="text-center py-5 text-body-secondary">
                    <i class="bi bi-inbox fs-1 mb-3 d-block opacity-50"></i>
                    <p class="mb-0">Pasta vazia</p>
                </div>
            `);
            return;
        }

        allItems.forEach(item => {
            const isAudio = item.itemType === 'audio';
            const icon = isAudio ? 'bi-music-note-beamed' : 'bi-camera-video';
            const badgeClass = isAudio ? 'bg-info' : 'bg-primary';
            const isSelected = selectedItems.some(s => s.id === item.id && s.type === item.itemType);

            const element = $(`
                <div class="list-group-item list-group-item-action folder-media-item ${isSelected ? 'selected' : ''}" data-id="${item.id}" data-type="${item.itemType}">
                    <div class="d-flex w-100 align-items-center">
                        <div class="form-check me-2">
                            <input class="form-check-input item-checkbox" type="checkbox" ${isSelected ? 'checked' : ''}
                                   data-id="${item.id}" data-type="${item.itemType}">
                        </div>
                        <div class="me-3">
                            <i class="bi ${icon} text-danger fs-5"></i>
                        </div>
                        <div class="flex-grow-1 min-width-0">
                            <h6 class="mb-1 text-truncate">${item.title || item.name}</h6>
                            <small class="text-body-tertiary">
                                <span class="badge ${badgeClass} me-2">${isAudio ? 'Áudio' : 'Vídeo'}</span>
                                <span><i class="bi bi-hdd me-1"></i>${formatFileSize(item.filesize)}</span>
                            </small>
                        </div>
                        <div class="ms-2 d-flex align-items-center gap-1">
                            <button class="btn btn-sm btn-success play-item-btn" data-id="${item.id}" data-type="${item.itemType}" title="Reproduzir">
                                <i class="bi bi-play-fill"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-secondary move-item-btn" data-id="${item.id}" data-type="${item.itemType}" title="Mover">
                                <i class="bi bi-arrow-right-circle"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-warning remove-from-folder-btn" data-id="${item.id}" data-type="${item.itemType}" title="Remover da pasta">
                                <i class="bi bi-x-circle"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `);

            element.find('.item-checkbox').on('change', (e) => {
                e.stopPropagation();
                toggleItemSelection(item.id, item.itemType, e.target.checked);
                element.toggleClass('selected', e.target.checked);
            });

            element.find('.play-item-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                playItemFromFolder(item, item.itemType);
            });

            element.find('.move-item-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                openMoveItemModal(item, item.itemType);
            });

            element.find('.remove-from-folder-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                removeItemFromFolder(item.id, item.itemType);
            });

            container.append(element);
        });
    }

    async function loadUnorganizedItems() {
        if (!authToken) return;

        try {
            const [audioResponse, videoResponse] = await Promise.all([
                $.ajax({
                    url: `${API_BASE_URL}/audio/list`,
                    method: 'GET',
                    headers: getAuthHeaders()
                }),
                $.ajax({
                    url: `${API_BASE_URL}/video/list-downloads`,
                    method: 'GET',
                    headers: getAuthHeaders()
                })
            ]);

            const unorganizedAudios = (audioResponse.audio_files || []).filter(a => !a.folder_id);
            const unorganizedVideos = (videoResponse.videos || []).filter(v => !v.folder_id);

            renderUnorganizedItems(unorganizedAudios, unorganizedVideos);
            $('#unorganizedItemCount').text(`${unorganizedAudios.length + unorganizedVideos.length} itens`);

        } catch (error) {
            console.error('Error loading unorganized items:', error);
        }
    }

    function renderUnorganizedItems(audios, videos) {
        const container = $('#unorganizedItemList');
        container.empty();

        const allItems = [
            ...audios.map(a => ({ ...a, itemType: 'audio' })),
            ...videos.map(v => ({ ...v, itemType: 'video' }))
        ];

        if (allItems.length === 0) {
            container.html(`
                <div class="text-center py-4 text-body-secondary">
                    <i class="bi bi-check-circle fs-1 mb-3 d-block opacity-50"></i>
                    <p class="mb-0">Todos os itens estão organizados em pastas</p>
                </div>
            `);
            return;
        }

        allItems.forEach(item => {
            const isAudio = item.itemType === 'audio';
            const icon = isAudio ? 'bi-music-note-beamed' : 'bi-camera-video';
            const badgeClass = isAudio ? 'bg-info' : 'bg-primary';
            const isSelected = selectedItems.some(s => s.id === item.id && s.type === item.itemType);

            const element = $(`
                <div class="list-group-item list-group-item-action unorganized-item ${isSelected ? 'selected' : ''}" data-id="${item.id}" data-type="${item.itemType}">
                    <div class="d-flex w-100 align-items-center">
                        <div class="form-check me-2">
                            <input class="form-check-input item-checkbox" type="checkbox" ${isSelected ? 'checked' : ''}
                                   data-id="${item.id}" data-type="${item.itemType}">
                        </div>
                        <div class="me-3">
                            <i class="bi ${icon} text-danger fs-5"></i>
                        </div>
                        <div class="flex-grow-1 min-width-0">
                            <h6 class="mb-1 text-truncate">${item.title || item.name}</h6>
                            <small class="text-body-tertiary">
                                <span class="badge ${badgeClass} me-2">${isAudio ? 'Áudio' : 'Vídeo'}</span>
                                <span><i class="bi bi-hdd me-1"></i>${formatFileSize(item.filesize)}</span>
                            </small>
                        </div>
                        <div class="ms-2 d-flex align-items-center gap-1">
                            <button class="btn btn-sm btn-success play-item-btn" data-id="${item.id}" data-type="${item.itemType}" title="Reproduzir">
                                <i class="bi bi-play-fill"></i>
                            </button>
                            <button class="btn btn-sm btn-danger move-to-folder-btn" data-id="${item.id}" data-type="${item.itemType}" title="Mover para pasta">
                                <i class="bi bi-folder-plus me-1"></i>Mover
                            </button>
                        </div>
                    </div>
                </div>
            `);

            element.find('.item-checkbox').on('change', (e) => {
                e.stopPropagation();
                toggleItemSelection(item.id, item.itemType, e.target.checked);
                element.toggleClass('selected', e.target.checked);
            });

            element.find('.play-item-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                playItemFromFolder(item, item.itemType);
            });

            element.find('.move-to-folder-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                openMoveItemModal(item, item.itemType);
            });

            container.append(element);
        });
    }

    // Folder CRUD operations
    function openCreateFolderModal() {
        $('#folderEditId').val('');
        $('#folderName').val('');
        $('#folderDescription').val('');
        $('#folderColor').val('#FFC107');
        $('#folderIcon').val('folder2');
        $('#folderModalLabel').html('<i class="bi bi-folder-plus text-warning me-2"></i>Nova Pasta');
        folderModal.show();
    }

    function openEditFolderModal(folder) {
        $('#folderEditId').val(folder.id);
        $('#folderName').val(folder.name);
        $('#folderDescription').val(folder.description || '');
        $('#folderColor').val(folder.color || '#FFC107');
        $('#folderIcon').val(folder.icon || 'folder2');
        $('#folderModalLabel').html('<i class="bi bi-pencil text-warning me-2"></i>Editar Pasta');
        folderModal.show();
    }

    async function saveFolder() {
        const folderId = $('#folderEditId').val();
        const name = $('#folderName').val().trim();
        const description = $('#folderDescription').val().trim();
        const color = $('#folderColor').val();
        const icon = $('#folderIcon').val();

        if (!name) {
            showToast('Nome da pasta é obrigatório', 'warning');
            return;
        }

        try {
            showLoading(folderId ? 'Atualizando pasta...' : 'Criando pasta...');

            const data = {
                name: name,
                description: description || null,
                color: color,
                icon: icon,
                parent_id: currentFolderId
            };

            if (folderId) {
                // Update
                await $.ajax({
                    url: `${API_BASE_URL}/folders/${folderId}`,
                    method: 'PUT',
                    headers: getAuthHeaders(),
                    data: JSON.stringify(data)
                });
                showToast('Pasta atualizada com sucesso!', 'success');
            } else {
                // Create
                await $.ajax({
                    url: `${API_BASE_URL}/folders`,
                    method: 'POST',
                    headers: getAuthHeaders(),
                    data: JSON.stringify(data)
                });
                showToast('Pasta criada com sucesso!', 'success');
            }

            hideLoading();
            folderModal.hide();
            loadFolders(currentFolderId);

        } catch (error) {
            hideLoading();
            console.error('Error saving folder:', error);
            const message = error.responseJSON?.detail || 'Erro ao salvar pasta';
            showToast(message, 'error');
        }
    }

    let pendingDeleteFolder = null;

    function confirmDeleteFolder(folder) {
        pendingDeleteFolder = folder;
        pendingDeleteItem = null;
        pendingDeleteType = 'folder';
        $('#deleteItemTitle').text(`Pasta "${folder.name}"`);
        $('#deleteModalLabel').html('<i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>Excluir Pasta');
        deleteModal.show();
    }

    async function deleteFolder(folderId) {
        if (!authToken) {
            showToast('Não autenticado', 'error');
            return;
        }

        try {
            showLoading('Excluindo pasta...');

            await $.ajax({
                url: `${API_BASE_URL}/folders/${folderId}`,
                method: 'DELETE',
                headers: getAuthHeaders()
            });

            hideLoading();
            showToast('Pasta excluída com sucesso!', 'success');
            loadFolders(currentFolderId);

        } catch (error) {
            hideLoading();
            console.error('Error deleting folder:', error);
            const message = error.responseJSON?.detail || 'Erro ao excluir pasta';
            showToast(message, 'error');
        }
    }

    // Move item functions
    async function openMoveItemModal(item, itemType) {
        // Reset to single item mode
        $('#moveBatchMode').val('false');
        $('#moveItemId').val(item.id);
        $('#moveItemType').val(itemType);
        $('#moveModalTitle').text('Mover Item');
        $('#moveItemTitle').text(item.title || item.name);
        $('#moveItemDescription').html(`Mover "<span id="moveItemTitle" class="fw-bold">${item.title || item.name}</span>" para:`);

        try {
            // Load all folders with hierarchy
            const container = $('#moveFolderList');
            container.empty();

            // Add root option
            const rootItem = $(`
                <a href="#" class="list-group-item list-group-item-action move-folder-option ${!item.folder_id ? 'active' : ''}" data-folder-id="">
                    <i class="bi bi-house me-2"></i>Raiz (sem pasta)
                </a>
            `);
            rootItem.on('click', (e) => {
                e.preventDefault();
                moveItemToFolder(null);
            });
            container.append(rootItem);

            // Load root folders and recursively load children
            await loadFoldersHierarchy(container, null, 0, item.folder_id);

            moveItemModal.show();

        } catch (error) {
            console.error('Error loading folders for move:', error);
            showToast('Erro ao carregar pastas', 'error');
        }
    }

    async function loadFoldersHierarchy(container, parentId, level, currentFolderIdOfItem) {
        try {
            const url = parentId
                ? `${API_BASE_URL}/folders/${parentId}/children`
                : `${API_BASE_URL}/folders/root`;

            const folders = await $.ajax({
                url: url,
                method: 'GET',
                headers: getAuthHeaders()
            });

            for (const folder of (folders || [])) {
                const iconClass = folder.icon || 'folder2';
                const isCurrentFolder = folder.id === currentFolderIdOfItem;
                const indent = level * 20; // 20px per level

                const item = $(`
                    <a href="#" class="list-group-item list-group-item-action move-folder-option ${isCurrentFolder ? 'active' : ''}"
                       data-folder-id="${folder.id}" style="padding-left: ${16 + indent}px;">
                        <i class="bi bi-${iconClass} me-2" style="color: ${folder.color || 'var(--bs-warning)'}"></i>
                        ${folder.name}
                        ${isCurrentFolder ? '<span class="badge bg-secondary ms-2">Atual</span>' : ''}
                    </a>
                `);
                item.on('click', (e) => {
                    e.preventDefault();
                    if (!isCurrentFolder) {
                        moveItemToFolder(folder.id);
                    }
                });
                container.append(item);

                // Recursively load children
                await loadFoldersHierarchy(container, folder.id, level + 1, currentFolderIdOfItem);
            }
        } catch (error) {
            console.error(`Error loading folders for parent ${parentId}:`, error);
        }
    }

    async function moveItemToFolder(folderId) {
        const batchMode = $('#moveBatchMode').val() === 'true';

        if (batchMode) {
            // Batch move mode
            await moveSelectedItemsToFolder(folderId);
        } else {
            // Single item mode
            const itemId = $('#moveItemId').val();
            const itemType = $('#moveItemType').val();

            if (!itemId || !itemType) return;

            try {
                showLoading('Movendo item...');

                const endpoint = itemType === 'audio'
                    ? `${API_BASE_URL}/audio/${itemId}/folder`
                    : `${API_BASE_URL}/video/${itemId}/folder`;

                await $.ajax({
                    url: endpoint,
                    method: 'PUT',
                    headers: getAuthHeaders(),
                    data: JSON.stringify({ folder_id: folderId })
                });

                hideLoading();
                moveItemModal.hide();
                showToast('Item movido com sucesso!', 'success');

                // Reload folder contents
                if (currentFolderId) {
                    loadFolderItems(currentFolderId);
                }
                loadUnorganizedItems();

            } catch (error) {
                hideLoading();
                console.error('Error moving item:', error);
                const message = error.responseJSON?.detail || 'Erro ao mover item';
                showToast(message, 'error');
            }
        }
    }

    // Selection management functions
    function toggleItemSelection(itemId, itemType, isSelected) {
        if (isSelected) {
            // Add to selection if not already present
            if (!selectedItems.some(s => s.id === itemId && s.type === itemType)) {
                selectedItems.push({ id: itemId, type: itemType });
            }
        } else {
            // Remove from selection
            selectedItems = selectedItems.filter(s => !(s.id === itemId && s.type === itemType));
        }
        updateSelectionUI();
    }

    function updateSelectionUI() {
        const count = selectedItems.length;
        $('#selectedCount').text(count);

        if (count > 0) {
            $('#moveSelectedBtn').removeClass('d-none');
            $('#clearSelectionBtn').removeClass('d-none');
        } else {
            $('#moveSelectedBtn').addClass('d-none');
            $('#clearSelectionBtn').addClass('d-none');
        }
    }

    function clearSelection() {
        selectedItems = [];
        updateSelectionUI();
        // Uncheck all checkboxes
        $('.item-checkbox').prop('checked', false);
        $('.folder-media-item, .unorganized-item').removeClass('selected');
    }

    async function openBatchMoveModal() {
        if (selectedItems.length === 0) {
            showToast('Nenhum item selecionado', 'warning');
            return;
        }

        $('#moveBatchMode').val('true');
        $('#moveItemId').val('');
        $('#moveItemType').val('');
        $('#moveModalTitle').text(`Mover ${selectedItems.length} Itens`);
        $('#moveItemDescription').html(`Mover <span class="fw-bold">${selectedItems.length} itens selecionados</span> para:`);

        try {
            const container = $('#moveFolderList');
            container.empty();

            // Add root option
            const rootItem = $(`
                <a href="#" class="list-group-item list-group-item-action move-folder-option" data-folder-id="">
                    <i class="bi bi-house me-2"></i>Raiz (sem pasta)
                </a>
            `);
            rootItem.on('click', (e) => {
                e.preventDefault();
                moveItemToFolder(null);
            });
            container.append(rootItem);

            // Load root folders and recursively load children
            await loadFoldersHierarchy(container, null, 0, null);

            moveItemModal.show();

        } catch (error) {
            console.error('Error loading folders for batch move:', error);
            showToast('Erro ao carregar pastas', 'error');
        }
    }

    async function moveSelectedItemsToFolder(folderId) {
        if (selectedItems.length === 0) return;

        try {
            showLoading(`Movendo ${selectedItems.length} itens...`);

            let successCount = 0;
            let errorCount = 0;

            for (const item of selectedItems) {
                try {
                    const endpoint = item.type === 'audio'
                        ? `${API_BASE_URL}/audio/${item.id}/folder`
                        : `${API_BASE_URL}/video/${item.id}/folder`;

                    await $.ajax({
                        url: endpoint,
                        method: 'PUT',
                        headers: getAuthHeaders(),
                        data: JSON.stringify({ folder_id: folderId })
                    });
                    successCount++;
                } catch (e) {
                    console.error(`Error moving item ${item.id}:`, e);
                    errorCount++;
                }
            }

            hideLoading();
            moveItemModal.hide();

            if (errorCount === 0) {
                showToast(`${successCount} itens movidos com sucesso!`, 'success');
            } else {
                showToast(`${successCount} movidos, ${errorCount} falharam`, 'warning');
            }

            // Clear selection and reload
            clearSelection();
            if (currentFolderId) {
                loadFolderItems(currentFolderId);
            }
            loadUnorganizedItems();

        } catch (error) {
            hideLoading();
            console.error('Error in batch move:', error);
            showToast('Erro ao mover itens', 'error');
        }
    }

    async function removeItemFromFolder(itemId, itemType) {
        try {
            showLoading('Removendo da pasta...');

            const endpoint = itemType === 'audio'
                ? `${API_BASE_URL}/audio/${itemId}/folder`
                : `${API_BASE_URL}/video/${itemId}/folder`;

            await $.ajax({
                url: endpoint,
                method: 'PUT',
                headers: getAuthHeaders(),
                data: JSON.stringify({ folder_id: null })
            });

            hideLoading();
            showToast('Item removido da pasta!', 'success');

            // Reload folder contents
            if (currentFolderId) {
                loadFolderItems(currentFolderId);
            }
            loadUnorganizedItems();

        } catch (error) {
            hideLoading();
            console.error('Error removing item from folder:', error);
            const message = error.responseJSON?.detail || 'Erro ao remover item da pasta';
            showToast(message, 'error');
        }
    }

    // Play item from folder view - switches to appropriate tab and plays
    function playItemFromFolder(item, itemType) {
        if (itemType === 'audio') {
            // Switch to audio tab
            const audioTab = document.getElementById('audio-tab');
            const tab = new bootstrap.Tab(audioTab);
            tab.show();
            // Play audio after tab switch
            setTimeout(() => {
                playAudio(item);
            }, 100);
        } else {
            // Switch to video tab
            const videoTab = document.getElementById('video-tab');
            const tab = new bootstrap.Tab(videoTab);
            tab.show();
            // Play video after tab switch
            setTimeout(() => {
                playVideo(item);
            }, 100);
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
        } else if (target === '#transcription-pane') {
            loadTranscriptionMediaList();
        } else if (target === '#folders-pane') {
            loadFolders(currentFolderId);
        }
    });

    // Folder buttons
    $('#createFolderBtn').on('click', openCreateFolderModal);
    $('#backToParentBtn').on('click', navigateBack);
    $('#refreshFoldersBtn').on('click', () => {
        loadFolders(currentFolderId);
        showToast('Lista de pastas atualizada', 'info');
    });
    $('#saveFolderBtn').on('click', saveFolder);
    $('#moveSelectedBtn').on('click', openBatchMoveModal);
    $('#clearSelectionBtn').on('click', clearSelection);

    // Transcription buttons
    $('#refreshTranscriptionListBtn').on('click', () => {
        loadTranscriptionMediaList();
        showToast('Lista de mídias atualizada', 'info');
    });

    $('#copyTranscriptionBtn').on('click', copyTranscription);
    $('#downloadTranscriptionBtn').on('click', downloadTranscription);
    $('#deleteTranscriptionBtn').on('click', () => {
        if (currentTranscriptionId) {
            confirmDeleteTranscription(currentTranscriptionId, $('#currentTranscriptionTitle').text());
        }
    });
    $('#modalCopyTranscriptionBtn').on('click', copyTranscription);
    $('#modalDownloadTranscriptionBtn').on('click', downloadTranscription);

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
