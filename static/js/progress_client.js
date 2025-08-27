/**
 * Advanced Progress Client - FASE 3 JavaScript Client
 * Cliente JavaScript avançado para comunicação WebSocket/SSE em tempo real
 */

class AdvancedProgressClient {
    constructor(options = {}) {
        // Configurações
        this.config = {
            websocketUrl: options.websocketUrl || `ws://${window.location.host}/ws/progress`,
            sseUrl: options.sseUrl || '/api/progress/stream',
            fallbackMode: options.fallbackMode || 'sse', // 'sse' ou 'polling'
            reconnectInterval: options.reconnectInterval || 3000,
            maxReconnectAttempts: options.maxReconnectAttempts || 10,
            heartbeatInterval: options.heartbeatInterval || 30000,
            token: options.token || null,
            debug: options.debug || false
        };

        // Estado da conexão
        this.state = {
            connected: false,
            reconnectAttempts: 0,
            lastMessageTime: null,
            clientId: null,
            connectionType: null, // 'websocket', 'sse', ou 'polling'
            statistics: {
                messagesReceived: 0,
                messagesLost: 0,
                averageLatency: 0,
                connectionUptime: 0
            }
        };

        // Conexões
        this.websocket = null;
        this.eventSource = null;
        this.pollingInterval = null;

        // Subscrições
        this.subscriptions = {
            tasks: new Set(),
            channels: new Set(['progress', 'system']),
            callbacks: new Map()
        };

        // Timers
        this.heartbeatTimer = null;
        this.reconnectTimer = null;
        this.latencyTestTimer = null;

        // Cache e buffer
        this.messageBuffer = [];
        this.lastProgressCache = new Map();

        this.log('AdvancedProgressClient initialized', this.config);
    }

    /**
     * Conecta ao servidor usando WebSocket como primeira opção
     */
    async connect() {
        try {
            this.log('Attempting connection...');
            
            // Tentar WebSocket primeiro
            if (await this.tryWebSocketConnection()) {
                this.state.connectionType = 'websocket';
                this.log('Connected via WebSocket');
                return true;
            }

            // Fallback para SSE
            if (this.config.fallbackMode === 'sse' && await this.trySSEConnection()) {
                this.state.connectionType = 'sse';
                this.log('Connected via SSE');
                return true;
            }

            // Último recurso: polling
            if (await this.tryPollingConnection()) {
                this.state.connectionType = 'polling';
                this.log('Connected via Polling');
                return true;
            }

            throw new Error('All connection methods failed');

        } catch (error) {
            this.log('Connection failed', error);
            this.onConnectionError(error);
            return false;
        }
    }

    /**
     * Tenta conexão WebSocket
     */
    async tryWebSocketConnection() {
        return new Promise((resolve) => {
            try {
                const url = new URL(this.config.websocketUrl);
                if (this.config.token) {
                    url.searchParams.set('token', this.config.token);
                }

                this.websocket = new WebSocket(url.toString());
                
                const timeout = setTimeout(() => {
                    this.websocket?.close();
                    resolve(false);
                }, 5000);

                this.websocket.onopen = () => {
                    clearTimeout(timeout);
                    this.onWebSocketConnected();
                    resolve(true);
                };

                this.websocket.onerror = (error) => {
                    clearTimeout(timeout);
                    this.log('WebSocket error', error);
                    resolve(false);
                };

                this.websocket.onclose = (event) => {
                    clearTimeout(timeout);
                    this.onConnectionClosed('websocket', event);
                    resolve(false);
                };

                this.websocket.onmessage = (event) => {
                    this.onWebSocketMessage(event);
                };

            } catch (error) {
                this.log('WebSocket setup error', error);
                resolve(false);
            }
        });
    }

