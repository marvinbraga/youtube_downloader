
import React from 'react';
import { View, Text, StyleSheet, Modal, TouchableOpacity, ScrollView, ActivityIndicator } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { useTheme } from '../context/ThemeContext';

interface TranscriptionModalProps {
  visible: boolean;
  title: string;
  content: string;
  isLoading: boolean;
  onClose: () => void;
  onDownload: () => void;
}

const TranscriptionModal: React.FC<TranscriptionModalProps> = ({
  visible,
  title,
  content,
  isLoading,
  onClose,
  onDownload
}) => {
  const { colors, theme } = useTheme();

  return (
    <Modal
      animationType="fade"
      transparent={true}
      visible={visible}
      onRequestClose={onClose}
    >
      <View style={[
        styles.modalOverlay,
        theme.componentStyles.modal.overlay
      ]}>
        <View style={[
          styles.modalContainer,
          theme.componentStyles.modal.container,
          { 
            backgroundColor: colors.background.primary,
            ...theme.shadows.lg
          }
        ]}>
          <View style={[
            styles.modalHeader,
            theme.componentStyles.modal.header,
            { borderBottomColor: colors.border }
          ]}>
            <Text style={[styles.modalTitle, { color: colors.text.primary }]}>
              {title}
            </Text>
            <TouchableOpacity onPress={onClose} style={styles.closeButton}>
              <Feather name="x" size={24} color={colors.text.secondary} />
            </TouchableOpacity>
          </View>
          
          <ScrollView 
            style={[styles.modalBody, theme.componentStyles.modal.body]}
            contentContainerStyle={styles.modalContent}
          >
            {isLoading ? (
              <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color={colors.primary} />
                <Text style={[styles.loadingText, { color: colors.text.primary }]}>
                  Carregando transcrição...
                </Text>
              </View>
            ) : (
              <Text style={[styles.transcriptionText, { color: colors.text.primary }]}>
                {content}
              </Text>
            )}
          </ScrollView>
          
          <View style={[
            styles.modalFooter,
            theme.componentStyles.modal.footer,
            { borderTopColor: colors.border }
          ]}>
            <TouchableOpacity 
              style={[
                styles.downloadButton,
                { backgroundColor: colors.primary }
              ]}
              onPress={onDownload}
              disabled={isLoading}
            >
              <Feather name="download" size={18} color="white" />
              <Text style={styles.downloadButtonText}>Baixar Transcrição</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalContainer: {
    width: '90%',
    maxHeight: '80%',
    borderRadius: 12,
    overflow: 'hidden',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
  },
  closeButton: {
    padding: 4,
  },
  modalBody: {
    maxHeight: 400,
  },
  modalContent: {
    padding: 16,
  },
  transcriptionText: {
    fontSize: 16,
    lineHeight: 24,
  },
  loadingContainer: {
    padding: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
  },
  modalFooter: {
    borderTopWidth: 1,
    padding: 16,
    alignItems: 'flex-end',
  },
  downloadButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 4,
  },
  downloadButtonText: {
    color: 'white',
    fontWeight: '500',
    marginLeft: 8,
  }
});

export default TranscriptionModal;
