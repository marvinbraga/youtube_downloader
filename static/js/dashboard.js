/**
 * Progress Dashboard Application - FASE 3 Main Dashboard Controller
 * Gerencia toda a interface do dashboard e integração com o cliente de progresso
 */

class ProgressDashboardApp {
    constructor(options = {}) {
        this.options = {
            apiBaseUrl: options.apiBaseUrl || '/api',
            websocketUrl: options.websocketUrl || `ws://${window.location.host}/ws/progress`,
            sseUrl: options.sseUrl || '/api/progress/stream',
            refreshInterval: options.refreshInterval || 30000, // 30 segundos
            debug: options.debug || false,
            ...options
        };

        // Estado da aplicação
        this.state = {
            initialized: false,
            dashboardData: null,
            selectedTasks: new Set(),
            activeTab: 'overview',
            chartInstances: new Map(),
            refreshTimer: null
        };

        // Componentes
        this.client = null;
        this.uiManager = null;
        this.chartManager = null;

        // Cache de elementos DOM
        this.elements = {};

        this.log('ProgressDashboardApp initialized', this.options);
    }

    /**
     * Inicializa a aplicação
     */
    async init() {
        try {
            this.showLoading('Initializing dashboard...');

            // Cachear elementos DOM
            this.cacheElements();

            // Configurar event listeners
            this.setupEventListeners();

            // Inicializar cliente de progresso
            await this.initProgressClient();

            // Inicializar gerenciador de UI
            this.initUIManager();

            // Inicializar gerenciador de gráficos
            this.initChartManager();

            // Carregar dados inicial
            await this.loadInitialData();

            // Iniciar atualizações periódicas
            this.startPeriodicRefresh();

            this.state.initialized = true;
            this.hideLoading();

            this.log('Dashboard initialized successfully');
            this.showToast('Dashboard connected successfully!', 'success');

        } catch (error) {
            this.log('Dashboard initialization failed', error);
            this.hideLoading();
            this.showToast('Failed to initialize dashboard', 'error');
        }
    }

    /**
     * Cachear elementos DOM para melhor performance
     */
    cacheElements() {
        this.elements = {
            // Header elements
            connectionIndicator: document.getElementById('connection-indicator'),
            connectionText: document.getElementById('connection-text'),
            refreshBtn: document.getElementById('refresh-btn'),
            exportBtn: document.getElementById('export-btn'),

            // Summary cards
            summaryCards: document.querySelectorAll('[data-summary-stat]'),

            // Active tasks
            activeTasksList: document.getElementById('active-tasks-list'),
            activeTasksEmpty: document.getElementById('active-tasks-empty'),

            // Metrics
            metricsGrid: document.querySelector('.metrics-grid'),
            metricItems: document.querySelectorAll('[data-metric]'),

            // Chart
            performanceChart: document.getElementById('performance-chart'),
            chartMetricSelector: document.getElementById('chart-metric-selector'),
            chartTimerangeSelector: document.getElementById('chart-timerange-selector'),

            // Alerts
            alertsList: document.getElementById('alerts-list'),
            alertsEmpty: document.getElementById('alerts-empty'),
            alertCount: document.getElementById('alert-count'),
            clearAlertsBtn: document.getElementById('clear-alerts'),

            // Recent tasks
            recentTasksList: document.getElementById('recent-tasks-list'),
            recentTasksEmpty: document.getElementById('recent-tasks-empty'),

            // Health status
            healthItems: document.querySelectorAll('.health-item'),
            uptimeStats: document.getElementById('uptime-stats'),
            systemUptime: document.getElementById('system-uptime'),
            totalRequests: document.getElementById('total-requests'),
            avgResponse: document.getElementById('avg-response'),

            // Modal
            taskDetailsModal: document.getElementById('task-details-modal'),
            taskDetailsContent: document.getElementById('task-details-content'),
            closeTaskModal: document.getElementById('close-task-modal'),

            // Loading
            loadingOverlay: document.getElementById('loading-overlay'),
            toastContainer: document.getElementById('toast-container')
        };
    }