    /**
     * Tenta conexão SSE
     */
    async trySSEConnection() {
        return new Promise((resolve) => {
            try {
                let url = this.config.sseUrl;
                const params = new URLSearchParams();
                
                if (this.config.token) {
                    params.set('token', this.config.token);
                }
                
                params.set('channels', Array.from(this.subscriptions.channels).join(','));
                
                if (params.toString()) {
                    url += '?' + params.toString();
                }

                this.eventSource = new EventSource(url);
                
                const timeout = setTimeout(() => {
                    this.eventSource?.close();
                    resolve(false);
                }, 5000);

                this.eventSource.onopen = () => {
                    clearTimeout(timeout);
                    this.onSSEConnected();
                    resolve(true);
                };

                this.eventSource.onerror = (error) => {
                    clearTimeout(timeout);
                    this.log('SSE error', error);
                    this.eventSource?.close();
                    resolve(false);
                };

                // Event listeners para diferentes tipos de eventos SSE
                this.eventSource.addEventListener('connected', (event) => {
                    this.onSSEMessage('connected', event);
                });

                this.eventSource.addEventListener('progress_update', (event) => {
                    this.onSSEMessage('progress_update', event);
                });

                this.eventSource.addEventListener('stage_update', (event) => {
                    this.onSSEMessage('stage_update', event);
                });

                this.eventSource.addEventListener('task_complete', (event) => {
                    this.onSSEMessage('task_complete', event);
                });

                this.eventSource.addEventListener('task_error', (event) => {
                    this.onSSEMessage('task_error', event);
                });

                this.eventSource.addEventListener('system_alert', (event) => {
                    this.onSSEMessage('system_alert', event);
                });

                this.eventSource.addEventListener('heartbeat', (event) => {
                    this.onSSEMessage('heartbeat', event);
                });

            } catch (error) {
                this.log('SSE setup error', error);
                resolve(false);
            }
        });
    }

    /**
     * Tenta conexão via polling
     */
    async tryPollingConnection() {
        try {
            // Fazer uma requisição de teste
            const response = await fetch('/api/dashboard/data');
            if (!response.ok) {
                throw new Error('Dashboard API not available');
            }

            this.startPolling();
            this.onPollingConnected();
            return true;

        } catch (error) {
            this.log('Polling connection failed', error);
            return false;
        }
    }

    /**
     * Inicia polling mode
     */
    startPolling() {
        this.pollingInterval = setInterval(async () => {
            try {
                const response = await fetch('/api/dashboard/data');
                if (response.ok) {
                    const data = await response.json();
                    this.onPollingData(data);
                } else {
                    throw new Error('Polling request failed');
                }
            } catch (error) {
                this.log('Polling error', error);
                this.onConnectionError(error);
            }
        }, 5000); // 5 segundos
    }

    /**
     * Handlers de conexão WebSocket
     */
    onWebSocketConnected() {
        this.state.connected = true;
        this.state.reconnectAttempts = 0;
        this.startHeartbeat();
        this.startLatencyTest();
        this.sendSubscriptions();
        this.onConnected('websocket');
    }

    onWebSocketMessage(event) {
        try {
            const message = JSON.parse(event.data);
            this.processMessage(message);
        } catch (error) {
            this.log('Error parsing WebSocket message', error);
        }
    }

    /**
     * Handlers de conexão SSE
     */
    onSSEConnected() {
        this.state.connected = true;
        this.state.reconnectAttempts = 0;
        this.startHeartbeat();
        this.onConnected('sse');
    }

    onSSEMessage(type, event) {
        try {
            const data = JSON.parse(event.data);
            this.processMessage({ type, data, timestamp: data.timestamp });
        } catch (error) {
            this.log('Error parsing SSE message', error);
        }
    }

    /**
     * Handlers de conexão Polling
     */
    onPollingConnected() {
        this.state.connected = true;
        this.state.reconnectAttempts = 0;
        this.onConnected('polling');
    }

    onPollingData(data) {
        // Simular mensagens baseadas em dados do polling
        this.processMessage({
            type: 'dashboard_update',
            data: data,
            timestamp: new Date().toISOString()
        });
    }

