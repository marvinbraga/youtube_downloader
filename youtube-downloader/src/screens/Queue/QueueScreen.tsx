import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Alert
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { useTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';
import { useDownloads } from '../../context/DownloadContext';
import StatusMessage from '../../components/StatusMessage';
import { getQueueStatus, cleanupQueue } from '../../services/api';

interface QueueStatus {
  total: number;
  queued: number;
  downloading: number;
  completed: number;
  failed: number;
  cancelled: number;
  retrying: number;
  active_slots: number;
  max_concurrent: number;
}

interface QueueTask {
  id: string;
  audio_id: string;
  url: string;
  status: string;
  progress: number;
  error_message?: string;
  retry_count: number;
  max_retries: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

const QueueScreen: React.FC = () => {
  const { colors, theme } = useTheme();
  const { authState, login } = useAuth();
  const { getQueueTasks, cancelDownload } = useDownloads();
  const [queueStatus, setQueueStatus] = useState<QueueStatus | null>(null);
  const [queueTasks, setQueueTasks] = useState<QueueTask[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{
    message: string;
    type: 'error' | 'success' | 'info';
  } | null>(null);

  // Carregar dados da fila
  const loadQueueData = useCallback(async () => {
    if (!authState.isAuthenticated) {
      return;
    }

    try {
      setIsLoading(true);

      // Carregar status da fila
      const status = await getQueueStatus();
      setQueueStatus(status);

      // Carregar tasks da fila
      const tasks = await getQueueTasks();
      setQueueTasks(tasks);

    } catch (error) {
      console.error('Erro ao carregar dados da fila:', error);
      setStatusMessage({
        message: 'Erro ao carregar dados da fila. Tente novamente.',
        type: 'error'
      });
    } finally {
      setIsLoading(false);
      setRefreshing(false);
    }
  }, [authState.isAuthenticated]);

  // Carregar dados no início
  useEffect(() => {
    if (authState.isAuthenticated) {
      loadQueueData();
    } else if (!authState.isLoading) {
      login();
    }
  }, [authState.isAuthenticated, authState.isLoading, login, loadQueueData]);

  // Auto-refresh a cada 5 segundos
  useEffect(() => {
    if (authState.isAuthenticated) {
      const interval = setInterval(loadQueueData, 5000);
      return () => clearInterval(interval);
    }
  }, [authState.isAuthenticated, loadQueueData]);

  // Função para pull-to-refresh
  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadQueueData();
  }, [loadQueueData]);

  // Função para cancelar task
  const handleCancelTask = useCallback(async (task: QueueTask) => {
    try {
      Alert.alert(
        'Cancelar Download',
        'Tem certeza que deseja cancelar este download?',
        [
          {
            text: 'Não',
            style: 'cancel'
          },
          {
            text: 'Sim, cancelar',
            style: 'destructive',
            onPress: async () => {
              const success = await cancelDownload(task.audio_id);
              if (success) {
                setStatusMessage({
                  message: 'Download cancelado com sucesso',
                  type: 'success'
                });
                loadQueueData(); // Recarregar
              } else {
                setStatusMessage({
                  message: 'Erro ao cancelar download',
                  type: 'error'
                });
              }
            }
          }
        ]
      );
    } catch (error) {
      console.error('Erro ao cancelar task:', error);
      setStatusMessage({
        message: 'Erro ao cancelar download',
        type: 'error'
      });
    }
  }, [cancelDownload, loadQueueData]);

  // Função para limpar fila
  const handleCleanupQueue = useCallback(async () => {
    try {
      Alert.alert(
        'Limpar Fila',
        'Deseja remover todas as tasks antigas (concluídas há mais de 24h)?',
        [
          {
            text: 'Cancelar',
            style: 'cancel'
          },
          {
            text: 'Limpar',
            style: 'default',
            onPress: async () => {
              try {
                await cleanupQueue(24);
                setStatusMessage({
                  message: 'Fila limpa com sucesso',
                  type: 'success'
                });
                loadQueueData();
              } catch (error) {
                setStatusMessage({
                  message: 'Erro ao limpar fila',
                  type: 'error'
                });
              }
            }
          }
        ]
      );
    } catch (error) {
      console.error('Erro ao limpar fila:', error);
    }
  }, [loadQueueData]);

  // Função para obter cor do status
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'queued':
        return colors.info;
      case 'downloading':
        return colors.primary;
      case 'completed':
        return colors.success;
      case 'failed':
        return colors.error;
      case 'cancelled':
        return colors.text.secondary;
      case 'retrying':
        return colors.warning;
      default:
        return colors.text.secondary;
    }
  };

  // Função para obter texto do status
  const getStatusText = (status: string) => {
    switch (status) {
      case 'queued':
        return 'Na fila';
      case 'downloading':
        return 'Baixando';
      case 'completed':
        return 'Concluído';
      case 'failed':
        return 'Falhou';
      case 'cancelled':
        return 'Cancelado';
      case 'retrying':
        return 'Tentando novamente';
      default:
        return status;
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: colors.background.primary }]}>
      {statusMessage && (
        <StatusMessage
          message={statusMessage.message}
          type={statusMessage.type}
          onClose={() => setStatusMessage(null)}
        />
      )}

      {/* Header com estatísticas */}
      {queueStatus && (
        <View style={[styles.statusContainer, { backgroundColor: colors.background.secondary, ...theme.shadows.sm }]}>
          <View style={styles.statusHeader}>
            <Feather name="list" size={24} color={colors.primary} />
            <Text style={[styles.statusTitle, { color: colors.text.primary }]}>
              Status da Fila de Downloads
            </Text>
            <TouchableOpacity onPress={handleCleanupQueue}>
              <Feather name="trash-2" size={20} color={colors.text.secondary} />
            </TouchableOpacity>
          </View>

          <View style={styles.statusGrid}>
            <View style={styles.statusItem}>
              <Text style={[styles.statusNumber, { color: colors.primary }]}>
                {queueStatus.active_slots}/{queueStatus.max_concurrent}
              </Text>
              <Text style={[styles.statusLabel, { color: colors.text.secondary }]}>Ativo</Text>
            </View>

            <View style={styles.statusItem}>
              <Text style={[styles.statusNumber, { color: colors.info }]}>
                {queueStatus.queued}
              </Text>
              <Text style={[styles.statusLabel, { color: colors.text.secondary }]}>Na fila</Text>
            </View>

            <View style={styles.statusItem}>
              <Text style={[styles.statusNumber, { color: colors.success }]}>
                {queueStatus.completed}
              </Text>
              <Text style={[styles.statusLabel, { color: colors.text.secondary }]}>Concluídos</Text>
            </View>

            <View style={styles.statusItem}>
              <Text style={[styles.statusNumber, { color: colors.error }]}>
                {queueStatus.failed}
              </Text>
              <Text style={[styles.statusLabel, { color: colors.text.secondary }]}>Falharam</Text>
            </View>
          </View>
        </View>
      )}

      {/* Lista de tasks */}
      <View style={[styles.tasksContainer, { backgroundColor: colors.background.secondary, ...theme.shadows.sm }]}>
        <Text style={[styles.tasksTitle, { color: colors.text.primary }]}>
          Tasks na Fila ({queueTasks.length})
        </Text>

        {isLoading && !refreshing ? (
          <View style={styles.centerLoading}>
            <ActivityIndicator size="large" color={colors.primary} />
            <Text style={[styles.loadingText, { color: colors.text.primary }]}>Carregando fila...</Text>
          </View>
        ) : queueTasks.length === 0 ? (
          <View style={styles.emptyState}>
            <Feather name="inbox" size={48} color={colors.text.secondary} />
            <Text style={[styles.emptyText, { color: colors.text.primary }]}>
              Nenhuma task na fila
            </Text>
          </View>
        ) : (
          <ScrollView
            style={styles.tasksList}
            contentContainerStyle={styles.tasksListContent}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={onRefresh}
                colors={[colors.primary]}
                tintColor={colors.primary}
              />
            }
          >
            {queueTasks.map((task) => (
              <View
                key={task.id}
                style={[styles.taskItem, { backgroundColor: colors.background.primary, borderColor: colors.border }]}
              >
                <View style={styles.taskHeader}>
                  <View style={styles.taskInfo}>
                    <Text style={[styles.taskTitle, { color: colors.text.primary }]} numberOfLines={1}>
                      {task.audio_id}
                    </Text>
                    <Text style={[styles.taskUrl, { color: colors.text.secondary }]} numberOfLines={1}>
                      {task.url}
                    </Text>
                  </View>

                  <View style={[styles.taskStatus, { backgroundColor: getStatusColor(task.status) + '20' }]}>
                    <View style={[styles.statusDot, { backgroundColor: getStatusColor(task.status) }]} />
                    <Text style={[styles.taskStatusText, { color: getStatusColor(task.status) }]}>
                      {getStatusText(task.status)}
                    </Text>
                  </View>
                </View>

                {/* Barra de progresso */}
                {task.status === 'downloading' && task.progress > 0 && (
                  <View style={styles.progressContainer}>
                    <View style={[styles.progressBar, { backgroundColor: colors.border }]}>
                      <View
                        style={[
                          styles.progressFill,
                          {
                            backgroundColor: colors.primary,
                            width: `${task.progress}%`
                          }
                        ]}
                      />
                    </View>
                    <Text style={[styles.progressText, { color: colors.text.secondary }]}>
                      {task.progress}%
                    </Text>
                  </View>
                )}

                {/* Informações de retry */}
                {task.retry_count > 0 && (
                  <Text style={[styles.retryInfo, { color: colors.warning }]}>
                    Tentativas: {task.retry_count}/{task.max_retries}
                  </Text>
                )}

                {/* Erro */}
                {task.error_message && (
                  <Text style={[styles.errorMessage, { color: colors.error }]}>
                    Erro: {task.error_message}
                  </Text>
                )}

                {/* Ações */}
                {(task.status === 'queued' || task.status === 'downloading') && (
                  <TouchableOpacity
                    style={[styles.cancelButton, { backgroundColor: colors.error }]}
                    onPress={() => handleCancelTask(task)}
                  >
                    <Feather name="x" size={16} color="white" />
                    <Text style={styles.cancelButtonText}>Cancelar</Text>
                  </TouchableOpacity>
                )}
              </View>
            ))}
          </ScrollView>
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
  },
  statusContainer: {
    borderRadius: 8,
    padding: 16,
    marginBottom: 16,
  },
  statusHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  statusTitle: {
    flex: 1,
    fontSize: 18,
    fontWeight: '600',
    marginLeft: 10,
  },
  statusGrid: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  statusItem: {
    alignItems: 'center',
  },
  statusNumber: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  statusLabel: {
    fontSize: 12,
    marginTop: 4,
  },
  tasksContainer: {
    flex: 1,
    borderRadius: 8,
    padding: 16,
  },
  tasksTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 16,
  },
  centerLoading: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 10,
    textAlign: 'center',
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyText: {
    marginTop: 16,
    textAlign: 'center',
    fontSize: 16,
  },
  tasksList: {
    flex: 1,
  },
  tasksListContent: {
    paddingBottom: 16,
  },
  taskItem: {
    padding: 12,
    borderRadius: 8,
    marginBottom: 12,
    borderWidth: 1,
  },
  taskHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  taskInfo: {
    flex: 1,
    marginRight: 12,
  },
  taskTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  taskUrl: {
    fontSize: 12,
    marginTop: 2,
  },
  taskStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 12,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 6,
  },
  taskStatusText: {
    fontSize: 12,
    fontWeight: '500',
  },
  progressContainer: {
    marginTop: 8,
    marginBottom: 4,
  },
  progressBar: {
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 2,
  },
  progressText: {
    fontSize: 12,
    marginTop: 4,
    textAlign: 'right',
  },
  retryInfo: {
    fontSize: 12,
    marginTop: 4,
  },
  errorMessage: {
    fontSize: 12,
    marginTop: 4,
  },
  cancelButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 4,
    marginTop: 8,
    alignSelf: 'flex-end',
  },
  cancelButtonText: {
    color: 'white',
    fontSize: 12,
    fontWeight: '500',
    marginLeft: 4,
  },
});

export default QueueScreen;