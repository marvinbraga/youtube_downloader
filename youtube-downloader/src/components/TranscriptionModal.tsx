
import React from 'react';
import { View, Text, StyleSheet, Modal, TouchableOpacity, ScrollView, ActivityIndicator } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { theme } from '../styles/theme';

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
  return (
    <Modal
      animationType="fade"
      transparent={true}
      visible={visible}
      onRequestClose={onClose}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>{title}</Text>
            <TouchableOpacity onPress={onClose} style={styles.closeButton}>
              <Feather name="x" size={24} color="#aaa" />
            </TouchableOpacity>
          </View>
          
          <ScrollView style={styles.modalBody} contentContainerStyle={styles.modalContent}>
            {isLoading ? (
              <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color={theme.colors.primary} />
                <Text style={styles.loadingText}>Carregando transcrição...</Text>
              </View>
            ) : (
              <Text style={styles.transcriptionText}>{content}</Text>
            )}
          </ScrollView>
          
          <View style={styles.modalFooter}>
            <TouchableOpacity 
              style={styles.downloadButton}
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
    backgroundColor: 'white',
    borderRadius: 12,
    overflow: 'hidden',
    ...theme.shadows.lg
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: theme.colors.textDark,
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
    color: theme.colors.textDark,
  },
  loadingContainer: {
    padding: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    color: theme.colors.textDark,
  },
  modalFooter: {
    borderTopWidth: 1,
    borderTopColor: theme.colors.border,
    padding: 16,
    alignItems: 'flex-end',
  },
  downloadButton: {
    backgroundColor: theme.colors.primary,
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