    /**
     * Processa mensagens recebidas
     */
    processMessage(message) {
        this.state.statistics.messagesReceived++;
        this.state.lastMessageTime = Date.now();

        // Calcular latência se disponível
        if (message.data?.timestamp) {
            const messageTime = new Date(message.data.timestamp).getTime();
            const currentTime = Date.now();
            const latency = currentTime - messageTime;
            this.updateLatencyStats(latency);
        }

        // Processar por tipo de mensagem
        switch (message.type) {
            case 'connected':
                this.handleConnectedMessage(message.data);
                break;
            case 'progress_update':
                this.handleProgressUpdate(message.data);
                break;
            case 'stage_update':
                this.handleStageUpdate(message.data);
                break;
            case 'task_complete':
                this.handleTaskComplete(message.data);
                break;
            case 'task_error':
                this.handleTaskError(message.data);
                break;
            case 'system_alert':
                this.handleSystemAlert(message.data);
                break;
            case 'heartbeat':
            case 'pong':
                this.handleHeartbeat(message.data);
                break;
            case 'dashboard_update':
                this.handleDashboardUpdate(message.data);
                break;
            case 'error':
                this.handleError(message.data);
                break;
            default:
                this.log('Unknown message type', message.type);
        }

        // Executar callbacks registrados
        this.executeCallbacks(message.type, message.data);
    }

    /**
     * Handlers específicos para tipos de mensagem
     */
    handleConnectedMessage(data) {
        this.state.clientId = data.client_id;
        this.log('Client connected with ID:', this.state.clientId);
    }

    handleProgressUpdate(data) {
        const taskId = data.task_id;
        const progress = {
            task_id: taskId,
            progress: data.progress,
            current_stage: data.current_stage,
            eta_seconds: data.eta_seconds,
            speed_bps: data.average_speed_bps,
            stages: data.stages || {},
            timestamp: data.timestamp || new Date().toISOString()
        };

        // Cache para evitar updates desnecessários
        const cached = this.lastProgressCache.get(taskId);
        if (!cached || Math.abs(cached.progress - progress.progress) >= 0.1) {
            this.lastProgressCache.set(taskId, progress);
            this.onProgress(progress);
        }
    }

    handleStageUpdate(data) {
        this.onStageUpdate({
            task_id: data.task_id,
            stage: data.updated_stage,
            stage_progress: data.stage_details,
            overall_progress: data.progress,
            timestamp: data.timestamp || new Date().toISOString()
        });
    }

    handleTaskComplete(data) {
        this.onTaskComplete({
            task_id: data.task_id,
            duration: data.total_duration,
            final_progress: data.final_progress,
            timestamp: data.timestamp || new Date().toISOString()
        });
        
        // Limpar cache
        this.lastProgressCache.delete(data.task_id);
    }

    handleTaskError(data) {
        this.onTaskError({
            task_id: data.task_id,
            error: data.error,
            stage: data.current_stage,
            timestamp: data.timestamp || new Date().toISOString()
        });
    }

    handleSystemAlert(data) {
        this.onSystemAlert({
            level: data.alert_type,
            message: data.message,
            data: data.data,
            timestamp: data.timestamp || new Date().toISOString()
        });
    }

    handleHeartbeat(data) {
        // Atualizar estatísticas de uptime
        if (data.timestamp) {
            const serverTime = new Date(data.timestamp).getTime();
            const clientTime = Date.now();
            const timeDiff = Math.abs(clientTime - serverTime);
            
            if (timeDiff > 5000) { // 5 segundos de diferença
                this.log('Clock skew detected', { timeDiff });
            }
        }
    }

    handleDashboardUpdate(data) {
        this.onDashboardUpdate(data);
    }

    handleError(data) {
        this.log('Server error', data);
        this.onError(data);
    }

    /**
     * Gerenciamento de subscrições
     */
    subscribeToTask(taskId) {
        this.subscriptions.tasks.add(taskId);
        
        if (this.state.connected && this.state.connectionType === 'websocket') {
            this.sendMessage({
                type: 'subscribe',
                data: {
                    task_ids: [taskId]
                }
            });
        }
    }

    unsubscribeFromTask(taskId) {
        this.subscriptions.tasks.delete(taskId);
        this.lastProgressCache.delete(taskId);
        
        if (this.state.connected && this.state.connectionType === 'websocket') {
            this.sendMessage({
                type: 'unsubscribe',
                data: {
                    task_ids: [taskId]
                }
            });
        }
    }

