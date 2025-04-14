# YouTube Downloader e Transcritor

Uma aplicação React para baixar, gerenciar, reproduzir e transcrever vídeos do YouTube, com interface amigável e diversas funcionalidades avançadas.

## 📋 Funcionalidades

- **Gerenciamento de Vídeos**: Visualize, organize e reproduza vídeos baixados
- **Gerenciamento de Áudios**: Extraia áudio de vídeos do YouTube
- **Transcrição de Conteúdo**: Transcreva áudios e vídeos em texto usando IA
- **Ordenação e Filtragem**: Organize seu conteúdo de várias maneiras
- **Interface Responsiva**: Experimente uma interface amigável e adaptável
- **Suporte a Temas**: Alterne entre temas claro e escuro

## 🛠️ Tecnologias Utilizadas

- **React/React Native**: Para a interface do usuário
- **Expo**: Facilitador de desenvolvimento React Native
- **TypeScript**: Para tipagem estática
- **Axios**: Para comunicação com o backend
- **React Navigation**: Para navegação entre telas
- **AsyncStorage**: Para armazenamento local

## 🗂️ Estrutura do Projeto

```
youtube-downloader/
├── src/
│   ├── components/       # Componentes reutilizáveis
│   ├── context/          # Contextos React (temas, autenticação)
│   ├── navigation/       # Configuração de navegação
│   ├── screens/          # Telas da aplicação
│   ├── services/         # Serviços (API, etc.)
│   ├── styles/           # Estilos e temas
│   └── types/            # Definições de tipos TypeScript
├── index.ts              # Ponto de entrada
├── App.tsx               # Componente raiz
└── package.json          # Dependências e scripts
```

## 💻 Requisitos de Sistema

- Node.js 14.x ou superior
- Yarn 1.22.x ou superior
- Expo CLI (para desenvolvimento móvel)
- Conexão com internet (para download de vídeos)

## 🚀 Instalação

1. Clone o repositório:
   ```bash
   git clone https://github.com/seu-usuario/youtube-downloader.git
   cd youtube-downloader
   ```

2. Instale as dependências:
   ```bash
   yarn install
   ```

3. Configure o backend:
   - Certifique-se de que o servidor backend esteja em execução na porta 8000
   - Veja o repositório do backend para instruções de configuração

## 🎯 Como Executar

Para iniciar o aplicativo em modo de desenvolvimento:

```bash
yarn start
```

Isso iniciará o servidor de desenvolvimento do Metro Bundler. Dependendo da plataforma alvo:

- Para web: Pressione `w` no terminal ou acesse `http://localhost:19006`
- Para Android: Pressione `a` no terminal (com o emulador ou dispositivo conectado)
- Para iOS: Pressione `i` no terminal (somente em macOS com Xcode instalado)

## 🧹 Limpeza de Cache

Se você estiver enfrentando problemas como tela branca, erros de renderização ou problemas de dependência, uma limpeza completa do cache pode resolver.

### Windows

1. **Parar o servidor** (Ctrl+C no terminal onde a aplicação está rodando)

2. **Limpar o cache do Yarn**:
   ```powershell
   yarn cache clean
   ```

3. **Limpar o cache do Metro Bundler**:
   ```powershell
   # Remova os arquivos de cache
   Remove-Item -Recurse -Force node_modules\.cache -ErrorAction SilentlyContinue
   
   # Limpe os arquivos temporários do Metro em %TEMP%
   Remove-Item -Recurse -Force $env:TEMP\metro-* -ErrorAction SilentlyContinue
   ```

4. **Reinstalar node_modules**:
   ```powershell
   # Remover pasta node_modules
   Remove-Item -Recurse -Force node_modules
   
   # Reinstalar dependências
   yarn install
   ```

5. **Opcional: Limpar outros arquivos temporários**:
   ```powershell
   Remove-Item -Recurse -Force .expo -ErrorAction SilentlyContinue
   Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
   Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
   ```

6. **Reiniciar o servidor com cache limpo**:
   ```powershell
   yarn start --reset-cache
   ```

### Linux/MacOS

1. **Parar o servidor** (Ctrl+C no terminal onde a aplicação está rodando)

2. **Limpar o cache do Yarn**:
   ```bash
   yarn cache clean
   ```

3. **Limpar o cache do Metro Bundler**:
   ```bash
   # Remova os arquivos de cache
   rm -rf node_modules/.cache
   
   # Limpe os arquivos temporários do Metro
   rm -rf $TMPDIR/metro-*
   ```

4. **Reinstalar node_modules**:
   ```bash
   # Remover pasta node_modules
   rm -rf node_modules
   
   # Reinstalar dependências
   yarn install
   ```

5. **Opcional: Limpar outros arquivos temporários**:
   ```bash
   rm -rf .expo
   rm -rf build
   rm -rf dist
   ```

6. **Reiniciar o servidor com cache limpo**:
   ```bash
   yarn start --reset-cache
   ```

## 🔍 Verificação Rápida de Problemas

Caso o problema de tela branca/erros persista após a limpeza, verifique:

1. **Arquivo de tema**: Confirme que o `src/styles/theme.ts` exporta as cores corretamente e está sendo importado sem erros

2. **Contexto de tema**: Verifique se o `ThemeContext.tsx` está processando o tema corretamente

3. **Navegação**: Certifique-se de que os componentes de navegação importam corretamente os temas

4. **API**: Confirme se o backend está acessível através da URL configurada (padrão: http://localhost:8000)

## 🔧 Soluções para Problemas Comuns

### Erro: "Cannot read properties of undefined (reading 'colors')"

Este erro geralmente ocorre quando o objeto de tema não está estruturado corretamente. Solução:

1. Edite `src/styles/theme.ts` e certifique-se que as cores estão exportadas corretamente no nível raiz do objeto:

```typescript
// Correto
export default {
  colors: {
    primary: '#3b82f6',
    secondary: '#60a5fa',
    // outras cores...
  },
  // outras propriedades...
};
```

2. Na importação, use:

```typescript
import theme from '../styles/theme';
// Acesso correto
theme.colors.primary 
```

### Erro: Aplicativo travando ou mostrando tela branca

Isso pode ocorrer devido a problemas de cache ou dependências:

1. Siga as instruções de limpeza de cache acima
2. Verifique o console para erros específicos e corrija-os
3. Certifique-se de que todas as dependências estão instaladas corretamente

## 📝 Contribuição

Contribuições são bem-vindas! Para contribuir:

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-funcionalidade`)
3. Faça commit das alterações (`git commit -m 'Adiciona nova funcionalidade'`)
4. Envie para o branch (`git push origin feature/nova-funcionalidade`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo LICENSE para detalhes.

---

*Este projeto foi desenvolvido para fins educacionais. Certifique-se de usar responsavelmente e respeitar os termos de serviço do YouTube.*