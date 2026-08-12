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
    let currentTranscriptionMedia = [];
    let transcriptionSearchMode = 'title';
    let lastTranscriptionSearchTerm = '';

    // Folder state
    let currentFolders = [];
    let currentFolderId = null;  // null = root folder
    let folderPath = [];  // breadcrumb path
    let selectedItems = [];  // {id, type} - itens selecionados para mover em lote

    // Album player state
    let currentAlbums = [];
    let currentAlbum = null;
    let albumQueue = [];
    let queueIndex = -1;
    let albumRepeatMode = 'off'; // off | all | one
    let albumShuffle = false;
    let albumSeeking = false;

    // ========================================
    // Theme Toggle
    // ========================================
    function initTheme() {
        const saved = localStorage.getItem('yd-theme');
        const theme = saved || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
        applyTheme(theme);
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        document.documentElement.setAttribute('data-bs-theme', theme);
        localStorage.setItem('yd-theme', theme);
        updateThemeToggleIcon(theme);
    }

    function updateThemeToggleIcon(theme) {
        const icon = $('#themeToggle .bi');
        if (theme === 'dark') {
            icon.removeClass('bi-sun-fill').addClass('bi-moon-fill');
        } else {
            icon.removeClass('bi-moon-fill').addClass('bi-sun-fill');
        }
    }

    $('#themeToggle').on('click', function() {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        applyTheme(next);
    });

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
        if (!localStorage.getItem('yd-theme')) {
            applyTheme(e.matches ? 'dark' : 'light');
        }
    });

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

        const toastTypeClass = `toast--${type}`;

        // Remove previous type classes
        $(toastEl).removeClass('toast--success toast--error toast--warning toast--info').addClass(toastTypeClass);

        $('#toastIcon').attr('class', `bi ${iconMap[type]} me-2`);
        $('#toastTitle').text(type === 'error' ? 'Erro' : type === 'success' ? 'Sucesso' : type === 'warning' ? 'Atenção' : 'Informação');
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

    function escapeHtml(text) {
        if (text === null || text === undefined) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function copyPathToClipboard(path) {
        if (!path) {
            showToast('Caminho indisponível', 'warning');
            return;
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(path).then(() => {
                showToast('Caminho copiado', 'success');
            }).catch(() => {
                showToast('Falha ao copiar caminho', 'error');
            });
        } else {
            const ta = document.createElement('textarea');
            ta.value = path;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            try {
                document.execCommand('copy');
                showToast('Caminho copiado', 'success');
            } catch (_) {
                showToast('Falha ao copiar caminho', 'error');
            }
            document.body.removeChild(ta);
        }
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

    function validateVideoUrl(url) {
        if (!url) return false;
        return (
            url.includes('youtube.com/') ||
            url.includes('youtu.be/') ||
            url.includes('instagram.com/')
        );
    }

    // Backward-compat alias — remove in a future cleanup pass.
    function validateYouTubeUrl(url) {
        return validateVideoUrl(url);
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
            if (searchTerm) {
                container.html(`
                    <div class="yd-empty-state">
                        <i class="bi bi-search yd-empty-state__icon"></i>
                        <p class="yd-empty-state__title">Nenhum resultado para "${escapeHtml(searchTerm)}"</p>
                        <p class="yd-empty-state__desc">Tente outra palavra ou limpe a busca.</p>
                        <button type="button" class="btn btn-sm btn-outline-secondary mt-2" data-clear-target="#searchAudioInput">
                            <i class="bi bi-x-lg me-1"></i>Limpar busca
                        </button>
                    </div>
                `);
                container.find('[data-clear-target]').on('click', () => {
                    $('#searchAudioInput').val('').trigger('input');
                });
                return;
            }
            container.html(`
                <div class="yd-empty-state">
                    <i class="bi bi-music-note-beamed yd-empty-state__icon"></i>
                    <p class="yd-empty-state__title">Nenhum áudio encontrado</p>
                    <p class="yd-empty-state__desc">Faça o download de um áudio na aba Download</p>
                </div>
            `);
            return;
        }

        audios.forEach(audio => {
            const isActive = audio.id === currentAudioId;
            const statusBadge = getStatusBadge(audio.download_status, audio.id);

            const item = $(`
                <a href="#" class="yd-media-item ${isActive ? 'active' : ''}"
                   data-id="${audio.id}">
                    <div class="d-flex w-100 align-items-center">
                        <div class="me-3">
                            <div class="yd-media-thumb yd-media-thumb--audio">
                                <i class="bi bi-music-note-beamed"></i>
                            </div>
                        </div>
                        <div class="flex-grow-1 min-width-0">
                            <h6 class="yd-media-title text-truncate">${highlightText(audio.title || audio.name, searchTerm)}</h6>
                            <div class="yd-media-meta">
                                <span class="me-3"><i class="bi bi-hdd me-1"></i>${formatFileSize(audio.filesize)}</span>
                                <span><i class="bi bi-calendar me-1"></i>${formatDate(audio.modified_date)}</span>
                            </div>
                            <div class="yd-media-path text-truncate font-monospace mt-1" title="${escapeHtml(audio.path || '')}">
                                <i class="bi bi-folder2-open me-1"></i><span class="yd-media-path__text">${escapeHtml(audio.path || '(sem caminho registrado)')}</span>
                                ${audio.path ? `<button type="button" class="btn btn-link p-0 ms-1 align-baseline copy-path-btn" data-path="${escapeHtml(audio.path)}" title="Copiar caminho"><i class="bi bi-clipboard"></i></button>` : ''}
                            </div>
                        </div>
                        <div class="ms-2 yd-action-group">
                            ${statusBadge}
                            <button class="btn btn-sm btn-danger yd-action-btn play-audio-btn" data-id="${audio.id}" title="Reproduzir">
                                <i class="bi bi-play-fill"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger yd-action-btn delete-audio-btn" data-id="${audio.id}" title="Excluir">
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

            item.find('.copy-path-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                copyPathToClipboard(audio.path);
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
            $('.yd-media-item').removeClass('active');
            $(`.yd-media-item[data-id="${audio.id}"]`).addClass('active');

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
            if (searchTerm) {
                container.html(`
                    <div class="yd-empty-state">
                        <i class="bi bi-search yd-empty-state__icon"></i>
                        <p class="yd-empty-state__title">Nenhum resultado para "${escapeHtml(searchTerm)}"</p>
                        <p class="yd-empty-state__desc">Tente outra palavra ou limpe a busca.</p>
                        <button type="button" class="btn btn-sm btn-outline-secondary mt-2" data-clear-target="#searchVideoInput">
                            <i class="bi bi-x-lg me-1"></i>Limpar busca
                        </button>
                    </div>
                `);
                container.find('[data-clear-target]').on('click', () => {
                    $('#searchVideoInput').val('').trigger('input');
                });
                return;
            }
            container.html(`
                <div class="yd-empty-state">
                    <i class="bi bi-camera-video yd-empty-state__icon"></i>
                    <p class="yd-empty-state__title">Nenhum vídeo encontrado</p>
                    <p class="yd-empty-state__desc">Faça o download de um vídeo na aba Download</p>
                </div>
            `);
            return;
        }

        videos.forEach(video => {
            const isActive = video.id === currentVideoId;
            const statusBadge = getStatusBadge(video.download_status, video.id);

            const item = $(`
                <a href="#" class="yd-media-item ${isActive ? 'active' : ''}"
                   data-id="${video.id}">
                    <div class="d-flex w-100 align-items-center">
                        <div class="me-3">
                            <div class="yd-media-thumb yd-media-thumb--video">
                                <i class="bi bi-camera-video"></i>
                            </div>
                        </div>
                        <div class="flex-grow-1 min-width-0">
                            <h6 class="yd-media-title text-truncate">${highlightText(video.title || video.name, searchTerm)}</h6>
                            <div class="yd-media-meta">
                                <span class="me-3"><i class="bi bi-hdd me-1"></i>${formatFileSize(video.filesize)}</span>
                                <span class="me-3"><i class="bi bi-aspect-ratio me-1"></i>${video.resolution || '-'}</span>
                                <span><i class="bi bi-clock me-1"></i>${formatDuration(video.duration)}</span>
                            </div>
                            <div class="yd-media-path text-truncate font-monospace mt-1" title="${escapeHtml(video.path || '')}">
                                <i class="bi bi-folder2-open me-1"></i><span class="yd-media-path__text">${escapeHtml(video.path || '(sem caminho registrado)')}</span>
                                ${video.path ? `<button type="button" class="btn btn-link p-0 ms-1 align-baseline copy-path-btn" data-path="${escapeHtml(video.path)}" title="Copiar caminho"><i class="bi bi-clipboard"></i></button>` : ''}
                            </div>
                        </div>
                        <div class="ms-2 yd-action-group">
                            ${statusBadge}
                            <button class="btn btn-sm btn-danger yd-action-btn play-video-btn" data-id="${video.id}"
                                    ${video.download_status !== 'ready' ? 'disabled' : ''} title="Reproduzir">
                                <i class="bi bi-play-fill"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger yd-action-btn delete-video-btn" data-id="${video.id}" title="Excluir">
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

            item.find('.copy-path-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                copyPathToClipboard(video.path);
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
            $('.yd-media-item').removeClass('active');
            $(`.yd-media-item[data-id="${video.id}"]`).addClass('active');

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
    // URL é playlist quando contém `list=` E NÃO contém `v=`.
    // URLs com ambos (watch?v=...&list=...) são vídeo único.
    function isPlaylistUrl(url) {
        try {
            const params = new URL(url).searchParams;
            return params.has('list') && !params.has('v');
        } catch (_) {
            return false;
        }
    }

    async function downloadAudio() {
        const url = $('#audioUrl').val().trim();
        const highQuality = $('#highQuality').is(':checked');

        if (!validateYouTubeUrl(url)) {
            showToast('Por favor, insira uma URL válida do YouTube ou Instagram', 'warning');
            return;
        }

        if (!authToken) {
            showToast('Não autenticado', 'error');
            return;
        }

        if (isPlaylistUrl(url)) {
            await downloadAudioPlaylist(url, highQuality);
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

    async function downloadAudioPlaylist(url, highQuality) {
        try {
            showLoading('Enfileirando playlist de áudio...');

            // PlaylistDownloadRequest (app/models/audio.py): url, high_quality.
            // skip_existing tem default no backend (True) e não há controle na UI — omitido.
            const response = await $.ajax({
                url: `${API_BASE_URL}/audio/playlist`,
                method: 'POST',
                headers: getAuthHeaders(),
                data: JSON.stringify({
                    url: url,
                    high_quality: highQuality
                })
            });

            hideLoading();

            // PlaylistDownloadResponse: playlist_title, total_items, queued_items, skipped_items, tasks[]
            const tasks = response.tasks || [];
            const queued = response.queued_items || 0;

            tasks.forEach((task) => {
                // Pular itens já existentes ou sem registro no DB.
                if (task.skipped || !task.item_id) {
                    return;
                }
                addActiveDownload(task.item_id, 'audio', task.title || 'Áudio');
                pollDownloadStatus(task.item_id, 'audio');
            });

            const folderId = response.folder_id;
            showToast(`Playlist enfileirada para download (${queued} itens)`, 'success');
            $('#audioUrl').val('');

            if (folderId && window.confirm('Abrir o álbum na aba Álbuns?')) {
                openAlbumById(folderId, { autoplay: false });
            }

        } catch (error) {
            hideLoading();
            console.error('Error downloading audio playlist:', error);
            const message = error.responseJSON?.detail || 'Erro ao enfileirar playlist';
            showToast(message, 'error');
        }
    }

    async function downloadVideo() {
        const url = $('#videoUrl').val().trim();
        const resolution = $('#videoResolution').val();

        if (!validateYouTubeUrl(url)) {
            showToast('Por favor, insira uma URL válida do YouTube ou Instagram', 'warning');
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

    function buildRingProgress(progress, status) {
        const p = Math.min(100, Math.max(0, progress));
        let fillClass = '';
        if (status === 'error')   fillClass = 'yd-ring__fill--error';
        else if (p >= 100)        fillClass = 'yd-ring__fill--success';
        else if (p >= 95)         fillClass = 'yd-ring__fill--converting';
        const label = p >= 100 ? '✓' : `${p}%`;
        // r=15.9 → circunferência ≈ 100, então stroke-dasharray usa o próprio percentual
        return `<div class="yd-ring-progress" title="${p}%">
                    <svg class="yd-ring" viewBox="0 0 36 36">
                        <circle class="yd-ring__track" cx="18" cy="18" r="15.9" stroke-width="2.5"/>
                        <circle class="yd-ring__fill ${fillClass}" cx="18" cy="18" r="15.9"
                                stroke-width="2.5"
                                stroke-dasharray="${p} 100"
                                transform="rotate(-90 18 18)"/>
                    </svg>
                    <span class="yd-ring__text">${label}</span>
                </div>`;
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

            let statusLabel = 'Baixando...';
            let statusIcon = 'bi-arrow-down-circle';
            let fillClass = 'yd-progress-bar__fill--active';
            if (download.progress >= 95 && download.progress < 100) {
                statusLabel = 'Convertendo...';
                statusIcon = 'bi-gear';
            } else if (download.progress >= 100) {
                statusLabel = 'Concluído';
                statusIcon = 'bi-check-circle';
                fillClass = 'yd-progress-bar__fill--success';
            }

            if (download.status === 'error') {
                statusLabel = 'Erro';
                statusIcon = 'bi-x-circle';
                fillClass = 'yd-progress-bar__fill--error';
            }

            const progressItem = $(`
                <div class="yd-download-item" data-download-id="${id}">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="d-flex align-items-center gap-2">
                            <i class="bi ${icon}" style="color: var(--yd-accent-primary)"></i>
                            <span class="text-truncate yd-media-title" style="max-width: 300px;">${download.title}</span>
                        </span>
                        <span class="d-flex align-items-center gap-2">
                            <span class="yd-badge yd-badge--pending"><i class="bi ${statusIcon} me-1"></i>${statusLabel}</span>
                            ${buildRingProgress(download.progress, download.status)}
                        </span>
                    </div>
                    <div class="yd-progress-bar">
                        <div class="yd-progress-bar__fill ${fillClass}"
                             style="width: ${download.progress}%"></div>
                    </div>
                </div>
            `);

            container.append(progressItem);
        });

        // Atualiza o anel nos itens da lista de áudio/vídeo in-place
        activeDownloads.forEach((download, id) => {
            const badge = $(`[data-badge-id="${id}"]`);
            if (badge.length) {
                badge.html(buildRingProgress(download.progress, download.status));
            }
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
            showToast(formatDeleteError(error, 'áudio'), 'error');
        }
    }

    function formatDeleteError(error, entity) {
        if (error?.responseJSON?.detail) return error.responseJSON.detail;
        if (error?.status === 0 || error?.readyState === 0) {
            return `Servidor não respondeu. Verifique se o backend está rodando em ${API_BASE_URL}.`;
        }
        if (error?.statusText === 'timeout') {
            return `Tempo esgotado ao excluir ${entity}. Tente novamente.`;
        }
        if (error?.status >= 500) {
            return `Erro interno ao excluir ${entity} (HTTP ${error.status}). Veja os logs do servidor.`;
        }
        return `Erro ao excluir ${entity}`;
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
            showToast(formatDeleteError(error, 'vídeo'), 'error');
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

            currentTranscriptionMedia = allMedia;
            // Reaplica a busca atual (se houver) sobre a lista recém-carregada.
            applyTranscriptionSearch();

            // (Re)inicia o poller global se a lista recém-renderizada tiver
            // itens ativos (queued/started). Singleton: limpa timer anterior.
            startTranscriptionStatusPoller();

        } catch (error) {
            console.error('Error loading transcription media list:', error);
            if (error.status === 401) {
                authenticate();
            } else {
                currentTranscriptionMedia = [];
                renderTranscriptionMediaList([]);
                showToast('Erro ao carregar lista de mídias', 'error');
            }
        }
    }

    function renderTranscriptionMediaList(mediaList, searchTerm = '', snippetsByFileId = null, useCompositeKey = false) {
        const container = $('#transcriptionMediaList');
        container.empty();

        if (mediaList.length === 0) {
            if (searchTerm) {
                container.html(`
                    <div class="yd-empty-state">
                        <i class="bi bi-search yd-empty-state__icon"></i>
                        <p class="yd-empty-state__title">Nenhum resultado para "${escapeHtml(searchTerm)}"</p>
                        <p class="yd-empty-state__desc">Tente outra palavra ou alterne o modo de busca (Título/Conteúdo).</p>
                        <button type="button" class="btn btn-sm btn-outline-secondary mt-2" id="clearTranscriptionSearchInline">
                            <i class="bi bi-x-lg me-1"></i>Limpar busca
                        </button>
                    </div>
                `);
                container.find('#clearTranscriptionSearchInline').on('click', () => {
                    $('#searchTranscriptionInput').val('').trigger('input');
                });
                return;
            }
            container.html(`
                <div class="yd-empty-state">
                    <i class="bi bi-collection yd-empty-state__icon"></i>
                    <p class="yd-empty-state__title">Nenhuma mídia encontrada</p>
                    <p class="yd-empty-state__desc">Faça downloads para que eles apareçam aqui</p>
                </div>
            `);
            return;
        }

        mediaList.forEach(media => {
            const isAudio = media.mediaType === 'audio';
            const icon = isAudio ? 'bi-music-note-beamed' : 'bi-camera-video';
            const typeBadge = isAudio ?
                '<span class="yd-badge yd-badge--audio"><i class="bi bi-music-note me-1"></i>Áudio</span>' :
                '<span class="yd-badge yd-badge--video"><i class="bi bi-camera-video me-1"></i>Vídeo</span>';

            const transcriptionStatus = getTranscriptionStatusBadge(media.transcription_status);
            const thumbClass = isAudio ? 'yd-media-thumb--audio' : 'yd-media-thumb--video';
            const titleHtml = searchTerm
                ? highlightText(media.title || media.name || '', searchTerm)
                : (media.title || media.name || '');
            const snippetKey = useCompositeKey ? `${media.id}|${media.mediaType}` : media.id;
            const snippetData = snippetsByFileId ? snippetsByFileId[snippetKey] : null;
            const snippetHtml = snippetData
                ? `<div class="yd-search-snippet" title="Trecho com a ocorrência (${snippetData.match_count} match${snippetData.match_count > 1 ? 'es' : ''})">${snippetData.snippet}</div>`
                : '';

            const playLabel = media.mediaType === 'audio' ? 'Reproduzir áudio' : 'Reproduzir vídeo';
            const item = $(`
                <div class="yd-media-item yd-clickable" data-id="${media.id}" data-type="${media.mediaType}" role="button" tabindex="0" title="${playLabel}">
                    <div class="d-flex w-100 align-items-center">
                        <div class="me-3">
                            <div class="yd-media-thumb ${thumbClass}">
                                <i class="bi ${icon}"></i>
                            </div>
                        </div>
                        <div class="flex-grow-1 min-width-0">
                            <h6 class="yd-media-title text-truncate">${titleHtml}</h6>
                            <div class="yd-media-meta">
                                ${typeBadge}
                                <span class="ms-2"><i class="bi bi-hdd me-1"></i>${formatFileSize(media.filesize)}</span>
                                <span class="ms-2"><i class="bi bi-calendar me-1"></i>${formatDate(media.modified_date)}</span>
                            </div>
                            ${snippetHtml}
                        </div>
                        <div class="ms-2 yd-action-group">
                            ${transcriptionStatus}
                            <button class="btn btn-sm btn-outline-info yd-action-btn view-transcription-btn" data-id="${media.id}"
                                    title="Ver Transcrição" ${media.transcription_status !== 'ended' ? 'disabled' : ''}>
                                <i class="bi bi-eye"></i>
                            </button>
                            <button class="btn btn-sm btn-danger yd-action-btn start-transcription-btn" data-id="${media.id}"
                                    title="Transcrever" ${media.transcription_status === 'started' || media.transcription_status === 'queued' ? 'disabled' : ''}>
                                <i class="bi bi-file-text"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger yd-action-btn delete-transcription-btn" data-id="${media.id}"
                                    title="${media.transcription_status === 'started' || media.transcription_status === 'queued' ? 'Cancelar Transcrição' : 'Excluir Transcrição'}"
                                    ${media.transcription_status === 'none' ? 'disabled' : ''}>
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
                confirmDeleteTranscription(media.id, media.title || media.name, media.transcription_status);
            });

            // Click no body do item → troca para a aba correspondente e reproduz.
            // Cliques nas action-buttons (acima) usam stopPropagation, então não disparam aqui.
            const triggerPlay = (e) => {
                if (e.target.closest('.yd-action-group')) return;
                e.preventDefault();
                playFromTranscriptionItem(media);
            };
            item.on('click', triggerPlay);
            item.on('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    triggerPlay(e);
                }
            });

            container.append(item);
        });
    }

    function getTranscriptionStatusBadge(status) {
        const badges = {
            'ended': '<span class="yd-badge yd-badge--transcribed"><i class="bi bi-check-circle me-1"></i>Transcrito</span>',
            'queued': '<span class="yd-badge yd-badge--processing"><i class="bi bi-clock-history me-1"></i>Aguardando</span>',
            'started': '<span class="yd-badge yd-badge--processing"><i class="bi bi-hourglass-split me-1"></i>Em andamento</span>',
            'error': '<span class="yd-badge yd-badge--error"><i class="bi bi-x-circle me-1"></i>Erro</span>',
            'none': '<span class="yd-badge yd-badge--not-transcribed"><i class="bi bi-dash-circle me-1"></i>Não transcrito</span>'
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

        // Enfileiramento otimista e NÃO-bloqueante: marca o item como "Aguardando"
        // e desabilita seu botão imediatamente, sem abrir o modal de loading e sem
        // recarregar a lista inteira. O modal cobria a tela e o reload recriava
        // todo o DOM a cada clique, fazendo o botão seguinte "sumir" — o que
        // impedia enfileirar vários itens em sequência. Agora dá para clicar em
        // vários rapidamente; cada um vira "Aguardando" e drena conforme a fila.
        const $btn = $(`.start-transcription-btn[data-id="${fileId}"]`);
        const $group = $btn.closest('.yd-action-group');
        $btn.prop('disabled', true);

        try {
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

            if (response.status === 'processing' || response.status === 'success') {
                // Feedback visual imediato no próprio item (sem re-render global).
                $group.find('.yd-badge').replaceWith(getTranscriptionStatusBadge('queued'));
                // Mantém o cache em dia para sobreviver a re-renders (busca/aba).
                // Tipo vem da própria linha (vídeos também têm botão "Transcrever").
                const mediaType = $btn.closest('.yd-media-item').attr('data-type') || 'audio';
                updateCachedTranscriptionStatus(fileId, mediaType, 'queued');
                showToast('Adicionado à fila de transcrição.', 'success');
                // Poller GLOBAL cuida das transições seguintes (Aguardando→Em
                // andamento→Transcrito) in-place, para todos os itens ativos.
                startTranscriptionStatusPoller();
            } else if (response.message && response.message.includes('já existe')) {
                $btn.prop('disabled', false);
                showToast('Transcrição já existe para este arquivo.', 'info');
                viewTranscription(fileId);
            } else {
                showToast(response.message || 'Adicionado à fila', 'info');
            }

        } catch (error) {
            $btn.prop('disabled', false);
            console.error('Error starting transcription:', error);
            const message = error.responseJSON?.detail || 'Erro ao iniciar transcrição';
            showToast(message, 'error');
        }
    }

    // ========================================
    // Poller GLOBAL de status de transcrição
    // ========================================
    // Substitui o antigo polling POR ITEM (pollTranscriptionStatus). Em vez de
    // um timer por arquivo clicado e um re-render completo ao concluir, mantemos
    // UM único timer que, a cada ~4s, busca o status de TODOS os itens (áudios +
    // vídeos, pois a aba mistura os dois) e aplica o resultado IN-PLACE em cada
    // linha já renderizada — sem recriar o DOM, sem piscar e sem perder o scroll.
    const TRANSCRIPTION_POLL_INTERVAL_MS = 4000;
    const ACTIVE_TRANSCRIPTION_STATUSES = ['queued', 'started'];
    let transcriptionPollTimer = null;

    // Há alguma linha renderizada em estado ativo (Aguardando/Em andamento)?
    // É o gatilho para iniciar e a condição de parada do poller.
    function hasActiveTranscriptionRows() {
        let active = false;
        $('#transcriptionMediaList .yd-media-item[data-id]').each(function () {
            const $row = $(this);
            const $start = $row.find('.start-transcription-btn');
            const $view = $row.find('.view-transcription-btn');
            // Estado ativo = botão "Transcrever" desabilitado e "Ver" desabilitado.
            // (queued/started desabilitam Transcrever; ended habilita Ver.)
            if ($start.prop('disabled') && $view.prop('disabled')) {
                active = true;
                return false; // break
            }
        });
        return active;
    }

    // Aplica o novo status numa linha específica (DOM + modelo em cache), sem
    // re-render. Espelha exatamente o que renderTranscriptionMediaList produz
    // (linhas ~1170-1183), para que linhas "patcheadas" não divirjam das recém
    // renderizadas após uma busca/re-render.
    function patchTranscriptionRow($row, newStatus) {
        const isActive = ACTIVE_TRANSCRIPTION_STATUSES.includes(newStatus);

        // Badge de status (único .yd-badge dentro do .yd-action-group; o badge
        // de tipo Áudio/Vídeo fica em .yd-media-meta). Mesmo seletor de startTranscription.
        $row.find('.yd-action-group .yd-badge').first()
            .replaceWith(getTranscriptionStatusBadge(newStatus));

        // Botão "Transcrever": desabilitado enquanto queued/started.
        $row.find('.start-transcription-btn').prop('disabled', isActive);

        // Botão "Ver Transcrição": habilitado apenas quando ended.
        $row.find('.view-transcription-btn').prop('disabled', newStatus !== 'ended');

        // Botão "Excluir/Cancelar": desabilitado quando none; título conforme estado.
        $row.find('.delete-transcription-btn')
            .prop('disabled', newStatus === 'none')
            .attr('title', isActive ? 'Cancelar Transcrição' : 'Excluir Transcrição');
    }

    // Localiza no cache (currentTranscriptionMedia) o item correspondente à linha,
    // casando por id + tipo (áudio/vídeo podem compartilhar id entre as listas).
    function updateCachedTranscriptionStatus(id, mediaType, newStatus) {
        const entry = currentTranscriptionMedia.find(
            m => String(m.id) === String(id) && m.mediaType === mediaType
        );
        if (entry) {
            entry.transcription_status = newStatus;
        }
    }

    async function pollTranscriptionStatusTick() {
        if (!authToken) {
            stopTranscriptionStatusPoller();
            return;
        }

        // Só vale a pena buscar se ainda houver itens ativos visíveis.
        if (!hasActiveTranscriptionRows()) {
            stopTranscriptionStatusPoller();
            return;
        }

        try {
            const [audioResponse, videoResponse] = await Promise.all([
                $.ajax({ url: `${API_BASE_URL}/audio/list`, method: 'GET', headers: getAuthHeaders() }),
                $.ajax({ url: `${API_BASE_URL}/video/list-downloads`, method: 'GET', headers: getAuthHeaders() })
            ]);

            // Mapa id|tipo -> status, a partir de ambas as listas.
            const statusByKey = {};
            (audioResponse.audio_files || []).forEach(a => {
                statusByKey[`${a.id}|audio`] = a.transcription_status;
            });
            (videoResponse.videos || []).forEach(v => {
                statusByKey[`${v.id}|video`] = v.transcription_status;
            });

            // Patcha cada linha já renderizada cujo status mudou.
            $('#transcriptionMediaList .yd-media-item[data-id]').each(function () {
                const $row = $(this);
                const id = $row.attr('data-id');
                const mediaType = $row.attr('data-type');
                const newStatus = statusByKey[`${id}|${mediaType}`];
                if (newStatus === undefined) return;

                // Compara contra o status REAL anterior guardado no cache. O DOM
                // dos botões não distingue queued de started (ambos só desabilitam
                // "Transcrever"), então usar o cache é o que permite a transição
                // Aguardando→Em andamento aparecer. Após o patch, o cache fica
                // igual ao servidor → ticks seguintes não repetem toast/patch.
                const entry = currentTranscriptionMedia.find(
                    m => String(m.id) === String(id) && m.mediaType === mediaType
                );
                const prevStatus = entry ? entry.transcription_status : undefined;

                if (newStatus !== prevStatus) {
                    patchTranscriptionRow($row, newStatus);
                    updateCachedTranscriptionStatus(id, mediaType, newStatus);
                    if (newStatus === 'ended') {
                        showToast('Transcrição concluída!', 'success');
                    } else if (newStatus === 'error') {
                        showToast('Erro na transcrição', 'error');
                    }
                }
            });

            // Se nada mais estiver ativo, encerra o ciclo.
            if (!hasActiveTranscriptionRows()) {
                stopTranscriptionStatusPoller();
            }

        } catch (error) {
            console.error('Error polling transcription status:', error);
            if (error.status === 401) {
                stopTranscriptionStatusPoller();
            }
        }
    }

    // Singleton: limpa qualquer timer anterior antes de (re)iniciar.
    function startTranscriptionStatusPoller() {
        stopTranscriptionStatusPoller();
        if (!authToken || !hasActiveTranscriptionRows()) return;
        transcriptionPollTimer = setInterval(pollTranscriptionStatusTick, TRANSCRIPTION_POLL_INTERVAL_MS);
    }

    function stopTranscriptionStatusPoller() {
        if (transcriptionPollTimer !== null) {
            clearInterval(transcriptionPollTimer);
            transcriptionPollTimer = null;
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

    function confirmDeleteTranscription(fileId, title, status) {
        pendingDeleteTranscriptionId = fileId;
        pendingDeleteTranscriptionTitle = title;
        const isCancel = status === 'started';
        const label = isCancel ? 'Cancelar Transcrição' : 'Excluir Transcrição';
        $('#deleteItemTitle').text(`Transcrição de "${title}"`);
        $('#deleteModalLabel').html(`<i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>${label}`);
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
                    <div class="yd-empty-state">
                        <i class="bi bi-file-text yd-empty-state__icon"></i>
                        <p class="yd-empty-state__title">Nenhuma transcrição carregada</p>
                        <p class="yd-empty-state__desc">Selecione um áudio ou vídeo e clique em "Transcrever" para gerar a transcrição.</p>
                    </div>
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
    // Album / music player
    // ========================================
    function escapeHtml(str) {
        return String(str == null ? '' : str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function formatAlbumTime(seconds) {
        if (!isFinite(seconds) || seconds < 0) return '0:00';
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m}:${s.toString().padStart(2, '0')}`;
    }

    function albumCoverUrl(album, tracks) {
        if (album && album.cover_url) return album.cover_url;
        const first = (tracks || []).find(t => t.youtube_id) || (tracks || [])[0];
        if (first && first.youtube_id) {
            return `https://i.ytimg.com/vi/${first.youtube_id}/hqdefault.jpg`;
        }
        return null;
    }

    function setCoverElement($el, url) {
        if (url) {
            $el.css('background-image', `url("${url}")`).empty();
        } else {
            $el.css('background-image', 'none').html('<i class="bi bi-music-note-beamed"></i>');
        }
    }

    function showAlbumsLibrary() {
        $('#albumsDetailView').addClass('d-none');
        $('#albumsLibraryView').removeClass('d-none');
        currentAlbum = null;
        $('#searchAlbumTracksInput').val('');
        syncClearButton(document.getElementById('searchAlbumTracksInput'));
    }

    function showAlbumDetail() {
        $('#albumsLibraryView').addClass('d-none');
        $('#albumsDetailView').removeClass('d-none');
        // Reset track search when opening a new album view
        $('#searchAlbumTracksInput').val('');
        const trackSearch = document.getElementById('searchAlbumTracksInput');
        if (trackSearch) syncClearButton(trackSearch);
        if (currentAlbum) {
            applyAlbumTrackSearch('');
        }
    }

    function switchToAlbumsTab() {
        const tab = document.getElementById('albums-tab');
        if (tab) {
            bootstrap.Tab.getOrCreateInstance(tab).show();
        }
    }

    async function loadAlbums() {
        if (!authToken) {
            await authenticate();
            return;
        }
        try {
            const response = await $.ajax({
                url: `${API_BASE_URL}/albums`,
                method: 'GET',
                headers: getAuthHeaders()
            });
            currentAlbums = response || [];
            applyAlbumSearch($('#searchAlbumsInput').val() || '');
        } catch (error) {
            console.error('Error loading albums:', error);
            if (error.status === 401) {
                authenticate();
            } else {
                currentAlbums = [];
                applyAlbumSearch($('#searchAlbumsInput').val() || '');
            }
        }
    }

    function applyAlbumSearch(searchTerm) {
        const term = (searchTerm || '').trim().toLowerCase();
        if (!term) {
            renderAlbumGrid(currentAlbums);
            return;
        }
        const filtered = currentAlbums.filter(album => {
            const fields = [
                album.name,
                album.artist,
                album.source_url,
                album.external_playlist_id,
                album.description,
            ];
            return fields.some(
                value => typeof value === 'string' && value.toLowerCase().includes(term)
            );
        });
        renderAlbumGrid(filtered, searchTerm);
    }

    function renderAlbumGrid(albums, searchTerm = '') {
        const container = $('#albumGrid');
        container.empty();

        if (!albums.length) {
            if (searchTerm) {
                container.html(`
                    <div class="yd-empty-state" style="grid-column: 1 / -1;">
                        <i class="bi bi-search yd-empty-state__icon"></i>
                        <p class="yd-empty-state__title">Nenhum resultado para "${escapeHtml(searchTerm)}"</p>
                        <p class="yd-empty-state__desc">Tente outra palavra ou limpe a busca.</p>
                        <button type="button" class="btn btn-sm btn-outline-secondary mt-2" data-clear-target="#searchAlbumsInput">
                            <i class="bi bi-x-lg me-1"></i>Limpar busca
                        </button>
                    </div>
                `);
                container.find('[data-clear-target]').on('click', () => {
                    $('#searchAlbumsInput').val('').trigger('input');
                });
                return;
            }
            container.html(`
                <div class="yd-empty-state" style="grid-column: 1 / -1;">
                    <i class="bi bi-disc yd-empty-state__icon"></i>
                    <p class="yd-empty-state__title">Nenhum álbum ainda</p>
                    <p class="yd-empty-state__desc">Baixe uma playlist de áudio para criar um álbum</p>
                </div>
            `);
            return;
        }

        albums.forEach(album => {
            const cover = albumCoverUrl(album);
            const artist = album.artist || 'Vários';
            const tracks = album.track_count || 0;
            const titleHtml = searchTerm
                ? highlightText(album.name || '', searchTerm)
                : escapeHtml(album.name || '');
            const artistHtml = searchTerm
                ? highlightText(artist, searchTerm)
                : escapeHtml(artist);
            const card = $(`
                <button type="button" class="yd-album-card" data-id="${escapeHtml(album.id)}">
                    <div class="yd-album-cover yd-album-cover--card"></div>
                    <div class="yd-album-card__title" title="${escapeHtml(album.name)}">${titleHtml}</div>
                    <p class="yd-album-card__artist">${artistHtml}</p>
                    <p class="yd-album-card__meta">${tracks} faixa${tracks === 1 ? '' : 's'}</p>
                </button>
            `);
            setCoverElement(card.find('.yd-album-cover'), cover);
            card.on('click', () => openAlbumById(album.id));
            container.append(card);
        });
    }

    async function openAlbumById(folderId, opts = {}) {
        const { autoplay = false } = opts;
        if (!authToken) {
            await authenticate();
            return;
        }
        switchToAlbumsTab();
        try {
            const album = await $.ajax({
                url: `${API_BASE_URL}/albums/${folderId}`,
                method: 'GET',
                headers: getAuthHeaders()
            });
            currentAlbum = album;
            renderAlbumDetail(album);
            showAlbumDetail();
            if (autoplay) {
                playAlbumAll();
            }
        } catch (error) {
            console.error('Error opening album:', error);
            if (error.status === 401) {
                authenticate();
            } else if (error.status === 404) {
                // Pasta legada ainda não marcada como album: tenta itens da pasta
                try {
                    const items = await $.ajax({
                        url: `${API_BASE_URL}/folders/${folderId}/items`,
                        method: 'GET',
                        headers: getAuthHeaders()
                    });
                    const folder = await $.ajax({
                        url: `${API_BASE_URL}/folders/${folderId}`,
                        method: 'GET',
                        headers: getAuthHeaders()
                    });
                    currentAlbum = {
                        ...folder,
                        tracks: items.audios || [],
                        track_count: (items.audios || []).length,
                        ready_count: (items.audios || []).filter(a => a.download_status === 'ready').length
                    };
                    renderAlbumDetail(currentAlbum);
                    showAlbumDetail();
                    if (autoplay) playAlbumAll();
                } catch (e2) {
                    showToast('Álbum não encontrado', 'error');
                }
            } else {
                showToast('Erro ao abrir álbum', 'error');
            }
        }
    }

    function renderAlbumDetail(album) {
        const tracks = album.tracks || [];
        const cover = albumCoverUrl(album, tracks);
        const artist = album.artist || 'Vários';
        const ready = album.ready_count != null
            ? album.ready_count
            : tracks.filter(t => t.download_status === 'ready').length;

        $('#albumDetailTitle').text(album.name || 'Álbum');
        $('#albumDetailArtist').text(artist);
        $('#albumDetailMeta').text(
            `${tracks.length} faixa${tracks.length === 1 ? '' : 's'}` +
            (ready < tracks.length ? ` · ${ready} pronta${ready === 1 ? '' : 's'}` : '')
        );
        setCoverElement($('#albumDetailCover'), cover);
        if (cover) {
            $('#albumHeroBackdrop').css('background-image', `url("${cover}")`);
        } else {
            $('#albumHeroBackdrop').css('background-image', 'none');
        }

        const canPlay = tracks.some(t => t.download_status === 'ready');
        $('#albumPlayAllBtn').prop('disabled', !canPlay);

        applyAlbumTrackSearch($('#searchAlbumTracksInput').val() || '');
    }

    function applyAlbumTrackSearch(searchTerm) {
        const tracks = (currentAlbum && currentAlbum.tracks) || [];
        const term = (searchTerm || '').trim().toLowerCase();
        if (!term) {
            renderAlbumTrackList(tracks);
            return;
        }
        const filtered = tracks.filter(track => {
            const fields = [
                track.title,
                track.name,
                track.url,
                track.youtube_id,
                track.external_id,
            ];
            const kw = track.keywords;
            if (Array.isArray(kw) && kw.some(k => typeof k === 'string' && k.toLowerCase().includes(term))) {
                return true;
            }
            if (typeof kw === 'string' && kw.toLowerCase().includes(term)) {
                return true;
            }
            return fields.some(
                value => typeof value === 'string' && value.toLowerCase().includes(term)
            );
        });
        renderAlbumTrackList(filtered, searchTerm);
    }

    function renderAlbumTrackList(tracks, searchTerm = '') {
        const list = $('#albumTrackList');
        list.empty();

        const allTracks = (currentAlbum && currentAlbum.tracks) || [];
        if (!allTracks.length) {
            list.html(`
                <div class="yd-empty-state">
                    <i class="bi bi-music-note-list yd-empty-state__icon"></i>
                    <p class="yd-empty-state__title">Sem faixas</p>
                </div>
            `);
            return;
        }

        if (!tracks.length) {
            if (searchTerm) {
                list.html(`
                    <div class="yd-empty-state">
                        <i class="bi bi-search yd-empty-state__icon"></i>
                        <p class="yd-empty-state__title">Nenhum resultado para "${escapeHtml(searchTerm)}"</p>
                        <p class="yd-empty-state__desc">Tente outra palavra ou limpe a busca.</p>
                        <button type="button" class="btn btn-sm btn-outline-secondary mt-2" data-clear-target="#searchAlbumTracksInput">
                            <i class="bi bi-x-lg me-1"></i>Limpar busca
                        </button>
                    </div>
                `);
                list.find('[data-clear-target]').on('click', () => {
                    $('#searchAlbumTracksInput').val('').trigger('input');
                });
                return;
            }
            list.html(`
                <div class="yd-empty-state">
                    <i class="bi bi-music-note-list yd-empty-state__icon"></i>
                    <p class="yd-empty-state__title">Sem faixas</p>
                </div>
            `);
            return;
        }

        tracks.forEach((track) => {
            // Prefer original playlist order number when available
            const originalIdx = allTracks.findIndex(t => t.id === track.id);
            const num = track.track_number != null
                ? track.track_number
                : (originalIdx >= 0 ? originalIdx + 1 : 1);
            const readyTrack = track.download_status === 'ready';
            const statusLabel = readyTrack
                ? ''
                : `<span class="badge bg-secondary">${escapeHtml(track.download_status || 'pendente')}</span>`;
            const playing = queueIndex >= 0 && albumQueue[queueIndex] && albumQueue[queueIndex].id === track.id;
            const title = track.title || track.name || '';
            const titleHtml = searchTerm
                ? highlightText(title, searchTerm)
                : escapeHtml(title);
            const row = $(`
                <div class="yd-album-track ${readyTrack ? 'is-ready' : ''} ${playing ? 'is-playing' : ''}" data-id="${escapeHtml(track.id)}">
                    <span class="yd-album-track__num">${num}</span>
                    <span class="yd-album-track__title" title="${escapeHtml(title)}">${titleHtml}</span>
                    ${statusLabel}
                    <button type="button" class="btn btn-sm btn-outline-danger yd-action-btn album-track-play" ${readyTrack ? '' : 'disabled'} title="Tocar">
                        <i class="bi bi-play-fill"></i>
                    </button>
                </div>
            `);
            if (readyTrack) {
                row.on('click', (e) => {
                    if ($(e.target).closest('.album-track-play').length) return;
                    playAlbumFromTrack(track.id);
                });
                row.find('.album-track-play').on('click', (e) => {
                    e.stopPropagation();
                    playAlbumFromTrack(track.id);
                });
            }
            list.append(row);
        });
    }

    function buildAlbumQueue(startTrackId) {
        const tracks = (currentAlbum && currentAlbum.tracks) || [];
        const ready = tracks.filter(t => t.download_status === 'ready');
        if (!ready.length) {
            albumQueue = [];
            queueIndex = -1;
            return false;
        }
        let ordered = ready.slice();
        if (albumShuffle) {
            for (let i = ordered.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [ordered[i], ordered[j]] = [ordered[j], ordered[i]];
            }
        }
        albumQueue = ordered;
        if (startTrackId) {
            const idx = albumQueue.findIndex(t => t.id === startTrackId);
            queueIndex = idx >= 0 ? idx : 0;
        } else {
            queueIndex = 0;
        }
        return true;
    }

    function playAlbumAll() {
        if (!buildAlbumQueue()) {
            showToast('Nenhuma faixa pronta para tocar', 'warning');
            return;
        }
        playAlbumAtIndex(queueIndex);
    }

    function playAlbumFromTrack(trackId) {
        if (!buildAlbumQueue(trackId)) {
            showToast('Faixa ainda não está pronta', 'warning');
            return;
        }
        playAlbumAtIndex(queueIndex);
    }

    function playAlbumAtIndex(index) {
        if (index < 0 || index >= albumQueue.length) return;
        queueIndex = index;
        const track = albumQueue[queueIndex];
        const audio = document.getElementById('albumAudioPlayer');
        if (!audio || !authToken) {
            showToast('Não autenticado', 'error');
            return;
        }

        // Pausa o player da aba Áudios para evitar sobreposição
        const mainPlayer = document.getElementById('audioPlayer');
        if (mainPlayer) {
            mainPlayer.pause();
        }

        audio.src = `${API_BASE_URL}/audio/stream/${track.id}?token=${authToken}`;
        audio.load();
        const playPromise = audio.play();
        if (playPromise && typeof playPromise.catch === 'function') {
            playPromise.catch(err => {
                console.error('Album play error:', err);
                showToast('Erro ao reproduzir faixa', 'error');
            });
        }

        const artist = (currentAlbum && currentAlbum.artist) || 'Vários';
        const cover = albumCoverUrl(currentAlbum, albumQueue);
        $('#albumPlayerTitle').text(track.title || track.name || 'Faixa');
        $('#albumPlayerArtist').text(artist);
        setCoverElement($('#albumPlayerCover'), cover);
        setAlbumPlayIcon(true);
        highlightPlayingTrack(track.id);
    }

    function highlightPlayingTrack(trackId) {
        $('#albumTrackList .yd-album-track').removeClass('is-playing');
        if (trackId) {
            $(`#albumTrackList .yd-album-track[data-id="${trackId}"]`).addClass('is-playing');
        }
    }

    function setAlbumPlayIcon(playing) {
        const icon = $('#albumPlayPauseBtn i');
        icon.toggleClass('bi-play-fill', !playing);
        icon.toggleClass('bi-pause-fill', playing);
    }

    function toggleAlbumPlayPause() {
        const audio = document.getElementById('albumAudioPlayer');
        if (!audio) return;
        if (!audio.src || queueIndex < 0) {
            playAlbumAll();
            return;
        }
        if (audio.paused) {
            audio.play().catch(() => showToast('Erro ao reproduzir faixa', 'error'));
        } else {
            audio.pause();
        }
    }

    function playAlbumNext() {
        if (!albumQueue.length) return;
        if (queueIndex < albumQueue.length - 1) {
            playAlbumAtIndex(queueIndex + 1);
        } else if (albumRepeatMode === 'all') {
            playAlbumAtIndex(0);
        }
    }

    function playAlbumPrev() {
        const audio = document.getElementById('albumAudioPlayer');
        if (audio && audio.currentTime > 3) {
            audio.currentTime = 0;
            return;
        }
        if (!albumQueue.length) return;
        if (queueIndex > 0) {
            playAlbumAtIndex(queueIndex - 1);
        } else if (albumRepeatMode === 'all') {
            playAlbumAtIndex(albumQueue.length - 1);
        } else if (audio) {
            audio.currentTime = 0;
        }
    }

    function cycleAlbumRepeat() {
        const modes = ['off', 'all', 'one'];
        const next = modes[(modes.indexOf(albumRepeatMode) + 1) % modes.length];
        albumRepeatMode = next;
        const btn = $('#albumRepeatBtn');
        btn.attr('data-mode', next);
        btn.toggleClass('is-active', next !== 'off');
        const icon = btn.find('i');
        icon.removeClass('bi-repeat bi-repeat-1');
        icon.addClass(next === 'one' ? 'bi-repeat-1' : 'bi-repeat');
        btn.attr('title', next === 'off' ? 'Repetir' : next === 'all' ? 'Repetir álbum' : 'Repetir faixa');
    }

    function onAlbumTimeUpdate() {
        if (albumSeeking) return;
        const audio = document.getElementById('albumAudioPlayer');
        if (!audio) return;
        const cur = audio.currentTime || 0;
        const dur = audio.duration || 0;
        $('#albumCurrentTime').text(formatAlbumTime(cur));
        $('#albumDuration').text(formatAlbumTime(dur));
        if (dur > 0) {
            $('#albumSeekBar').val((cur / dur) * 100);
        }
    }

    function onAlbumEnded() {
        if (albumRepeatMode === 'one') {
            playAlbumAtIndex(queueIndex);
            return;
        }
        if (queueIndex < albumQueue.length - 1) {
            playAlbumAtIndex(queueIndex + 1);
        } else if (albumRepeatMode === 'all') {
            playAlbumAtIndex(0);
        } else {
            setAlbumPlayIcon(false);
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
                <div class="yd-empty-state">
                    <i class="bi bi-folder2 yd-empty-state__icon"></i>
                    <p class="yd-empty-state__title">Nenhuma pasta encontrada</p>
                    <p class="yd-empty-state__desc">Clique em "Nova Pasta" para criar</p>
                </div>
            `);
            return;
        }

        folders.forEach(folder => {
            const iconClass = folder.icon || 'folder2';
            const colorStyle = folder.color ? `color: ${folder.color}` : 'color: var(--yd-warning)';
            // kind=album always; legacy playlist folders may still lack kind until restart backfill
            const isAlbum = folder.kind === 'album' ||
                (folder.kind !== 'playlist' && (folder.icon === 'playlist' || folder.description === 'Playlist'));
            const playAlbumBtn = isAlbum
                ? `<button class="btn btn-sm btn-outline-danger yd-action-btn play-album-btn" data-id="${folder.id}" title="Tocar álbum">
                       <i class="bi bi-play-fill"></i>
                   </button>`
                : '';

            const item = $(`
                <a href="#" class="yd-folder-item" data-id="${folder.id}">
                    <div class="d-flex w-100 align-items-center">
                        <div class="me-3">
                            <i class="bi bi-${iconClass} yd-folder-icon" style="${colorStyle}"></i>
                        </div>
                        <div class="flex-grow-1 min-width-0">
                            <h6 class="yd-media-title text-truncate">${folder.name}</h6>
                            ${folder.description ? `<small class="yd-media-meta">${folder.description}</small>` : ''}
                        </div>
                        <div class="ms-2 yd-action-group">
                            ${playAlbumBtn}
                            <button class="btn btn-sm btn-outline-secondary yd-action-btn edit-folder-btn" data-id="${folder.id}" title="Editar">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger yd-action-btn delete-folder-btn" data-id="${folder.id}" title="Excluir">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                </a>
            `);

            // Navigate into folder
            item.on('click', (e) => {
                if ($(e.target).closest('.edit-folder-btn, .delete-folder-btn, .play-album-btn').length === 0) {
                    e.preventDefault();
                    navigateToFolder(folder);
                }
            });

            item.find('.play-album-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                openAlbumById(folder.id, { autoplay: true });
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
                <div class="yd-empty-state">
                    <i class="bi bi-inbox yd-empty-state__icon"></i>
                    <p class="yd-empty-state__title">Pasta vazia</p>
                    <p class="yd-empty-state__desc">Mova itens para esta pasta</p>
                </div>
            `);
            return;
        }

        allItems.forEach(item => {
            const isAudio = item.itemType === 'audio';
            const icon = isAudio ? 'bi-music-note-beamed' : 'bi-camera-video';
            const thumbClass = isAudio ? 'yd-media-thumb--audio' : 'yd-media-thumb--video';
            const typeBadge = isAudio ?
                '<span class="yd-badge yd-badge--audio">Áudio</span>' :
                '<span class="yd-badge yd-badge--video">Vídeo</span>';
            const isSelected = selectedItems.some(s => s.id === item.id && s.type === item.itemType);

            const element = $(`
                <div class="yd-media-item folder-media-item ${isSelected ? 'selected' : ''}" data-id="${item.id}" data-type="${item.itemType}">
                    <div class="d-flex w-100 align-items-center">
                        <div class="form-check me-2">
                            <input class="form-check-input item-checkbox" type="checkbox" ${isSelected ? 'checked' : ''}
                                   data-id="${item.id}" data-type="${item.itemType}">
                        </div>
                        <div class="me-3">
                            <div class="yd-media-thumb ${thumbClass}">
                                <i class="bi ${icon}"></i>
                            </div>
                        </div>
                        <div class="flex-grow-1 min-width-0">
                            <h6 class="yd-media-title text-truncate">${item.title || item.name}</h6>
                            <div class="yd-media-meta">
                                ${typeBadge}
                                <span class="ms-2"><i class="bi bi-hdd me-1"></i>${formatFileSize(item.filesize)}</span>
                            </div>
                        </div>
                        <div class="ms-2 yd-action-group">
                            <button class="btn btn-sm btn-success yd-action-btn play-item-btn" data-id="${item.id}" data-type="${item.itemType}" title="Reproduzir">
                                <i class="bi bi-play-fill"></i>
                            </button>
                            ${item.transcription_status === 'ended' ? `
                            <button class="btn btn-sm btn-outline-info yd-action-btn view-transcription-btn" data-id="${item.id}" data-type="${item.itemType}" title="Ver Transcrição">
                                <i class="bi bi-eye"></i>
                            </button>` : ''}
                            <button class="btn btn-sm btn-outline-secondary yd-action-btn move-item-btn" data-id="${item.id}" data-type="${item.itemType}" title="Mover">
                                <i class="bi bi-arrow-right-circle"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-warning yd-action-btn remove-from-folder-btn" data-id="${item.id}" data-type="${item.itemType}" title="Remover da pasta">
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

            element.find('.view-transcription-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                viewTranscription(item.id, item.title || item.name);
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
                <div class="yd-empty-state">
                    <i class="bi bi-check-circle yd-empty-state__icon"></i>
                    <p class="yd-empty-state__desc">Todos os itens estão organizados em pastas</p>
                </div>
            `);
            return;
        }

        allItems.forEach(item => {
            const isAudio = item.itemType === 'audio';
            const icon = isAudio ? 'bi-music-note-beamed' : 'bi-camera-video';
            const thumbClass = isAudio ? 'yd-media-thumb--audio' : 'yd-media-thumb--video';
            const typeBadge = isAudio ?
                '<span class="yd-badge yd-badge--audio">Áudio</span>' :
                '<span class="yd-badge yd-badge--video">Vídeo</span>';
            const isSelected = selectedItems.some(s => s.id === item.id && s.type === item.itemType);

            const element = $(`
                <div class="yd-media-item unorganized-item ${isSelected ? 'selected' : ''}" data-id="${item.id}" data-type="${item.itemType}">
                    <div class="d-flex w-100 align-items-center">
                        <div class="form-check me-2">
                            <input class="form-check-input item-checkbox" type="checkbox" ${isSelected ? 'checked' : ''}
                                   data-id="${item.id}" data-type="${item.itemType}">
                        </div>
                        <div class="me-3">
                            <div class="yd-media-thumb ${thumbClass}">
                                <i class="bi ${icon}"></i>
                            </div>
                        </div>
                        <div class="flex-grow-1 min-width-0">
                            <h6 class="yd-media-title text-truncate">${item.title || item.name}</h6>
                            <div class="yd-media-meta">
                                ${typeBadge}
                                <span class="ms-2"><i class="bi bi-hdd me-1"></i>${formatFileSize(item.filesize)}</span>
                            </div>
                        </div>
                        <div class="ms-2 yd-action-group">
                            <button class="btn btn-sm btn-success yd-action-btn play-item-btn" data-id="${item.id}" data-type="${item.itemType}" title="Reproduzir">
                                <i class="bi bi-play-fill"></i>
                            </button>
                            ${item.transcription_status === 'ended' ? `
                            <button class="btn btn-sm btn-outline-info yd-action-btn view-transcription-btn" data-id="${item.id}" data-type="${item.itemType}" title="Ver Transcrição">
                                <i class="bi bi-eye"></i>
                            </button>` : ''}
                            <button class="btn btn-sm btn-danger yd-action-btn move-to-folder-btn" data-id="${item.id}" data-type="${item.itemType}" title="Mover para pasta">
                                <i class="bi bi-folder-plus"></i>
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

            element.find('.view-transcription-btn').on('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                viewTranscription(item.id, item.title || item.name);
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
                        <i class="bi bi-${iconClass} me-2" style="color: ${folder.color || 'var(--yd-warning)'}"></i>
                        ${folder.name}
                        ${isCurrentFolder ? '<span class="yd-badge yd-badge--pending ms-2">Atual</span>' : ''}
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
    function getStatusBadge(status, id) {
        if (status === 'downloading' && id) {
            const dl = activeDownloads.get(id);
            const progress = dl ? dl.progress : 0;
            const dlStatus = dl ? dl.status : 'downloading';
            return `<span class="yd-status-badge" data-badge-id="${id}">${buildRingProgress(progress, dlStatus)}</span>`;
        }
        const badges = {
            'ready': '<span class="yd-badge yd-badge--ready"><i class="bi bi-check-circle me-1"></i>Pronto</span>',
            'downloading': '<span class="yd-badge yd-badge--downloading"><i class="bi bi-arrow-down-circle me-1"></i>Baixando</span>',
            'pending': '<span class="yd-badge yd-badge--pending"><i class="bi bi-clock me-1"></i>Pendente</span>',
            'error': '<span class="yd-badge yd-badge--error"><i class="bi bi-x-circle me-1"></i>Erro</span>'
        };
        return badges[status] || '';
    }

    function escapeRegex(str) {
        return String(str).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    function highlightText(text, searchTerm) {
        if (!searchTerm || !text) return text || '';
        const regex = new RegExp(`(${escapeRegex(searchTerm)})`, 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }

    // Campos pesquisados em filterList para Áudios/Vídeos. Inclui keywords
    // (array de strings, vindo do to_dict() do modelo) e url (não source_url —
    // o payload usa "url"). title/name continuam sendo os primários.
    const SEARCH_FIELDS = ['title', 'name', 'url'];

    function filterList(items, searchTerm, renderFn) {
        if (!searchTerm) {
            renderFn(items);
            return;
        }

        const term = searchTerm.toLowerCase();
        const filtered = items.filter(item => {
            for (const field of SEARCH_FIELDS) {
                const value = item[field];
                if (typeof value === 'string' && value.toLowerCase().includes(term)) {
                    return true;
                }
            }
            // keywords pode ser array
            const kw = item.keywords;
            if (Array.isArray(kw) && kw.some(k => typeof k === 'string' && k.toLowerCase().includes(term))) {
                return true;
            }
            if (typeof kw === 'string' && kw.toLowerCase().includes(term)) {
                return true;
            }
            return false;
        });

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
    function syncClearButton(inputEl) {
        const $input = $(inputEl);
        const hasValue = !!$input.val();
        $(`.yd-search-clear[data-target="#${$input.attr('id')}"]`).prop('hidden', !hasValue);
    }

    let audioSearchTimeout;
    $('#searchAudioInput').on('input', function() {
        clearTimeout(audioSearchTimeout);
        const searchTerm = $(this).val();
        syncClearButton(this);
        audioSearchTimeout = setTimeout(() => {
            filterList(currentAudios, searchTerm, renderAudioList);
        }, 300);
    });

    let videoSearchTimeout;
    $('#searchVideoInput').on('input', function() {
        clearTimeout(videoSearchTimeout);
        const searchTerm = $(this).val();
        syncClearButton(this);
        videoSearchTimeout = setTimeout(() => {
            filterList(currentVideos, searchTerm, renderVideoList);
        }, 300);
    });

    let albumSearchTimeout;
    $('#searchAlbumsInput').on('input', function() {
        clearTimeout(albumSearchTimeout);
        const searchTerm = $(this).val();
        syncClearButton(this);
        albumSearchTimeout = setTimeout(() => {
            applyAlbumSearch(searchTerm);
        }, 300);
    });

    let albumTrackSearchTimeout;
    $('#searchAlbumTracksInput').on('input', function() {
        clearTimeout(albumTrackSearchTimeout);
        const searchTerm = $(this).val();
        syncClearButton(this);
        albumTrackSearchTimeout = setTimeout(() => {
            applyAlbumTrackSearch(searchTerm);
        }, 300);
    });

    // Click-to-play a partir do item de Transcrições.
    // Troca para a aba correspondente (Áudios ou Vídeos) e dispara o player.
    // Reproveita as funções existentes playAudio/playVideo — não duplica lógica.
    function playFromTranscriptionItem(media) {
        const isAudio = media.mediaType === 'audio';
        const targetTabId = isAudio ? '#audio-tab' : '#video-tab';
        const tabEl = document.querySelector(targetTabId);
        if (!tabEl) return;

        // Acompanha o evento "shown" para garantir que o pane esteja visível
        // antes de chamar o player (necessário no caso de vídeo, cujo overlay
        // de loading reside no DOM do pane).
        const onShown = () => {
            tabEl.removeEventListener('shown.bs.tab', onShown);
            if (isAudio) {
                playAudio(media);
            } else {
                playVideo(media);
            }
        };

        if (tabEl.classList.contains('active')) {
            // Já está na aba — toca direto.
            if (isAudio) playAudio(media); else playVideo(media);
        } else {
            tabEl.addEventListener('shown.bs.tab', onShown, { once: true });
            bootstrap.Tab.getOrCreateInstance(tabEl).show();
        }
    }

    // --- Transcription search ---
    let transcriptionSearchTimeout;
    let transcriptionSearchAbort = null;

    function applyTranscriptionSearch() {
        const term = lastTranscriptionSearchTerm.trim();
        if (!term) {
            renderTranscriptionMediaList(currentTranscriptionMedia);
            return;
        }
        if (transcriptionSearchMode === 'title') {
            const lower = term.toLowerCase();
            const filtered = currentTranscriptionMedia.filter(m =>
                ((m.title || '').toLowerCase().includes(lower)) ||
                ((m.name || '').toLowerCase().includes(lower))
            );
            renderTranscriptionMediaList(filtered, term);
            return;
        }
        // Modo conteúdo: hit backend
        if (term.length < 2) {
            renderTranscriptionMediaList(currentTranscriptionMedia, term);
            return;
        }
        runTranscriptionContentSearch(term);
    }

    function runTranscriptionContentSearch(term) {
        if (transcriptionSearchAbort) {
            transcriptionSearchAbort.abort();
        }
        const controller = new AbortController();
        transcriptionSearchAbort = controller;
        const url = `${API_BASE_URL}/transcription/search?q=${encodeURIComponent(term)}`;
        $('#transcriptionMediaList').html(`
            <div class="yd-empty-state">
                <div class="spinner-border text-danger mb-3" role="status"><span class="visually-hidden">Buscando...</span></div>
                <p class="mb-0">Buscando "${escapeHtml(term)}" nas transcrições...</p>
            </div>
        `);
        fetch(url, {
            headers: getAuthHeaders(),
            signal: controller.signal
        })
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                return r.json();
            })
            .then(data => {
                const rows = Array.isArray(data?.results) ? data.results : [];
                // Chave composta por (file_id, media_type): áudio e vídeo
                // do mesmo external_id seriam colidir em uma única chave.
                const keyOf = (id, type) => `${id}|${type}`;
                const matchKeys = new Set(
                    rows.filter(r => r && r.file_id && r.media_type)
                        .map(r => keyOf(r.file_id, r.media_type))
                );
                const snippets = {};
                rows.forEach(r => {
                    if (!r || !r.file_id || !r.media_type) return;
                    snippets[keyOf(r.file_id, r.media_type)] = {
                        snippet: r.snippet,
                        match_count: r.match_count,
                    };
                });
                const filtered = currentTranscriptionMedia.filter(
                    m => matchKeys.has(keyOf(m.id, m.mediaType))
                );
                filtered.sort((a, b) =>
                    (snippets[keyOf(b.id, b.mediaType)]?.match_count || 0)
                    - (snippets[keyOf(a.id, a.mediaType)]?.match_count || 0)
                );
                renderTranscriptionMediaList(filtered, term, snippets, true);
                if (data?.truncated) {
                    showToast(
                        `Mostrando os primeiros ${rows.length} de ${data.total_matches} resultados`,
                        'info'
                    );
                }
            })
            .catch(err => {
                if (err.name === 'AbortError') return;
                console.error('Erro na busca de conteúdo:', err);
                showToast('Erro na busca de conteúdo das transcrições', 'error');
                renderTranscriptionMediaList([], term);
            });
    }

    $('#searchTranscriptionInput').on('input', function() {
        clearTimeout(transcriptionSearchTimeout);
        lastTranscriptionSearchTerm = $(this).val();
        syncClearButton(this);
        const delay = transcriptionSearchMode === 'content' ? 400 : 200;
        transcriptionSearchTimeout = setTimeout(applyTranscriptionSearch, delay);
    });

    $('input[name="searchTranscriptionMode"]').on('change', function() {
        transcriptionSearchMode = $(this).val();
        // Cancela qualquer fetch de conteúdo em voo antes de aplicar o novo modo
        // — evita que uma resposta tardia sobrescreva a renderização do modo título.
        if (transcriptionSearchAbort) {
            transcriptionSearchAbort.abort();
            transcriptionSearchAbort = null;
        }
        applyTranscriptionSearch();
    });

    // Botões de limpar (×) compartilhados nos inputs de busca
    $(document).on('click', '.yd-search-clear', function() {
        const target = $(this).data('target');
        $(target).val('').trigger('input').focus();
    });

    // ESC dentro de um input de busca limpa o conteúdo
    $('.yd-search-input').on('keydown', function(e) {
        if (e.key === 'Escape' && $(this).val()) {
            e.preventDefault();
            $(this).val('').trigger('input');
        }
    });

    // Atalho global '/' para focar a busca da aba ativa
    $(document).on('keydown', function(e) {
        if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return;
        const tag = (e.target.tagName || '').toLowerCase();
        if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.target.isContentEditable) return;
        const activePane = $('.tab-pane.active');
        // Prefer the search field that is actually visible (library vs album detail).
        let $input = activePane.find('.yd-search-input:visible').first();
        if (!$input.length) {
            $input = activePane.find('.yd-search-input').first();
        }
        if ($input.length) {
            e.preventDefault();
            $input.trigger('focus').select();
        }
    });

    // Tab change events
    $('button[data-bs-toggle="pill"]').on('shown.bs.tab', function(e) {
        const target = $(e.target).attr('data-bs-target');
        // Sair da aba de transcrições para o poller global (Bootstrap pills
        // apenas ocultam o pane; sem isto o timer continuaria disparando).
        if (target !== '#transcription-pane') {
            stopTranscriptionStatusPoller();
        }
        if (target === '#audio-pane') {
            loadAudioList();
        } else if (target === '#video-pane') {
            loadVideoList();
        } else if (target === '#transcription-pane') {
            loadTranscriptionMediaList();
        } else if (target === '#folders-pane') {
            loadFolders(currentFolderId);
        } else if (target === '#albums-pane') {
            loadAlbums();
        }
    });

    // Album player controls
    $('#refreshAlbumsBtn').on('click', () => {
        loadAlbums();
        showToast('Lista de álbuns atualizada', 'info');
    });
    $('#albumBackBtn').on('click', showAlbumsLibrary);
    $('#albumPlayAllBtn').on('click', () => playAlbumAll());
    $('#albumPlayPauseBtn').on('click', toggleAlbumPlayPause);
    $('#albumPrevBtn').on('click', playAlbumPrev);
    $('#albumNextBtn').on('click', playAlbumNext);
    $('#albumShuffleBtn').on('click', () => {
        albumShuffle = !albumShuffle;
        $('#albumShuffleBtn').toggleClass('is-active', albumShuffle);
    });
    $('#albumRepeatBtn').on('click', cycleAlbumRepeat);
    $('#albumSeekBar').on('input', function() {
        albumSeeking = true;
        const audio = document.getElementById('albumAudioPlayer');
        if (audio && audio.duration) {
            $('#albumCurrentTime').text(formatAlbumTime((this.value / 100) * audio.duration));
        }
    });
    $('#albumSeekBar').on('change', function() {
        const audio = document.getElementById('albumAudioPlayer');
        if (audio && audio.duration) {
            audio.currentTime = (this.value / 100) * audio.duration;
        }
        albumSeeking = false;
    });

    const albumAudioEl = document.getElementById('albumAudioPlayer');
    if (albumAudioEl) {
        albumAudioEl.addEventListener('timeupdate', onAlbumTimeUpdate);
        albumAudioEl.addEventListener('loadedmetadata', onAlbumTimeUpdate);
        albumAudioEl.addEventListener('play', () => setAlbumPlayIcon(true));
        albumAudioEl.addEventListener('pause', () => setAlbumPlayIcon(false));
        albumAudioEl.addEventListener('ended', onAlbumEnded);
    }

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
    initTheme();
    authenticate();
});
