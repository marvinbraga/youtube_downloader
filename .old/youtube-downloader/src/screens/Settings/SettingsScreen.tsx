import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Switch,
  TouchableOpacity,
  Alert
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { useTheme } from '../../context/ThemeContext';
import { useDownloads } from '../../context/DownloadContext';
import { cleanupQueue } from '../../services/api';

const SettingsScreen: React.FC = () => {
  const { colors, theme, toggleTheme, isDarkTheme } = useTheme();
  const { notificationsEnabled, setNotificationsEnabled } = useDownloads();

  const handleCleanupQueue = async () => {
    Alert.alert(
      'Limpar Fila de Downloads',
      'Esta ação irá remover todas as tasks antigas (concluídas há mais de 24h) da fila. Continuar?',
      [
        {
          text: 'Cancelar',
          style: 'cancel'
        },
        {
          text: 'Limpar',
          style: 'destructive',
          onPress: async () => {
            try {
              await cleanupQueue(24);
              Alert.alert('Sucesso', 'Fila de downloads limpa com sucesso');
            } catch (error) {
              Alert.alert('Erro', 'Não foi possível limpar a fila de downloads');
            }
          }
        }
      ]
    );
  };

  const SettingItem = ({ 
    icon, 
    title, 
    subtitle, 
    onPress, 
    rightElement 
  }: {
    icon: string;
    title: string;
    subtitle?: string;
    onPress?: () => void;
    rightElement?: React.ReactNode;
  }) => (
    <TouchableOpacity
      style={[styles.settingItem, { backgroundColor: colors.background.secondary, borderColor: colors.border }]}
      onPress={onPress}
      disabled={!onPress}
    >
      <View style={styles.settingContent}>
        <View style={styles.settingIcon}>
          <Feather name={icon as any} size={20} color={colors.primary} />
        </View>
        <View style={styles.settingText}>
          <Text style={[styles.settingTitle, { color: colors.text.primary }]}>
            {title}
          </Text>
          {subtitle && (
            <Text style={[styles.settingSubtitle, { color: colors.text.secondary }]}>
              {subtitle}
            </Text>
          )}
        </View>
        {rightElement && (
          <View style={styles.settingRight}>
            {rightElement}
          </View>
        )}
        {onPress && !rightElement && (
          <Feather name="chevron-right" size={16} color={colors.text.secondary} />
        )}
      </View>
    </TouchableOpacity>
  );

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: colors.background.primary }]}
      contentContainerStyle={styles.content}
    >
      {/* Seção de Aparência */}
      <View style={[styles.section, { backgroundColor: colors.background.secondary, ...theme.shadows.sm }]}>
        <View style={styles.sectionHeader}>
          <Feather name="eye" size={20} color={colors.primary} />
          <Text style={[styles.sectionTitle, { color: colors.text.primary }]}>
            Aparência
          </Text>
        </View>
        
        <SettingItem
          icon="moon"
          title="Modo Escuro"
          subtitle="Alterna entre tema claro e escuro"
          rightElement={
            <Switch
              value={isDarkTheme}
              onValueChange={toggleTheme}
              trackColor={{ false: colors.border, true: colors.primary + '40' }}
              thumbColor={isDarkTheme ? colors.primary : colors.background.primary}
            />
          }
        />
      </View>

      {/* Seção de Downloads */}
      <View style={[styles.section, { backgroundColor: colors.background.secondary, ...theme.shadows.sm }]}>
        <View style={styles.sectionHeader}>
          <Feather name="download" size={20} color={colors.primary} />
          <Text style={[styles.sectionTitle, { color: colors.text.primary }]}>
            Downloads
          </Text>
        </View>
        
        <SettingItem
          icon="bell"
          title="Notificações"
          subtitle="Receber alertas quando downloads concluírem"
          rightElement={
            <Switch
              value={notificationsEnabled}
              onValueChange={setNotificationsEnabled}
              trackColor={{ false: colors.border, true: colors.primary + '40' }}
              thumbColor={notificationsEnabled ? colors.primary : colors.background.primary}
            />
          }
        />
        
        <SettingItem
          icon="trash-2"
          title="Limpar Fila"
          subtitle="Remove downloads antigos da fila (24h+)"
          onPress={handleCleanupQueue}
        />
      </View>

      {/* Seção de Informações */}
      <View style={[styles.section, { backgroundColor: colors.background.secondary, ...theme.shadows.sm }]}>
        <View style={styles.sectionHeader}>
          <Feather name="info" size={20} color={colors.primary} />
          <Text style={[styles.sectionTitle, { color: colors.text.primary }]}>
            Sobre
          </Text>
        </View>
        
        <SettingItem
          icon="smartphone"
          title="Versão do App"
          subtitle="1.0.0"
        />
        
        <SettingItem
          icon="server"
          title="Servidor"
          subtitle="http://localhost:8000"
        />
        
        <SettingItem
          icon="users"
          title="Limite de Downloads"
          subtitle="2 downloads simultâneos"
        />
      </View>

      {/* Seção de Funcionalidades */}
      <View style={[styles.section, { backgroundColor: colors.background.secondary, ...theme.shadows.sm }]}>
        <View style={styles.sectionHeader}>
          <Feather name="zap" size={20} color={colors.primary} />
          <Text style={[styles.sectionTitle, { color: colors.text.primary }]}>
            Funcionalidades
          </Text>
        </View>
        
        <View style={styles.featureList}>
          <View style={styles.feature}>
            <Feather name="check-circle" size={16} color={colors.success} />
            <Text style={[styles.featureText, { color: colors.text.primary }]}>
              Fila de downloads com limite de concorrência
            </Text>
          </View>
          
          <View style={styles.feature}>
            <Feather name="check-circle" size={16} color={colors.success} />
            <Text style={[styles.featureText, { color: colors.text.primary }]}>
              Retry automático com backoff exponencial
            </Text>
          </View>
          
          <View style={styles.feature}>
            <Feather name="check-circle" size={16} color={colors.success} />
            <Text style={[styles.featureText, { color: colors.text.primary }]}>
              Cancelamento de downloads em andamento
            </Text>
          </View>
          
          <View style={styles.feature}>
            <Feather name="check-circle" size={16} color={colors.success} />
            <Text style={[styles.featureText, { color: colors.text.primary }]}>
              Atualizações em tempo real via SSE
            </Text>
          </View>
          
          <View style={styles.feature}>
            <Feather name="check-circle" size={16} color={colors.success} />
            <Text style={[styles.featureText, { color: colors.text.primary }]}>
              Notificações de conclusão
            </Text>
          </View>
          
          <View style={styles.feature}>
            <Feather name="check-circle" size={16} color={colors.success} />
            <Text style={[styles.featureText, { color: colors.text.primary }]}>
              Interface de monitoramento da fila
            </Text>
          </View>
        </View>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    padding: 16,
  },
  section: {
    borderRadius: 8,
    padding: 16,
    marginBottom: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginLeft: 8,
  },
  settingItem: {
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 8,
    overflow: 'hidden',
  },
  settingContent: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
  },
  settingIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'transparent',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  settingText: {
    flex: 1,
  },
  settingTitle: {
    fontSize: 16,
    fontWeight: '500',
  },
  settingSubtitle: {
    fontSize: 14,
    marginTop: 2,
  },
  settingRight: {
    marginLeft: 12,
  },
  featureList: {
    marginTop: 8,
  },
  feature: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  featureText: {
    fontSize: 14,
    marginLeft: 8,
  },
});

export default SettingsScreen;