    /**
     * Configurar event listeners
     */
    setupEventListeners() {
        // Header actions
        this.elements.refreshBtn?.addEventListener('click', () => this.refreshData());
        this.elements.exportBtn?.addEventListener('click', () => this.exportData());

        // Chart controls
        this.elements.chartMetricSelector?.addEventListener('change', (e) => {
            this.updateChart(e.target.value);
        });
        this.elements.chartTimerangeSelector?.addEventListener('change', (e) => {
            this.updateChart(null, parseInt(e.target.value));
        });

        // Alerts
        this.elements.clearAlertsBtn?.addEventListener('click', () => this.clearAlerts());

        // Modal
        this.elements.closeTaskModal?.addEventListener('click', () => this.hideTaskModal());
        this.elements.taskDetailsModal?.addEventListener('click', (e) => {
            if (e.target === this.elements.taskDetailsModal) {
                this.hideTaskModal();
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));

        // Panel collapse/expand
        document.querySelectorAll('[id^="collapse-"]').forEach(btn => {
            btn.addEventListener('click', (e) => this.togglePanel(e.target));
        });

        // Health refresh
        document.getElementById('refresh-health')?.addEventListener('click', () => {
            this.refreshHealthStatus();
        });

        // Window resize
        window.addEventListener('resize', () => this.handleWindowResize());
    }

    /**
     * Inicializar cliente de progresso
     */
    async initProgressClient() {
        this.client = new AdvancedProgressClient({
            websocketUrl: this.options.websocketUrl,
            sseUrl: this.options.sseUrl,
            token: this.getAuthToken(),
            debug: this.options.debug,
            reconnectInterval: 3000,
            maxReconnectAttempts: 10
        });

        // Setup event listeners para conexão
        this.client.on('connected', (data) => {
            this.updateConnectionStatus(true, data.connectionType);
        });

        this.client.on('connection_error', (error) => {
            this.updateConnectionStatus(false);
            this.log('Connection error', error);
        });

        this.client.on('disconnected', () => {
            this.updateConnectionStatus(false);
        });

        // Setup listeners para dados
        this.client.on('dashboard_update', (data) => {
            this.handleDashboardUpdate(data);
        });

        this.client.on('progress', (data) => {
            this.handleProgressUpdate(data);
        });

        this.client.on('task_complete', (data) => {
            this.handleTaskComplete(data);
        });

        this.client.on('task_error', (data) => {
            this.handleTaskError(data);
        });

        this.client.on('system_alert', (data) => {
            this.handleSystemAlert(data);
        });

        // Conectar
        await this.client.connect();
    }

    /**
     * Inicializar gerenciador de UI
     */
    initUIManager() {
        this.uiManager = new ProgressUIManager(this.client, {
            progressSelector: '.active-task-item',
            dashboardSelector: '.dashboard-main',
            alertsSelector: '#alerts-list',
            animate: true,
            showETA: true,
            showSpeed: true
        });
    }

    /**
     * Inicializar gerenciador de gráficos
     */
    initChartManager() {
        this.chartManager = new ChartManager();
        
        if (this.elements.performanceChart) {
            const defaultMetric = this.elements.chartMetricSelector?.value || 'websocket_latency';
            const defaultTimerange = parseInt(this.elements.chartTimerangeSelector?.value) || 1;
            
            this.initPerformanceChart(defaultMetric, defaultTimerange);
        }
    }

    /**
     * Carregar dados inicial
     */
    async loadInitialData() {
        try {
            const response = await fetch(`${this.options.apiBaseUrl}/dashboard/data`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.handleDashboardUpdate(data);
            
            // Subscrever a canais relevantes
            this.client.subscribeToChannel('system');
            this.client.subscribeToChannel('progress');

        } catch (error) {
            this.log('Failed to load initial data', error);
            this.showToast('Failed to load dashboard data', 'error');
        }
    }

    /**
     * Iniciar atualizações periódicas
     */
    startPeriodicRefresh() {
        this.state.refreshTimer = setInterval(() => {
            this.refreshData();
        }, this.options.refreshInterval);
    }

    /**
     * Parar atualizações periódicas
     */
    stopPeriodicRefresh() {
        if (this.state.refreshTimer) {
            clearInterval(this.state.refreshTimer);
            this.state.refreshTimer = null;
        }
    }

    /**
     * Atualizar status da conexão
     */
    updateConnectionStatus(connected, connectionType = null) {
        const indicator = this.elements.connectionIndicator;
        const text = this.elements.connectionText;

        if (!indicator || !text) return;

        if (connected) {
            indicator.className = 'status-indicator connected';
            text.textContent = `Connected (${connectionType || 'unknown'})`;
        } else {
            indicator.className = 'status-indicator disconnected';
            text.textContent = 'Disconnected';
        }
    }

    /**
     * Handle dashboard data updates
     */
    handleDashboardUpdate(data) {
        this.state.dashboardData = data;

        // Atualizar summary cards
        this.updateSummaryCards(data.summary || {});

        // Atualizar active tasks
        this.updateActiveTasks(data.active_tasks || []);

        // Atualizar system metrics
        this.updateSystemMetrics(data.system_metrics || {});

        // Atualizar alerts
        this.updateAlerts(data.alerts || []);

        // Atualizar recent tasks
        this.updateRecentTasks(data.recent_completed || []);

        // Atualizar health status
        this.updateHealthStatus(data.system_health || {});

        // Atualizar uptime stats
        this.updateUptimeStats(data.uptime_stats || {});

        this.log('Dashboard updated', data);
    }

    /**
     * Atualizar summary cards
     */
    updateSummaryCards(summary) {
        this.elements.summaryCards.forEach(card => {
            const stat = card.getAttribute('data-summary-stat');
            if (summary[stat] !== undefined) {
                card.textContent = this.formatSummaryValue(stat, summary[stat]);
            }
        });
    }

    /**
     * Atualizar active tasks
     */
    updateActiveTasks(activeTasks) {
        const container = this.elements.activeTasksList;
        const emptyState = this.elements.activeTasksEmpty;

        if (!container) return;

        if (activeTasks.length === 0) {
            container.style.display = 'none';
            if (emptyState) emptyState.style.display = 'block';
            return;
        }

        container.style.display = 'block';
        if (emptyState) emptyState.style.display = 'none';

        // Limpar e recriar lista
        container.innerHTML = '';

        activeTasks.forEach(task => {
            const taskElement = this.createActiveTaskElement(task);
            container.appendChild(taskElement);

            // Subscrever aos updates desta task
            this.client.subscribeToTask(task.task_id);
        });
    }

    /**
     * Criar elemento de active task
     */
    createActiveTaskElement(task) {
        const div = document.createElement('div');
        div.className = 'active-task-item';
        div.setAttribute('data-task-id', task.task_id);
        
        const progress = Math.round(task.progress || 0);
        const eta = task.eta_seconds ? this.formatDuration(task.eta_seconds) : 'Unknown';
        const stage = task.current_stage ? this.formatStageName(task.current_stage) : 'Starting';

        div.innerHTML = `
            <div class="task-info">
                <span class="task-id">${task.task_id}</span>
                <span class="task-type">${task.task_type}</span>
                <span class="task-progress">${progress}%</span>
            </div>
            <div class="task-bar">
                <div class="task-progress-bar" style="width: ${progress}%"></div>
            </div>
            <div class="task-details">
                <span class="task-stage">Stage: ${stage}</span>
                <span class="task-eta">ETA: ${eta}</span>
            </div>
        `;

        // Click handler para mostrar detalhes
        div.addEventListener('click', () => {
            this.showTaskDetails(task.task_id);
        });

        return div;
    }

    /**
     * Atualizar system metrics
     */
    updateSystemMetrics(metrics) {
        this.elements.metricItems.forEach(item => {
            const metricName = item.getAttribute('data-metric');
            const metricData = metrics[metricName];

            if (metricData) {
                const valueElement = item.querySelector('.metric-value');
                const unitElement = item.querySelector('.metric-unit');

                if (valueElement) {
                    valueElement.textContent = this.formatMetricValue(metricName, metricData.current);
                }

                if (unitElement && metricData.unit) {
                    unitElement.textContent = metricData.unit;
                }

                // Adicionar indicador de tendência se disponível
                this.updateMetricTrend(item, metricData);
            }
        });
    }

    /**
     * Atualizar alerts
     */
    updateAlerts(alerts) {
        const container = this.elements.alertsList;
        const emptyState = this.elements.alertsEmpty;
        const countElement = this.elements.alertCount;

        if (!container) return;

        // Atualizar contador
        if (countElement) {
            countElement.textContent = alerts.length;
        }

        if (alerts.length === 0) {
            container.style.display = 'none';
            if (emptyState) emptyState.style.display = 'block';
            return;
        }

        container.style.display = 'block';
        if (emptyState) emptyState.style.display = 'none';

        // Limpar e recriar lista
        container.innerHTML = '';

        alerts.slice(0, 10).forEach(alert => { // Mostrar apenas os 10 mais recentes
            const alertElement = this.createAlertElement(alert);
            container.appendChild(alertElement);
        });
    }

    /**
     * Criar elemento de alert
     */
    createAlertElement(alert) {
        const div = document.createElement('div');
        div.className = `alert-item ${alert.level || 'info'}`;

        const timestamp = new Date(alert.timestamp).toLocaleTimeString();

        div.innerHTML = `
            <div class="alert-header">
                <span class="alert-level ${alert.level || 'info'}">${(alert.level || 'info').toUpperCase()}</span>
                <span class="alert-time">${timestamp}</span>
            </div>
            <div class="alert-message">${alert.message || 'No message'}</div>
        `;

        return div;
    }

    /**
     * Atualizar recent tasks
     */
    updateRecentTasks(recentTasks) {
        const container = this.elements.recentTasksList;
        const emptyState = this.elements.recentTasksEmpty;

        if (!container) return;

        if (recentTasks.length === 0) {
            container.style.display = 'none';
            if (emptyState) emptyState.style.display = 'block';
            return;
        }

        container.style.display = 'block';
        if (emptyState) emptyState.style.display = 'none';

        // Limpar e recriar lista
        container.innerHTML = '';

        recentTasks.slice(0, 10).forEach(task => {
            const taskElement = this.createRecentTaskElement(task);
            container.appendChild(taskElement);
        });
    }

    /**
     * Criar elemento de recent task
     */
    createRecentTaskElement(task) {
        const div = document.createElement('div');
        div.className = `recent-task-item ${task.status}`;

        const completedAt = task.completed_at ? 
            new Date(task.completed_at).toLocaleTimeString() : 'Unknown';

        div.innerHTML = `
            <div class="recent-task-info">
                <span class="recent-task-id">${task.task_id}</span>
                <span class="recent-task-type">${task.task_type}</span>
            </div>
            <div class="recent-task-meta">
                <span class="recent-task-status ${task.status}">${task.status}</span>
                <span class="recent-task-time">${completedAt}</span>
            </div>
        `;

        return div;
    }

    /**
     * Atualizar health status
     */
    updateHealthStatus(healthStatus) {
        this.elements.healthItems.forEach(item => {
            const healthType = item.id.replace('-health', '').replace('-', '_');
            const status = healthStatus[healthType];

            if (status) {
                const statusElement = item.querySelector('.health-status');
                if (statusElement) {
                    statusElement.className = `health-status ${status}`;
                    statusElement.textContent = status.charAt(0).toUpperCase() + status.slice(1);
                }
            }
        });
    }

    /**
     * Atualizar uptime statistics
     */
    updateUptimeStats(uptimeStats) {
        if (this.elements.systemUptime && uptimeStats.uptime_seconds) {
            this.elements.systemUptime.textContent = this.formatDuration(uptimeStats.uptime_seconds);
        }

        if (this.elements.totalRequests && uptimeStats.total_requests_processed) {
            this.elements.totalRequests.textContent = uptimeStats.total_requests_processed.toLocaleString();
        }

        if (this.elements.avgResponse && uptimeStats.average_response_time_ms) {
            this.elements.avgResponse.textContent = `${uptimeStats.average_response_time_ms.toFixed(1)}ms`;
        }
    }

    /**
     * Handle progress updates
     */
    handleProgressUpdate(data) {
        // Atualizar elemento específico da task
        const taskElement = document.querySelector(`[data-task-id="${data.task_id}"]`);
        if (taskElement) {
            this.updateTaskProgress(taskElement, data);
        }
    }

    /**
     * Handle task completion
     */
    handleTaskComplete(data) {
        this.showToast(`Task ${data.task_id} completed!`, 'success');
        
        // Remover da lista de active tasks após delay
        setTimeout(() => {
            const taskElement = document.querySelector(`[data-task-id="${data.task_id}"]`);
            if (taskElement) {
                taskElement.style.opacity = '0';
                setTimeout(() => taskElement.remove(), 300);
            }
        }, 3000);
    }

    /**
     * Handle task errors
     */
    handleTaskError(data) {
        this.showToast(`Task ${data.task_id} failed: ${data.error}`, 'error');
        
        // Atualizar visual da task
        const taskElement = document.querySelector(`[data-task-id="${data.task_id}"]`);
        if (taskElement) {
            taskElement.classList.add('error');
        }
    }

    /**
     * Handle system alerts
     */
    handleSystemAlert(alert) {
        // Mostrar toast para alerts críticos
        if (alert.level === 'critical' || alert.level === 'error') {
            this.showToast(alert.message, alert.level);
        }

        // Atualizar lista de alerts
        if (this.state.dashboardData) {
            this.state.dashboardData.alerts = this.state.dashboardData.alerts || [];
            this.state.dashboardData.alerts.unshift(alert);
            this.updateAlerts(this.state.dashboardData.alerts);
        }
    }

    /**
     * Inicializar performance chart
     */
    async initPerformanceChart(metricName = 'websocket_latency', timerangeHours = 1) {
        if (!this.elements.performanceChart) return;

        try {
            const history = await this.fetchMetricHistory(metricName, timerangeHours);
            
            const chart = new Chart(this.elements.performanceChart, {
                type: 'line',
                data: {
                    labels: history.map(point => 
                        new Date(point.timestamp * 1000).toLocaleTimeString()
                    ),
                    datasets: [{
                        label: this.formatMetricLabel(metricName),
                        data: history.map(point => point.value),
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        x: {
                            display: true,
                            grid: {
                                display: false
                            }
                        },
                        y: {
                            display: true,
                            beginAtZero: true
                        }
                    },
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    }
                }
            });

            this.state.chartInstances.set('performance', chart);

        } catch (error) {
            this.log('Failed to initialize performance chart', error);
        }
    }

    /**
     * Atualizar chart
     */
    async updateChart(metricName = null, timerangeHours = null) {
        const chart = this.state.chartInstances.get('performance');
        if (!chart) return;

        const currentMetric = metricName || this.elements.chartMetricSelector?.value || 'websocket_latency';
        const currentTimerange = timerangeHours || parseInt(this.elements.chartTimerangeSelector?.value) || 1;

        try {
            const history = await this.fetchMetricHistory(currentMetric, currentTimerange);
            
            chart.data.labels = history.map(point => 
                new Date(point.timestamp * 1000).toLocaleTimeString()
            );
            chart.data.datasets[0].data = history.map(point => point.value);
            chart.data.datasets[0].label = this.formatMetricLabel(currentMetric);
            
            chart.update('none');

        } catch (error) {
            this.log('Failed to update chart', error);
        }
    }

    /**
     * Fetch metric history from API
     */
    async fetchMetricHistory(metricName, hours = 1) {
        try {
            const response = await fetch(
                `${this.options.apiBaseUrl}/metrics/${metricName}/history?hours=${hours}`
            );
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            return data || [];

        } catch (error) {
            this.log('Failed to fetch metric history', error);
            return [];
        }
    }

    /**
     * Mostrar detalhes de uma task
     */
    async showTaskDetails(taskId) {
        try {
            this.showLoading('Loading task details...');
            
            const response = await fetch(`${this.options.apiBaseUrl}/tasks/${taskId}/details`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const taskDetails = await response.json();
            
            if (this.elements.taskDetailsContent) {
                this.elements.taskDetailsContent.innerHTML = this.createTaskDetailsHTML(taskDetails);
            }
            
            this.elements.taskDetailsModal?.classList.add('show');
            this.hideLoading();

        } catch (error) {
            this.log('Failed to load task details', error);
            this.hideLoading();
            this.showToast('Failed to load task details', 'error');
        }
    }

    /**
     * Criar HTML para detalhes da task
     */
    createTaskDetailsHTML(taskDetails) {
        const task = taskDetails.task_info;
        const events = taskDetails.events || [];
        const timeline = taskDetails.timeline;

        let html = `
            <div class="task-details">
                <h4>Task Information</h4>
                <div class="detail-grid">
                    <div class="detail-item">
                        <span class="detail-label">ID:</span>
                        <span class="detail-value">${task.task_id}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Type:</span>
                        <span class="detail-value">${task.task_type}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Status:</span>
                        <span class="detail-value status-${task.status}">${task.status}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Progress:</span>
                        <span class="detail-value">${Math.round(task.progress?.percentage || 0)}%</span>
                    </div>
                </div>
        `;

        if (task.progress?.stages) {
            html += `
                <h4>Stages Progress</h4>
                <div class="stages-progress">
            `;
            
            Object.entries(task.progress.stages).forEach(([stageName, stage]) => {
                html += `
                    <div class="stage-item">
                        <div class="stage-header">
                            <span class="stage-name">${this.formatStageName(stageName)}</span>
                            <span class="stage-progress">${Math.round(stage.percentage)}%</span>
                        </div>
                        <div class="stage-bar">
                            <div class="stage-fill" style="width: ${stage.percentage}%"></div>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
        }

        if (events.length > 0) {
            html += `
                <h4>Recent Events</h4>
                <div class="event-timeline">
            `;
            
            events.slice(0, 20).forEach(event => {
                const time = new Date(event.timestamp).toLocaleTimeString();
                html += `
                    <div class="event-item">
                        <span class="event-time">${time}</span>
                        <span class="event-type">${event.event_type}</span>
                        <span class="event-message">${event.message}</span>
                    </div>
                `;
            });
            
            html += '</div>';
        }

        html += '</div>';
        return html;
    }

    /**
     * Esconder modal de task details
     */
    hideTaskModal() {
        this.elements.taskDetailsModal?.classList.remove('show');
    }

    /**
     * Refresh data
     */
    async refreshData() {
        try {
            this.elements.refreshBtn?.classList.add('loading');
            await this.loadInitialData();
            this.showToast('Dashboard refreshed', 'info');
        } catch (error) {
            this.showToast('Failed to refresh data', 'error');
        } finally {
            this.elements.refreshBtn?.classList.remove('loading');
        }
    }

    /**
     * Export data
     */
    async exportData() {
        try {
            const response = await fetch(`${this.options.apiBaseUrl}/dashboard/report`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const report = await response.json();
            
            // Criar e download do arquivo JSON
            const blob = new Blob([JSON.stringify(report, null, 2)], { 
                type: 'application/json' 
            });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `dashboard-report-${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            this.showToast('Report exported successfully', 'success');

        } catch (error) {
            this.log('Failed to export data', error);
            this.showToast('Failed to export report', 'error');
        }
    }

    /**
     * Clear all alerts
     */
    clearAlerts() {
        if (this.elements.alertsList) {
            this.elements.alertsList.innerHTML = '';
            this.elements.alertsList.style.display = 'none';
        }
        
        if (this.elements.alertsEmpty) {
            this.elements.alertsEmpty.style.display = 'block';
        }
        
        if (this.elements.alertCount) {
            this.elements.alertCount.textContent = '0';
        }
        
        if (this.state.dashboardData) {
            this.state.dashboardData.alerts = [];
        }

        this.showToast('Alerts cleared', 'info');
    }

    /**
     * Toggle panel collapse/expand
     */
    togglePanel(button) {
        const panel = button.closest('.dashboard-panel');
        const content = panel?.querySelector('.panel-content');
        
        if (content) {
            const isCollapsed = content.style.display === 'none';
            content.style.display = isCollapsed ? 'block' : 'none';
            button.textContent = isCollapsed ? '▼' : '▶';
        }
    }

    /**
     * Handle keyboard shortcuts
     */
    handleKeyboardShortcuts(event) {
        // Ctrl/Cmd + R: Refresh
        if ((event.ctrlKey || event.metaKey) && event.key === 'r') {
            event.preventDefault();
            this.refreshData();
        }
        
        // Escape: Close modal
        if (event.key === 'Escape') {
            this.hideTaskModal();
        }
    }

    /**
     * Handle window resize
     */
    handleWindowResize() {
        // Redraw charts
        this.state.chartInstances.forEach(chart => {
            chart.resize();
        });
    }

    /**
     * Show loading overlay
     */
    showLoading(message = 'Loading...') {
        if (this.elements.loadingOverlay) {
            this.elements.loadingOverlay.querySelector('.loading-text').textContent = message;
            this.elements.loadingOverlay.classList.add('show');
        }
    }

    /**
     * Hide loading overlay
     */
    hideLoading() {
        this.elements.loadingOverlay?.classList.remove('show');
    }

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        
        this.elements.toastContainer?.appendChild(toast);
        
        // Trigger animation
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Auto remove
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }

    /**
     * Utility functions
     */
    getAuthToken() {
        // Implementar lógica de auth token se necessário
        return localStorage.getItem('auth_token') || null;
    }

    formatSummaryValue(stat, value) {
        switch (stat) {
            case 'system_load':
                return typeof value === 'string' ? value : 'Unknown';
            default:
                return typeof value === 'number' ? value.toLocaleString() : value;
        }
    }

    formatMetricValue(metricName, value) {
        if (typeof value !== 'number') return '0';
        
        if (metricName.includes('latency')) {
            return value.toFixed(1);
        } else if (metricName.includes('speed')) {
            return this.formatSpeed(value);
        } else if (metricName.includes('usage')) {
            return value.toFixed(1);
        }
        
        return value.toString();
    }

    formatMetricLabel(metricName) {
        return metricName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

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

    log(message, data = null) {
        if (this.options.debug) {
            console.log(`[ProgressDashboard] ${message}`, data || '');
        }
    }

    /**
     * Cleanup when page unloads
     */
    cleanup() {
        this.stopPeriodicRefresh();
        this.client?.disconnect();
        
        this.state.chartInstances.forEach(chart => {
            chart.destroy();
        });
        
        this.state.chartInstances.clear();
    }
}

/**
 * Chart Manager - Gerencia gráficos Chart.js
 */
class ChartManager {
    constructor() {
        this.charts = new Map();
        this.defaultColors = [
            '#2563eb', '#dc2626', '#059669', '#d97706', 
            '#7c3aed', '#db2777', '#0891b2', '#65a30d'
        ];
    }

    createChart(canvas, config) {
        const chart = new Chart(canvas, config);
        this.charts.set(canvas.id, chart);
        return chart;
    }

    destroyChart(id) {
        const chart = this.charts.get(id);
        if (chart) {
            chart.destroy();
            this.charts.delete(id);
        }
    }

    updateChart(id, data) {
        const chart = this.charts.get(id);
        if (chart) {
            chart.data = data;
            chart.update('none');
        }
    }

    resizeAll() {
        this.charts.forEach(chart => chart.resize());
    }

    destroyAll() {
        this.charts.forEach(chart => chart.destroy());
        this.charts.clear();
    }
}

// Export para uso global
window.ProgressDashboardApp = ProgressDashboardApp;
window.ChartManager = ChartManager;