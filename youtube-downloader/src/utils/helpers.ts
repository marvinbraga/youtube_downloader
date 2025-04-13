
/**
 * Formata uma data em uma string legível
 * @param dateString String de data para formatar
 * @returns Data formatada
 */
export const formatDate = (dateString: string): string => {
  const date = new Date(dateString);
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
};

/**
 * Formata o tamanho do arquivo para uma string legível
 * @param bytes Tamanho em bytes
 * @returns Tamanho formatado (KB, MB, GB)
 */
export const formatFileSize = (bytes: number): string => {
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  if (bytes === 0) return '0 Bytes';
  const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)).toString());
  return Math.round(bytes / Math.pow(1024, i)) + ' ' + sizes[i];
};

/**
 * Destaca texto com base em uma consulta de pesquisa
 * @param text Texto original
 * @param searchTerm Termo a ser destacado
 * @returns Texto HTML com destaques (para uso com componentes de texto compatíveis)
 */
export const highlightText = (text: string, searchTerm: string): string => {
  if (!searchTerm || !text) return text;
  const regex = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  return text.replace(regex, '<span style="background-color: yellow">$1</span>');
};

/**
 * Verifica se uma URL do YouTube é válida
 * @param url URL a verificar
 * @returns boolean indicando se é válida
 */
export const isValidYoutubeUrl = (url: string): boolean => {
  return url.trim() !== '' && 
    (url.includes('youtube.com/') || url.includes('youtu.be/'));
};

/**
 * Aguarda um tempo específico
 * @param ms Tempo em milissegundos
 * @returns Promise que resolve após o tempo
 */
export const sleep = (ms: number): Promise<void> => {
  return new Promise(resolve => setTimeout(resolve, ms));
};

/**
 * Trunca texto para um comprimento máximo
 * @param text Texto a truncar
 * @param maxLength Comprimento máximo
 * @returns Texto truncado
 */
export const truncateText = (text: string, maxLength: number): string => {
  if (!text || text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
};
