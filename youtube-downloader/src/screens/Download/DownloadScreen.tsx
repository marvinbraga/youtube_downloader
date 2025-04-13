
import React, { useState } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TextInput, 
  TouchableOpacity, 
  Switch,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { checkAudioExists, downloadAudio } from '../../services/api';
import StatusMessage from '../../components/StatusMessage';
import { theme } from '../../styles/theme';
import { useAuth } from '../../context/AuthContext';
import { useNavigation } from '@react-navigation/native';

const DownloadScreen: React.FC = () => {
  const { authState, login } = useAuth();
  const navigation = useNavigation();
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [highQuality, setHighQuality] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{
    message: string;
    type: 'error' | 'success' | 'info';
  } | null>(null);
  
  // Função para validar URL
  const isValidYoutubeUrl = (url: string) => {
    return url.trim() !== '' && 
      (url.includes('youtube.com/') || url.includes('youtu.be/'));
  };
  
  // Função para fazer download de áudio
  const handleDownload = async () => {
    if (!isValidYoutubeUrl(youtubeUrl)) {
      setStatusMessage({
        message: 'Por favor, insira uma URL do YouTube válida',
        type: 'error'
      });
      return;
    }
    
    try {
      if (!authState.isAuthenticated) {
        await login();
      }
      
      setIsLoading(true);
      setStatusMessage({
        message: 'Verificando se o áudio já existe...',
        type: 'info'
      });
      
      // Verificar se o áudio já existe
      const existsCheck = await checkAudioExists(youtubeUrl);
      
      if (existsCheck.exists && existsCheck.audio_info) {
        setStatusMessage({
          message: `Áudio já foi baixado anteriormente: ${existsCheck.audio_info.name}`,
          type: 'success'
        });
        
        // Navegar para a aba de áudio
        navigation.navigate('Áudio' as never);
        setYoutubeUrl('');
        return;
      }
      
      // Fazer o download do áudio
      setStatusMessage({
        message: 'Iniciando download de áudio...',
        type: 'info'
      });
      
      const response = await downloadAudio(youtubeUrl, highQuality);
      
      if (response.status === 'processando') {
        setStatusMessage({
          message: 'Download de áudio iniciado em segundo plano. Veja a aba "Áudio" após a conclusão.',
          type: 'success'
        });
        setYoutubeUrl('');
      } else {
        setStatusMessage({
          message: 'Falha ao iniciar o download de áudio',
          type: 'error'
        });
      }
    } catch (error) {
      console.error('Erro:', error);
      setStatusMessage({
        message: 'Erro ao fazer download do áudio. Tente novamente.',
        type: 'error'
      });
    } finally {
      setIsLoading(false);
    }
  };
  
  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.scrollContainer}>
        <View style={styles.container}>
          {statusMessage && (
            <StatusMessage
              message={statusMessage.message}
              type={statusMessage.type}
              onClose={() => setStatusMessage(null)}
            />
          )}
          
          <View style={styles.formContainer}>
            <View style={styles.formHeader}>
              <Feather name="download" size={24} color={theme.colors.primary} />
              <Text style={styles.formTitle}>Download de Áudio do YouTube</Text>
            </View>
            
            <View style={styles.formGroup}>
              <Text style={styles.label}>URL do YouTube:</Text>
              <TextInput
                style={styles.input}
                placeholder="https://www.youtube.com/watch?v=..."
                value={youtubeUrl}
                onChangeText={setYoutubeUrl}
                autoCapitalize="none"
                autoCorrect={false}
              />
            </View>
            
            <View style={styles.formGroup}>
              <View style={styles.switchContainer}>
                <Text style={styles.switchLabel}>Alta qualidade de áudio</Text>
                <Switch
                  value={highQuality}
                  onValueChange={setHighQuality}
                  trackColor={{ false: '#d1d1d1', true: '#a3d4ff' }}
                  thumbColor={highQuality ? theme.colors.primary : '#f4f3f4'}
                />
              </View>
            </View>
            
            <TouchableOpacity
              style={[styles.downloadButton, !isValidYoutubeUrl(youtubeUrl) && styles.downloadButtonDisabled]}
              onPress={handleDownload}
              disabled={!isValidYoutubeUrl(youtubeUrl) || isLoading}
            >
              {isLoading ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <>
                  <Feather name="download" size={18} color="#fff" />
                  <Text style={styles.downloadButtonText}>Baixar Áudio</Text>
                </>
              )}
            </TouchableOpacity>
            
            <View style={styles.infoContainer}>
              <Feather name="info" size={18} color={theme.colors.info} style={styles.infoIcon} />
              <Text style={styles.infoText}>
                O download pode demorar alguns minutos dependendo do tamanho do vídeo.
                Após concluído, o áudio estará disponível na aba "Áudio".
              </Text>
            </View>
          </View>
          
          <View style={styles.transcriptionInfoContainer}>
            <View style={styles.formHeader}>
              <Feather name="file-text" size={24} color={theme.colors.primary} />
              <Text style={styles.formTitle}>Transcrição de Áudio</Text>
            </View>
            
            <Text style={styles.transcriptionInfoText}>
              Selecione um arquivo de áudio na aba "Áudio" e use o botão de transcrição para converter áudio em texto.
            </Text>
            
            <View style={styles.infoContainer}>
              <Feather name="alert-circle" size={18} color={theme.colors.warning} style={styles.infoIcon} />
              <Text style={styles.infoText}>
                A transcrição é processada em segundo plano e pode demorar alguns minutos para ser concluída.
              </Text>
            </View>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  scrollContainer: {
    flexGrow: 1,
  },
  container: {
    flex: 1,
    backgroundColor: '#fff',
    padding: 16,
  },
  formContainer: {
    backgroundColor: theme.colors.backgroundLight,
    borderRadius: 8,
    padding: 16,
    marginBottom: 20,
    ...theme.shadows.sm
  },
  formHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  formTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginLeft: 10,
    color: theme.colors.textDark,
  },
  formGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 16,
    marginBottom: 8,
    fontWeight: '500',
    color: theme.colors.textDark,
  },
  input: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 4,
    padding: 12,
    fontSize: 16,
  },
  switchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 8,
  },
  switchLabel: {
    fontSize: 16,
    color: theme.colors.textDark,
  },
  downloadButton: {
    backgroundColor: theme.colors.secondary,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 4,
    marginTop: 8,
  },
  downloadButtonDisabled: {
    backgroundColor: '#a0a0a0',
  },
  downloadButtonText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: 16,
    marginLeft: 8,
  },
  infoContainer: {
    flexDirection: 'row',
    backgroundColor: 'rgba(23, 162, 184, 0.1)',
    padding: 12,
    borderRadius: 4,
    marginTop: 16,
    alignItems: 'flex-start',
  },
  infoIcon: {
    marginRight: 10,
    marginTop: 2,
  },
  infoText: {
    flex: 1,
    color: theme.colors.textDark,
    lineHeight: 20,
  },
  transcriptionInfoContainer: {
    backgroundColor: theme.colors.backgroundLight,
    borderRadius: 8,
    padding: 16,
    ...theme.shadows.sm
  },
  transcriptionInfoText: {
    fontSize: 16,
    color: theme.colors.textDark,
    marginBottom: 16,
    lineHeight: 22,
  },
});

export default DownloadScreen;