    subscribeToChannel(channel) {
        this.subscriptions.channels.add(channel);
        
        if (this.state.connected && this.state.connectionType === 'websocket') {
            this.sendMessage({
                type: 'subscribe',
                data: {
                    channels: [channel]
                }
            });
        }
    }

    /**
     * Envia subscrições atuais para o servidor
     */
    sendSubscriptions() {
        if (this.state.connectionType !== 'websocket') return;

        this.sendMessage({
            type: 'subscribe',
            data: {
                task_ids: Array.from(this.subscriptions.tasks),
                channels: Array.from(this.subscriptions.channels)
            }
        });
    }

    /**
     * Envia mensagem para o servidor (WebSocket apenas)
     */
    sendMessage(message) {
        if (this.websocket?.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify(message));
        }
    }

    /**
     * Sistema de heartbeat
     */
    startHeartbeat() {
        if (this.heartbeatTimer) return;

        this.heartbeatTimer = setInterval(() => {
            if (this.state.connectionType === 'websocket') {
                this.sendMessage({
                    type: 'ping',
                    data: {
                        timestamp: new Date().toISOString()
                    }
                });
            }
            
            // Verificar se a conexão ainda está ativa
            const timeSinceLastMessage = Date.now() - (this.state.lastMessageTime || 0);
            if (timeSinceLastMessage > 60000) { // 1 minuto sem mensagens
                this.log('Connection appears stale, attempting reconnection');
                this.reconnect();
            }
        }, this.config.heartbeatInterval);
    }

    stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    /**
     * Teste de latência
     */
    startLatencyTest() {
        if (this.latencyTestTimer || this.state.connectionType !== 'websocket') return;

        this.latencyTestTimer = setInterval(() => {
            const startTime = performance.now();
            this.sendMessage({
                type: 'ping',
                data: {
                    timestamp: new Date().toISOString(),
                    latency_test: startTime
                }
            });
        }, 60000); // A cada minuto
    }

    stopLatencyTest() {
        if (this.latencyTestTimer) {
            clearInterval(this.latencyTestTimer);
            this.latencyTestTimer = null;
        }
    }

    updateLatencyStats(latency) {
        const stats = this.state.statistics;
        const alpha = 0.1; // Smoothing factor para média móvel
        
        if (stats.averageLatency === 0) {
            stats.averageLatency = latency;
        } else {
            stats.averageLatency = (alpha * latency) + ((1 - alpha) * stats.averageLatency);
        }
    }

    /**
     * Reconexão automática
     */
    onConnectionClosed(type, event) {
        this.log(`${type} connection closed`, event);
        this.state.connected = false;
        this.stopHeartbeat();
        this.stopLatencyTest();
        
        if (this.state.reconnectAttempts < this.config.maxReconnectAttempts) {
            this.scheduleReconnect();
        } else {
            this.log('Max reconnection attempts reached');
            this.onConnectionError(new Error('Max reconnection attempts exceeded'));
        }
    }

    scheduleReconnect() {
        if (this.reconnectTimer) return;

        const delay = Math.min(
            this.config.reconnectInterval * Math.pow(2, this.state.reconnectAttempts),
            30000 // Máximo 30 segundos
        );

        this.log(`Scheduling reconnection attempt ${this.state.reconnectAttempts + 1} in ${delay}ms`);

        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.reconnect();
        }, delay);
    }

    async reconnect() {
        this.state.reconnectAttempts++;
        this.cleanup();
        
        const connected = await this.connect();
        if (!connected) {
            this.scheduleReconnect();
        }
    }

    /**
     * Sistema de callbacks
     */
    on(event, callback) {
        if (!this.subscriptions.callbacks.has(event)) {
            this.subscriptions.callbacks.set(event, []);
        }
        this.subscriptions.callbacks.get(event).push(callback);
    }

    off(event, callback) {
        if (this.subscriptions.callbacks.has(event)) {
            const callbacks = this.subscriptions.callbacks.get(event);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }

    executeCallbacks(event, data) {
        const callbacks = this.subscriptions.callbacks.get(event) || [];
        callbacks.forEach(callback => {
            try {
                callback(data);
            } catch (error) {
                this.log('Callback error', error);
            }
        });
    }

    /**
     * Event handlers (podem ser sobrescritos)
     */
    onConnected(connectionType) {
        this.log(`Connected via ${connectionType}`);
        this.executeCallbacks('connected', { connectionType });
    }

    onConnectionError(error) {
        this.log('Connection error', error);
        this.executeCallbacks('connection_error', error);
    }

    onProgress(progress) {
        this.executeCallbacks('progress', progress);
    }

    onStageUpdate(stageData) {
        this.executeCallbacks('stage_update', stageData);
    }

    onTaskComplete(taskData) {
        this.executeCallbacks('task_complete', taskData);
    }

    onTaskError(errorData) {
        this.executeCallbacks('task_error', errorData);
    }

    onSystemAlert(alert) {
        this.executeCallbacks('system_alert', alert);
    }

    onDashboardUpdate(data) {
        this.executeCallbacks('dashboard_update', data);
    }

    onError(error) {
        this.executeCallbacks('error', error);
    }

    /**
     * Utilitários
     */
    getStatistics() {
        return {
            ...this.state.statistics,
            connectionType: this.state.connectionType,
            connected: this.state.connected,
            reconnectAttempts: this.state.reconnectAttempts,
            subscriptions: {
                tasks: Array.from(this.subscriptions.tasks),
                channels: Array.from(this.subscriptions.channels)
            }
        };
    }

    getConnectionInfo() {
        return {
            connected: this.state.connected,
            connectionType: this.state.connectionType,
            clientId: this.state.clientId,
            reconnectAttempts: this.state.reconnectAttempts,
            lastMessageTime: this.state.lastMessageTime
        };
    }

    /**
     * Cleanup
     */
    cleanup() {
        // Fechar conexões
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }

        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }

        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }

        // Limpar timers
        this.stopHeartbeat();
        this.stopLatencyTest();
        
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        // Resetar estado
        this.state.connected = false;
    }

    disconnect() {
        this.log('Disconnecting...');
        this.cleanup();
        this.executeCallbacks('disconnected', {});
    }

    log(message, data = null) {
        if (this.config.debug) {
            console.log(`[AdvancedProgressClient] ${message}`, data || '');
        }
    }
}

