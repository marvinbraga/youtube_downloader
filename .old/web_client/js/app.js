$(document).ready(function () {
  // Configurações básicas da aplicação
  const API_BASE_URL = 'http://localhost:8000';
  let currentVideos = [];
  let currentAudios = [];
  let currentVideoId = null;
  let currentAudioId = null;
  let currentTranscriptionId = null;

  // Configurações de autenticação
  let authToken = null;
  const CLIENT_ID = 'your_client_id';
  const CLIENT_SECRET = 'your_client_secret';
  const VIDEO_CACHE_KEY = 'video_list_cache';
  const AUDIO_CACHE_KEY = 'audio_list_cache';
  const CACHE_DURATION = 5 * 60 * 1000; // 5 minutos

  // Mapeamento de status de transcrição para mensagens e cores
  const transcriptionStatusMap = {
      "none": {
          badge: null,
          buttonClass: "btn-success",
          buttonIcon: "fas fa-microphone",
          buttonText: "Transcrever"
      },
      "started": {
          badge: { text: "Transcrevendo", class: "badge-warning", icon: "fas fa-spinner fa-spin" },
          buttonClass: "btn-warning",
          buttonIcon: "fas fa-spinner fa-spin",
          buttonText: "Transcrevendo..."
      },
      "ended": {
          badge: { text: "Transcrito", class: "badge-success", icon: "fas fa-check" },
          buttonClass: "btn-warning",
          buttonIcon: "fas fa-file-alt",
          buttonText: "Ver Transcrição"
      },
      "error": {
          badge: { text: "Erro", class: "badge-error", icon: "fas fa-exclamation-circle" },
          buttonClass: "btn-danger",
          buttonIcon: "fas fa-redo",
          buttonText: "Tentar Novamente"
      }
  };

  // Configurações do modal
  const modal = document.getElementById("transcriptionModal");
  const span = document.getElementsByClassName("close")[0];
  
  // Fechar o modal quando o usuário clica no X
  span.onclick = function() {
    modal.style.display = "none";
  }
  
  // Fechar o modal quando o usuário clica fora dele
  window.onclick = function(event) {
    if (event.target == modal) {
      modal.style.display = "none";
    }
  }

  function saveToCache(items, sortBy, cacheKey) {
    const cache = {
      timestamp: Date.now(),
      data: items,
      sortBy: sortBy  // Salvamos também o tipo de ordenação
    };
    localStorage.setItem(cacheKey, JSON.stringify(cache));
  }

  function getFromCache(requestedSortBy, cacheKey) {
    const cache = localStorage.getItem(cacheKey);
    if (!cache) return null;

    const {timestamp, data, sortBy} = JSON.parse(cache);

    if (Date.now() - timestamp > CACHE_DURATION || (sortBy !== undefined && sortBy !== requestedSortBy)) {
      localStorage.removeItem(cacheKey);
      return null;
    }

    return data;
  }

  function toggleLoading(show, message = "Carregando...") {
    if (show) {
      $('.loading-text').text(message);
      $('#loadingOverlay').css('display', 'flex');
    } else {
      $('#loadingOverlay').hide();
    }
  }

  // Sistema de autenticação
  async function authenticate() {
    try {
      console.log('Tentando autenticar...');
      const response = await $.ajax({
        url: `${API_BASE_URL}/auth/token`,
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
          client_id: CLIENT_ID,
          client_secret: CLIENT_SECRET
        })
      });
      console.log('Autenticação bem-sucedida:', response);

      authToken = response.access_token;
      setTimeout(authenticate, 25 * 60 * 1000);
      loadVideoList();
      loadAudioList();
    } catch (error) {
      console.error('Erro de autenticação:', error);
      showError('Erro de autenticação. Por favor, recarregue a página.');
    }
  }

  // Funções auxiliares
  function getAuthHeaders() {
    return {
      'Authorization': `Bearer ${authToken}`
    };
  }

  function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  }

  function formatFileSize(bytes) {
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 Byte';
    const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
    return Math.round(bytes / Math.pow(1024, i), 2) + ' ' + sizes[i];
  }

  function highlightText(text, searchTerm) {
    if (!searchTerm) return text;
    const regex = new RegExp(`(${searchTerm})`, 'gi');
    return text.replace(regex, '<span class="highlight">$1</span>');
  }

  function showError(message) {
    $('#errorMessage').text(message).show();
    setTimeout(() => $('#errorMessage').hide(), 5000);
  }
  
  function showSuccess(message) {
    $('#successMessage').text(message).show();
    setTimeout(() => $('#successMessage').hide(), 5000);
  }
  
  function showInfo(message) {
    $('#infoMessage').text(message).show();
    setTimeout(() => $('#infoMessage').hide(), 5000);
  }

  // Renderização e gerenciamento de vídeos
  function renderVideoList(videos, searchTerm = '') {
    const videosDiv = $('#videos').empty();

    if (videos.length === 0) {
      videosDiv.append('<div class="no-results">Nenhum vídeo encontrado</div>');
      return;
    }

    const highlight = text => searchTerm ?
      text.replace(new RegExp(`(${searchTerm})`, 'gi'), '<span class="highlight">$1</span>') :
      text;

    videos.forEach(video => {
      // Verifica o status da transcrição (se existir)
      const transcriptionStatus = video.transcription_status || "none";
      
      // Obtém os detalhes de exibição com base no status
      const statusConfig = transcriptionStatusMap[transcriptionStatus] || transcriptionStatusMap["none"];
      
      // Indicador visual de transcrição (badge)
      let transcriptionBadge = '';
      if (statusConfig.badge) {
        transcriptionBadge = $('<span>')
          .addClass(`badge ${statusConfig.badge.class}`)
          .html(`<i class="${statusConfig.badge.icon}"></i> ${statusConfig.badge.text}`)
          .css('margin-left', '10px');
      }
      
      // Adiciona botões de ação para o vídeo
      const actionButtons = $('<div>')
        .addClass('action-buttons')
        .append(
          $('<button>')
            .addClass('btn btn-primary')
            .html('<i class="fas fa-play icon"></i>Reproduzir')
            .click((e) => {
              e.stopPropagation();
              playVideo(video);
            })
        );
      
      // Adiciona botão de transcrição se aplicável
      if (transcriptionStatus === "ended") {
        actionButtons.append(
          $('<button>')
            .addClass(`btn ${statusConfig.buttonClass}`)
            .html(`<i class="${statusConfig.buttonIcon} icon"></i>${statusConfig.buttonText}`)
            .click((e) => {
              e.stopPropagation();
              viewTranscription(video);
            })
        );
      }
      
      const videoElement = $('<div>')
        .addClass('video-item')
        .toggleClass('active', video.id === currentVideoId)
        .append(
          $('<div>').html(highlight(video.name)).append(transcriptionBadge),
          $('<div>')
            .addClass('video-info')
            .append(
              $('<div>').text(`Caminho: ${video.path}`),
              $('<div>').text(`Modificado em: ${formatDate(video.modified_date)}`),
              $('<div>').text(`Tamanho: ${formatFileSize(video.size)}`)
            ),
          actionButtons
        )
        .click(() => playVideo(video));
      videosDiv.append(videoElement);
    });
  }
  
  // Renderização e gerenciamento de áudios
  function renderAudioList(audios, searchTerm = '') {
    const audiosDiv = $('#audios').empty();

    if (audios.length === 0) {
      audiosDiv.append('<div class="no-results">Nenhum áudio encontrado</div>');
      return;
    }

    const highlight = text => searchTerm ?
      text.replace(new RegExp(`(${searchTerm})`, 'gi'), '<span class="highlight">$1</span>') :
      text;

    audios.forEach(audio => {
      // Verifica o status da transcrição
      const transcriptionStatus = audio.transcription_status || "none";
      
      console.log(`Áudio ${audio.id} - transcription_status: ${transcriptionStatus}`);
      
      // Obtém os detalhes de exibição com base no status
      const statusConfig = transcriptionStatusMap[transcriptionStatus] || transcriptionStatusMap["none"];
      
      // Botões de ação para cada áudio
      const actionButtons = $('<div>')
        .addClass('action-buttons')
        .append(
          $('<button>')
            .addClass('btn btn-primary')
            .html('<i class="fas fa-play icon"></i>Reproduzir')
            .click((e) => {
              e.stopPropagation();
              playAudio(audio);
            })
        );
        
      // Adiciona o botão de transcrição com base no status
      const transcribeBtn = $('<button>')
        .addClass(`btn ${statusConfig.buttonClass}`)
        .html(`<i class="${statusConfig.buttonIcon} icon"></i>${statusConfig.buttonText}`)
        .click((e) => {
          e.stopPropagation();
          
          // Comportamento com base no status
          if (transcriptionStatus === "ended") {
            // Se já está transcrito, visualiza a transcrição
            viewTranscription(audio);
          } else if (transcriptionStatus === "started") {
            // Se está em andamento, verifica o status atual
            checkTranscriptionStatus(audio);
          } else {
            // Se não tem transcrição ou teve erro, inicia nova transcrição
            transcribeAudio(audio);
          }
        });
        
      // Se está em andamento, desabilita o botão
      if (transcriptionStatus === "started") {
        transcribeBtn.prop('disabled', true).addClass('btn-disabled');
      }
      
      actionButtons.append(transcribeBtn);
      
      // Indicador visual de transcrição (badge)
      let transcriptionBadge = '';
      if (statusConfig.badge) {
        transcriptionBadge = $('<span>')
          .addClass(`badge ${statusConfig.badge.class}`)
          .html(`<i class="${statusConfig.badge.icon}"></i> ${statusConfig.badge.text}`)
          .css('margin-left', '10px');
      }
      
      // Criando o elemento de áudio
      const audioElement = $('<div>')
        .addClass('audio-item')
        .toggleClass('active', audio.id === currentAudioId)
        .attr('data-id', audio.id)  // Adicionando o ID como atributo para facilitar a busca
        .append(
          $('<div>').html(highlight(audio.name)).append(transcriptionBadge),
          $('<div>')
            .addClass('audio-info')
            .append(
              $('<div>').text(`Caminho: ${audio.path}`),
              $('<div>').text(`Modificado em: ${formatDate(audio.modified_date)}`),
              $('<div>').text(`Tamanho: ${formatFileSize(audio.size)}`)
            ),
          actionButtons
        )
        .click(() => {
          $('.audio-item').removeClass('active');
          audioElement.addClass('active');
          currentAudioId = audio.id;
        });
        
      audiosDiv.append(audioElement);
    });
    
    // Inicia verificação periódica para áudios em transcrição
    const inProgressAudios = audios.filter(audio => audio.transcription_status === "started");
    if (inProgressAudios.length > 0) {
      startTranscriptionStatusCheck(inProgressAudios);
    }
  }

  // Funções de gerenciamento de vídeos
  function filterVideos(searchTerm) {
    if (!searchTerm) {
      renderVideoList(currentVideos);
      return;
    }

    const searchTermLower = searchTerm.toLowerCase();
    const filteredVideos = currentVideos.filter(video =>
      video.name.toLowerCase().includes(searchTermLower) ||
      video.path.toLowerCase().includes(searchTermLower)
    );

    renderVideoList(filteredVideos, searchTerm);
  }
  
  // Funções de gerenciamento de áudios
  function filterAudios(searchTerm) {
    if (!searchTerm) {
      renderAudioList(currentAudios);
      return;
    }

    const searchTermLower = searchTerm.toLowerCase();
    const filteredAudios = currentAudios.filter(audio =>
      audio.name.toLowerCase().includes(searchTermLower) ||
      audio.path.toLowerCase().includes(searchTermLower)
    );

    renderAudioList(filteredAudios, searchTerm);
  }

  function loadVideoList(sortBy = 'none') {
    if (!authToken) {
      authenticate();
      return;
    }

    // Limpa o cache para forçar atualização dos dados
    localStorage.removeItem(VIDEO_CACHE_KEY);

    $.ajax({
      url: `${API_BASE_URL}/videos?sort_by=${sortBy}`,
      method: 'GET',
      headers: getAuthHeaders(),
      success: function (response) {
        currentVideos = response.videos || [];
        
        // Verifica e atualiza status de transcrição para cada vídeo
        checkTranscriptionStatusForAllItems(currentVideos, "video");
        
        saveToCache(currentVideos, sortBy, VIDEO_CACHE_KEY);  // Salvamos com a ordenação atual
        filterVideos($('#searchVideoInput').val());
      },
      error: function (xhr, status, error) {
        if (xhr.status === 401) {
          authenticate();
        } else {
          showError(`Erro ao carregar vídeos: ${error}`);
        }
      }
    });
  }
  
  function loadAudioList() {
    if (!authToken) {
      authenticate();
      return;
    }

    // Limpa o cache para forçar uma atualização dos dados
    localStorage.removeItem(AUDIO_CACHE_KEY);

    $.ajax({
      url: `${API_BASE_URL}/audio/list`,
      method: 'GET',
      headers: getAuthHeaders(),
      success: function (response) {
        currentAudios = response.audio_files || [];
        console.log("Áudios carregados:", currentAudios);
        
        // Verifica e atualiza status de transcrição para áudios (para manter compatibilidade com sistemas antigos)
        checkTranscriptionStatusForAllItems(currentAudios, "audio");
        
        saveToCache(currentAudios, null, AUDIO_CACHE_KEY);
        filterAudios($('#searchAudioInput').val());
      },
      error: function (xhr, status, error) {
        if (xhr.status === 401) {
          authenticate();
        } else {
          showError(`Erro ao carregar áudios: ${error}`);
        }
      }
    });
  }
  
  // Função para verificar o status de transcrição de todos os itens
  function checkTranscriptionStatusForAllItems(items, type) {
    // Para cada item, verifica se há has_transcription definido sem transcription_status
    items.forEach(item => {
      // Migra has_transcription antigo para transcription_status
      if (item.has_transcription === true && !item.transcription_status) {
        item.transcription_status = "ended";
        console.log(`Atualizando ${type} ${item.id}: has_transcription = true -> transcription_status = ended`);
      }
      
      // Se tiver caminho de transcrição mas não tiver status, considera como "ended"
      if (item.transcription_path && (!item.transcription_status || item.transcription_status === "none")) {
        item.transcription_status = "ended";
        console.log(`Atualizando ${type} ${item.id}: tem caminho de transcrição -> transcription_status = ended`);
      }
      
      // Para compatibilidade, verifica se o arquivo corresponde a um MD no sistema
      // Isso só seria feito para uma migração completa, aqui só registramos no console
      if (!item.transcription_status || item.transcription_status === "none") {
        console.log(`${type} ${item.id} (${item.name}) não possui status de transcrição definido`);
      }
    });
  }
  
  // Timer para verificar transcrições em andamento
  let transcriptionCheckTimer = null;
  
  function startTranscriptionStatusCheck(audiosToCheck) {
    // Limpa o timer existente, se houver
    if (transcriptionCheckTimer) {
      clearInterval(transcriptionCheckTimer);
    }
    
    // Define um intervalo para verificar o status da transcrição
    transcriptionCheckTimer = setInterval(() => {
      audiosToCheck.forEach(audio => {
        checkTranscriptionStatus(audio, false); // false indica verificação silenciosa
      });
    }, 10000); // Verifica a cada 10 segundos
  }
  
  // Verifica o status da transcrição
  async function checkTranscriptionStatus(audio, showMessages = true) {
    if (!authToken) {
      if (showMessages) showError('Erro de autenticação. Tentando reconectar...');
      return authenticate();
    }
    
    try {
      if (showMessages) toggleLoading(true, "Verificando status da transcrição...");
      
      const response = await $.ajax({
        url: `${API_BASE_URL}/audio/transcription_status/${audio.id}`,
        method: 'GET',
        headers: getAuthHeaders()
      });
      
      if (showMessages) toggleLoading(false);
      
      console.log("Status da transcrição:", response);
      
      // Se o status mudou, atualiza a interface
      if (response.status !== audio.transcription_status) {
        console.log(`Status da transcrição mudou: ${audio.transcription_status} -> ${response.status}`);
        
        // Encontra o áudio na lista e atualiza seu status
        const updatedAudios = currentAudios.map(a => {
          if (a.id === audio.id) {
            return { ...a, transcription_status: response.status };
          }
          return a;
        });
        
        // Atualiza a lista de áudios
        currentAudios = updatedAudios;
        saveToCache(currentAudios, null, AUDIO_CACHE_KEY);
        
        // Renderiza novamente para mostrar o novo status
        renderAudioList(currentAudios, $('#searchAudioInput').val());
        
        // Se a transcrição foi concluída e estamos mostrando mensagens
        if (response.status === "ended" && showMessages) {
          showSuccess("Transcrição concluída com sucesso!");
          
          // Pergunta se o usuário quer visualizar a transcrição
          if (confirm("Transcrição concluída! Deseja visualizá-la agora?")) {
            viewTranscription({...audio, transcription_status: "ended"});
          }
        } 
        // Se houve erro e estamos mostrando mensagens
        else if (response.status === "error" && showMessages) {
          showError("Ocorreu um erro durante a transcrição. Você pode tentar novamente.");
        }
      } else if (showMessages) {
        // Se o status não mudou, mas estamos mostrando mensagens
        if (response.status === "started") {
          showInfo("A transcrição ainda está em andamento. Por favor, aguarde.");
        } else if (response.status === "ended") {
          viewTranscription({...audio, transcription_status: "ended"});
        }
      }
      
      return response.status;
    } catch (error) {
      if (showMessages) {
        console.error('Erro:', error);
        toggleLoading(false);
        showError(`Erro ao verificar status da transcrição: ${error.message}`);
      }
      if (error.status === 401) authenticate();
      return null;
    }
  }

  async function playVideo(video) {
    if (!authToken) {
      showError('Erro de autenticação. Tentando reconectar...');
      return authenticate();
    }

    try {
      toggleLoading(true, "Carregando vídeo..."); // Mostra o loading

      const response = await fetch(`${API_BASE_URL}/video/${video.id}`, {
        headers: getAuthHeaders()
      });

      const reader = response.body.getReader();
      let receivedLength = 0;
      const chunks = [];

      while (true) {
        const {done, value} = await reader.read();

        if (done) break;

        chunks.push(value);
        receivedLength += value.length;
        $('.loading-text').text(`Carregando vídeo...`);
      }

      const videoBlob = new Blob(chunks);
      const url = URL.createObjectURL(videoBlob);
      const videoPlayer = $('#videoPlayer')[0];

      videoPlayer.src = url;
      videoPlayer.onended = () => URL.revokeObjectURL(url);

      // Eventos para controlar o loading
      videoPlayer.onloadeddata = () => {
        toggleLoading(false);
      };

      videoPlayer.onerror = () => {
        toggleLoading(false);
        showError('Erro ao carregar o vídeo');
      };

      await videoPlayer.play();

      currentVideoId = video.id;
      $('#currentVideoTitle').text(video.name);
      renderVideoList(currentVideos, $('#searchVideoInput').val());

    } catch (error) {
      console.error('Erro:', error);
      toggleLoading(false);
      showError(`Erro ao reproduzir vídeo: ${error.message}`);
      if (error.message.includes('401')) authenticate();
    }
  }
  
  async function playAudio(audio) {
    try {
      toggleLoading(true, "Carregando áudio..."); // Mostra o loading
      
      // Atualiza o elemento ativo
      $('.audio-item').removeClass('active');
      $(`.audio-item[data-id="${audio.id}"]`).addClass('active');
      currentAudioId = audio.id;
      
      // Carregando o arquivo de áudio - como não temos um endpoint específico, 
      // você precisaria implementar isso no backend ou ajustar este código
      toggleLoading(false);
      
      showError("Reprodução de áudio ainda não implementada");
      
    } catch (error) {
      console.error('Erro:', error);
      toggleLoading(false);
      showError(`Erro ao reproduzir áudio: ${error.message}`);
      if (error.message.includes('401')) authenticate();
    }
  }
  
  // Função para visualizar uma transcrição existente
  async function viewTranscription(item) {
    if (!authToken) {
      showError('Erro de autenticação. Tentando reconectar...');
      return authenticate();
    }
    
    try {
      toggleLoading(true, "Carregando transcrição..."); 
      
      // Define o ID atual para download posterior
      currentTranscriptionId = item.id;
      
      // Atualiza o título do modal
      $('#transcriptionTitle').text(`Transcrição: ${item.name || item.title}`);
      
      // Carrega a transcrição
      const response = await fetch(`${API_BASE_URL}/audio/transcription/${item.id}`, {
        headers: getAuthHeaders()
      });
      
      if (!response.ok) {
        throw new Error(`Erro ao carregar transcrição: ${response.status} ${response.statusText}`);
      }
      
      // Obtém o texto da transcrição
      const transcriptionText = await response.text();
      
      // Exibe o texto formatado no modal
      $('#transcriptionContent').text(transcriptionText);
      
      // Exibe o modal
      modal.style.display = "block";
      
      toggleLoading(false);
      
    } catch (error) {
      console.error('Erro:', error);
      toggleLoading(false);
      showError(`Erro ao carregar transcrição: ${error.message}`);
      if (error.message.includes('401')) authenticate();
    }
  }
  
  // Download da transcrição atual
  async function downloadTranscription() {
    if (!currentTranscriptionId) {
      showError('Nenhuma transcrição selecionada para download');
      return;
    }
    
    try {
      // Abre a URL da transcrição em uma nova aba para download
      window.open(`${API_BASE_URL}/audio/transcription/${currentTranscriptionId}`, '_blank');
    } catch (error) {
      console.error('Erro:', error);
      showError(`Erro ao baixar transcrição: ${error.message}`);
    }
  }
  
  // Verifica se o áudio já existe
  async function checkAudioExists(url) {
    if (!authToken) {
      showError('Erro de autenticação. Tentando reconectar...');
      return authenticate();
    }
    
    try {
      const response = await $.ajax({
        url: `${API_BASE_URL}/audio/check_exists?youtube_url=${encodeURIComponent(url)}`,
        method: 'GET',
        headers: getAuthHeaders()
      });
      
      return response;
    } catch (error) {
      console.error('Erro ao verificar existência do áudio:', error);
      throw error;
    }
  }
  
  async function downloadAudio() {
    if (!authToken) {
      showError('Erro de autenticação. Tentando reconectar...');
      return authenticate();
    }
    
    const youtubeUrl = $('#youtubeUrl').val().trim();
    const highQuality = $('#highQuality').is(':checked');
    
    if (!youtubeUrl) {
      showError('Por favor, insira uma URL do YouTube válida');
      return;
    }
    
    // Validação básica da URL
    if (!youtubeUrl.includes('youtube.com/') && !youtubeUrl.includes('youtu.be/')) {
      showError('URL do YouTube inválida');
      return;
    }
    
    try {
      toggleLoading(true, "Verificando se o áudio já existe..."); // Mostra o loading
      
      // Primeiro, verifica se o áudio já existe
      const existsCheck = await checkAudioExists(youtubeUrl);
      
      if (existsCheck.exists) {
        toggleLoading(false);
        showSuccess(`Áudio já foi baixado anteriormente: ${existsCheck.audio_info.title}`);
        
        // Navega para a aba de áudio e destaca o áudio existente
        $('.tab[data-tab="audio"]').click();
        
        // Tenta encontrar o áudio na lista
        const audioId = existsCheck.audio_info.id;
        setTimeout(() => {
          const audioElement = $(`.audio-item[data-id="${audioId}"]`);
          if (audioElement.length) {
            // Rola para o elemento
            const container = $('.audio-list');
            container.animate({
              scrollTop: audioElement.offset().top - container.offset().top + container.scrollTop()
            }, 500);
            
            // Destaca o elemento por um momento
            audioElement.addClass('highlight');
            setTimeout(() => {
              audioElement.removeClass('highlight');
            }, 2000);
          }
        }, 500);
        
        return;
      }
      
      // Se não existe, continua com o download
      toggleLoading(true, "Iniciando download de áudio..."); 
      
      const response = await $.ajax({
        url: `${API_BASE_URL}/audio/download`,
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        },
        data: JSON.stringify({
          url: youtubeUrl,
          high_quality: highQuality
        })
      });
      
      toggleLoading(false);
      
      if (response.status === 'processando') {
        showSuccess('Download de áudio iniciado em segundo plano. Veja a aba "Áudio" após a conclusão.');
        // Limpa o campo de URL
        $('#youtubeUrl').val('');
        
        // Programa uma atualização da lista de áudio após algum tempo
        setTimeout(() => {
          localStorage.removeItem(AUDIO_CACHE_KEY); // Invalida o cache
          loadAudioList(); // Recarrega a lista
        }, 10000); // Aguarda 10 segundos
      } else {
        showError('Falha ao iniciar o download de áudio');
      }
      
    } catch (error) {
      console.error('Erro:', error);
      toggleLoading(false);
      
      let errorMessage = 'Erro ao fazer download do áudio';
      if (error.responseJSON && error.responseJSON.detail) {
        errorMessage += `: ${error.responseJSON.detail}`;
      }
      
      showError(errorMessage);
      if (error.status === 401) authenticate();
    }
  }
  
  async function transcribeAudio(audio) {
    if (!authToken) {
      showError('Erro de autenticação. Tentando reconectar...');
      return authenticate();
    }
    
    if (!audio || !audio.id) {
      showError('Nenhum áudio selecionado para transcrição');
      return;
    }
    
    // Verifica o status atual da transcrição
    const transcriptionStatus = audio.transcription_status || "none";
    
    // Se já está concluída
    if (transcriptionStatus === "ended") {
      viewTranscription(audio);
      return;
    }
    
    // Se está em andamento
    if (transcriptionStatus === "started") {
      showInfo("Transcrição em andamento. Por favor, aguarde a conclusão.");
      return;
    }
    
    // Se teve erro anteriormente, confirma se deseja tentar novamente
    if (transcriptionStatus === "error" && !confirm("Houve um erro na transcrição anterior. Deseja tentar novamente?")) {
      return;
    }
    
    try {
      toggleLoading(true, "Iniciando transcrição de áudio..."); // Mostra o loading
      
      const response = await $.ajax({
        url: `${API_BASE_URL}/audio/transcribe`,
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        },
        data: JSON.stringify({
          file_id: audio.id,
          provider: "groq",  // Default provider
          language: "pt"     // Português
        })
      });
      
      toggleLoading(false);
      
      if (response.status === 'processing') {
        showSuccess('Transcrição iniciada em segundo plano. Isso pode levar alguns minutos.');
        
        // Atualiza o status na interface
        const updatedAudios = currentAudios.map(a => {
          if (a.id === audio.id) {
            return { ...a, transcription_status: "started" };
          }
          return a;
        });
        
        currentAudios = updatedAudios;
        saveToCache(currentAudios, null, AUDIO_CACHE_KEY);
        renderAudioList(currentAudios, $('#searchAudioInput').val());
        
        // Inicia verificação periódica do status
        startTranscriptionStatusCheck([{...audio, transcription_status: "started"}]);
      } else if (response.status === 'success') {
        showSuccess('Transcrição já existe! Carregando visualização...');
        
        // Atualiza o status na interface
        const updatedAudios = currentAudios.map(a => {
          if (a.id === audio.id) {
            return { ...a, transcription_status: "ended" };
          }
          return a;
        });
        
        currentAudios = updatedAudios;
        saveToCache(currentAudios, null, AUDIO_CACHE_KEY);
        renderAudioList(currentAudios, $('#searchAudioInput').val());
        
        // Mostrar a transcrição existente
        viewTranscription({...audio, transcription_status: "ended"});
      } else {
        showError('Falha ao iniciar a transcrição');
      }
      
    } catch (error) {
      console.error('Erro:', error);
      toggleLoading(false);
      
      let errorMessage = 'Erro ao transcrever áudio';
      if (error.responseJSON && error.responseJSON.detail) {
        errorMessage += `: ${error.responseJSON.detail}`;
      }
      
      showError(errorMessage);
      if (error.status === 401) authenticate();
    }
  }

  // Event listeners
  $('#videoPlayer').on('contextmenu', function (e) {
    e.preventDefault();
    return false;
  });

  let searchVideoTimeout;
  $('#searchVideoInput').on('input', function () {
    clearTimeout(searchVideoTimeout);
    const searchTerm = $(this).val();

    searchVideoTimeout = setTimeout(() => {
      filterVideos(searchTerm);
    }, 300);
  });
  
  let searchAudioTimeout;
  $('#searchAudioInput').on('input', function () {
    clearTimeout(searchAudioTimeout);
    const searchTerm = $(this).val();

    searchAudioTimeout = setTimeout(() => {
      filterAudios(searchTerm);
    }, 300);
  });

  $('.sort-button').click(function () {
    const sortBy = $(this).data('sort');
    $('.sort-button').removeClass('active');
    $(this).addClass('active');
    loadVideoList(sortBy);
  });
  
  // Navegação por abas
  $('.tab').click(function() {
    // Remove a classe active de todas as abas e conteúdos
    $('.tab').removeClass('active');
    $('.tab-content').removeClass('active');
    
    // Adiciona a classe active na aba clicada
    $(this).addClass('active');
    
    // Exibe o conteúdo correspondente
    const tabId = $(this).data('tab');
    $(`#${tabId}-tab`).addClass('active');
    
    // Recarrega os dados se necessário
    if (tabId === 'audio') {
      loadAudioList();
    } else if (tabId === 'videos') {
      loadVideoList($('.sort-button.active').data('sort'));
    }
  });
  
  // Download de áudio
  $('#downloadAudioBtn').click(function() {
    downloadAudio();
  });
  
  // Download de transcrição do modal
  $('#downloadTranscriptionBtn').click(function() {
    downloadTranscription();
  });

  // Inicia a aplicação
  authenticate();
});