/**
 * Progress UI Manager - Gerencia a interface de progresso
 */
class ProgressUIManager {
    constructor(client, options = {}) {
        this.client = client;
        this.options = {
            progressSelector: options.progressSelector || '.progress-item',
            dashboardSelector: options.dashboardSelector || '#dashboard',
            alertsSelector: options.alertsSelector || '#alerts',
            animate: options.animate !== false,
            showETA: options.showETA !== false,
            showSpeed: options.showSpeed !== false,
            ...options
        };

        this.progressBars = new Map();
        this.alertsContainer = null;

        this.init();
    }

    init() {
        // Setup event listeners
        this.client.on('progress', (data) => this.updateProgressBar(data));
        this.client.on('stage_update', (data) => this.updateStageInfo(data));
        this.client.on('task_complete', (data) => this.onTaskComplete(data));
        this.client.on('task_error', (data) => this.onTaskError(data));
        this.client.on('system_alert', (data) => this.showAlert(data));
        this.client.on('dashboard_update', (data) => this.updateDashboard(data));

        // Setup alerts container
        this.setupAlertsContainer();
    }

    updateProgressBar(data) {
        const container = this.findOrCreateProgressContainer(data.task_id);
        if (!container) return;

        const progressBar = container.querySelector('.progress-bar');
        const progressText = container.querySelector('.progress-text');
        const stageText = container.querySelector('.stage-text');
        const etaText = container.querySelector('.eta-text');
        const speedText = container.querySelector('.speed-text');

        if (progressBar) {
            const percentage = Math.round(data.progress);
            progressBar.style.width = `${percentage}%`;
            
            if (this.options.animate) {
                progressBar.style.transition = 'width 0.5s ease-in-out';
            }
        }

        if (progressText) {
            progressText.textContent = `${Math.round(data.progress)}%`;
        }

        if (stageText && data.current_stage) {
            stageText.textContent = this.formatStageName(data.current_stage);
        }

        if (etaText && data.eta_seconds && this.options.showETA) {
            etaText.textContent = `ETA: ${this.formatDuration(data.eta_seconds)}`;
        }

        if (speedText && data.speed_bps && this.options.showSpeed) {
            speedText.textContent = `${this.formatSpeed(data.speed_bps)}`;
        }

        // Update stages if available
        if (data.stages) {
            this.updateStagesProgress(container, data.stages);
        }
    }

    updateStageInfo(data) {
        const container = this.findProgressContainer(data.task_id);
        if (!container) return;

        const stageText = container.querySelector('.stage-text');
        if (stageText) {
            stageText.textContent = this.formatStageName(data.stage);
        }

        // Update specific stage progress if stages container exists
        if (data.stage_progress) {
            this.updateSpecificStage(container, data.stage, data.stage_progress);
        }
    }

    updateStagesProgress(container, stages) {
        const stagesContainer = container.querySelector('.stages-container');
        if (!stagesContainer) return;

        Object.entries(stages).forEach(([stageName, stageData]) => {
            const stageElement = stagesContainer.querySelector(`[data-stage="${stageName}"]`);
            if (stageElement) {
                const stageBar = stageElement.querySelector('.stage-bar');
                const stageText = stageElement.querySelector('.stage-text');

                if (stageBar) {
                    stageBar.style.width = `${stageData.percentage}%`;
                }

                if (stageText) {
                    stageText.textContent = `${Math.round(stageData.percentage)}%`;
                }
            }
        });
    }

    onTaskComplete(data) {
        const container = this.findProgressContainer(data.task_id);
        if (container) {
            container.classList.add('completed');
            
            const progressBar = container.querySelector('.progress-bar');
            if (progressBar) {
                progressBar.style.width = '100%';
                progressBar.classList.add('success');
            }

            const statusText = container.querySelector('.status-text');
            if (statusText) {
                statusText.textContent = 'Completed';
                statusText.classList.add('success');
            }

            // Auto-hide após 5 segundos
            setTimeout(() => {
                if (container.parentNode) {
                    container.style.opacity = '0';
                    setTimeout(() => {
                        container.remove();
                    }, 500);
                }
            }, 5000);
        }

        // Show success notification
        this.showNotification(`Task ${data.task_id} completed successfully!`, 'success');
    }

    onTaskError(data) {
        const container = this.findProgressContainer(data.task_id);
        if (container) {
            container.classList.add('error');
            
            const progressBar = container.querySelector('.progress-bar');
            if (progressBar) {
                progressBar.classList.add('error');
            }

            const statusText = container.querySelector('.status-text');
            if (statusText) {
                statusText.textContent = `Error: ${data.error}`;
                statusText.classList.add('error');
            }
        }

        // Show error notification
        this.showNotification(`Task ${data.task_id} failed: ${data.error}`, 'error');
    }

    showAlert(alert) {
        const alertElement = this.createAlertElement(alert);
        if (this.alertsContainer && alertElement) {
            this.alertsContainer.appendChild(alertElement);
            
            // Auto-remove low priority alerts
            if (alert.level === 'info') {
                setTimeout(() => {
                    alertElement.remove();
                }, 10000);
            }
        }
    }

    updateDashboard(data) {
        // Update dashboard overview
        const dashboardElement = document.querySelector(this.options.dashboardSelector);
        if (!dashboardElement) return;

        // Update summary stats
        this.updateSummaryStats(dashboardElement, data.summary || {});
        
        // Update active tasks list
        this.updateActiveTasksList(dashboardElement, data.active_tasks || []);
        
        // Update system metrics
        this.updateSystemMetrics(dashboardElement, data.system_metrics || {});
    }

    // Helper methods
    findOrCreateProgressContainer(taskId) {
        let container = this.findProgressContainer(taskId);
        
        if (!container) {
            container = this.createProgressContainer(taskId);
        }
        
        return container;
    }

    findProgressContainer(taskId) {
        return document.querySelector(`[data-task-id="${taskId}"]`);
    }

    createProgressContainer(taskId) {
        const template = this.getProgressTemplate(taskId);
        const parentContainer = document.querySelector(this.options.progressSelector)?.parentNode;
        
        if (parentContainer && template) {
            parentContainer.appendChild(template);
            return template;
        }
        
        return null;
    }

    getProgressTemplate(taskId) {
        const template = document.createElement('div');
        template.className = 'progress-item';
        template.setAttribute('data-task-id', taskId);
        
        template.innerHTML = `
            <div class="progress-header">
                <span class="task-id">${taskId}</span>
                <span class="progress-text">0%</span>
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar"></div>
            </div>
            <div class="progress-info">
                <span class="stage-text"></span>
                <span class="eta-text"></span>
                <span class="speed-text"></span>
                <span class="status-text"></span>
            </div>
            <div class="stages-container"></div>
        `;
        
        return template;
    }

    createAlertElement(alert) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${alert.level}`;
        
        alertDiv.innerHTML = `
            <div class="alert-content">
                <strong>${alert.level.toUpperCase()}</strong>: ${alert.message}
                <small>${new Date(alert.timestamp).toLocaleTimeString()}</small>
            </div>
            <button class="alert-close">&times;</button>
        `;
        
        const closeBtn = alertDiv.querySelector('.alert-close');
        closeBtn.addEventListener('click', () => alertDiv.remove());
        
        return alertDiv;
    }

    setupAlertsContainer() {
        this.alertsContainer = document.querySelector(this.options.alertsSelector);
        
        if (!this.alertsContainer) {
            this.alertsContainer = document.createElement('div');
            this.alertsContainer.id = 'alerts';
            this.alertsContainer.className = 'alerts-container';
            document.body.appendChild(this.alertsContainer);
        }
    }

    showNotification(message, type = 'info') {
        // Create temporary notification
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.classList.add('show');
        }, 100);
        
        // Auto-remove
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }

    // Utility formatters
    formatStageName(stage) {
        return stage.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    formatDuration(seconds) {
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
        return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
    }

    formatSpeed(bytesPerSecond) {
        const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
        let value = bytesPerSecond;
        let unitIndex = 0;
        
        while (value >= 1024 && unitIndex < units.length - 1) {
            value /= 1024;
            unitIndex++;
        }
        
        return `${value.toFixed(1)} ${units[unitIndex]}`;
    }

    updateSummaryStats(dashboard, summary) {
        // Implementation would update dashboard summary statistics
        const summaryElements = dashboard.querySelectorAll('[data-summary-stat]');
        summaryElements.forEach(element => {
            const statName = element.getAttribute('data-summary-stat');
            if (summary[statName] !== undefined) {
                element.textContent = summary[statName];
            }
        });
    }

    updateActiveTasksList(dashboard, activeTasks) {
        const tasksContainer = dashboard.querySelector('.active-tasks-list');
        if (!tasksContainer) return;

        // Clear and rebuild list
        tasksContainer.innerHTML = '';
        
        activeTasks.forEach(task => {
            const taskElement = document.createElement('div');
            taskElement.className = 'active-task-item';
            taskElement.innerHTML = `
                <div class="task-info">
                    <span class="task-id">${task.task_id}</span>
                    <span class="task-type">${task.task_type}</span>
                    <span class="task-progress">${Math.round(task.progress)}%</span>
                </div>
                <div class="task-bar">
                    <div class="task-progress-bar" style="width: ${task.progress}%"></div>
                </div>
            `;
            
            tasksContainer.appendChild(taskElement);
        });
    }

    updateSystemMetrics(dashboard, metrics) {
        const metricsContainer = dashboard.querySelector('.system-metrics');
        if (!metricsContainer) return;

        Object.entries(metrics).forEach(([metricName, metricData]) => {
            const metricElement = metricsContainer.querySelector(`[data-metric="${metricName}"]`);
            if (metricElement) {
                const valueElement = metricElement.querySelector('.metric-value');
                const unitElement = metricElement.querySelector('.metric-unit');
                
                if (valueElement) {
                    valueElement.textContent = metricData.current || 0;
                }
                
                if (unitElement && metricData.unit) {
                    unitElement.textContent = metricData.unit;
                }
            }
        });
    }
}

// Export para uso global
window.AdvancedProgressClient = AdvancedProgressClient;
window.ProgressUIManager = ProgressUIManager;