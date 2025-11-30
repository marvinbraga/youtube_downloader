# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is a React Native/Expo YouTube downloader application that allows users to download YouTube videos as audio files and transcribe them using AI. The app is built in Portuguese and features a modern UI with dark/light theme support.

## Key Commands

### Development
```bash
# Start development server
yarn start

# Run on specific platforms
yarn android
yarn ios
yarn web

# Install dependencies
yarn install

# Clear cache (if experiencing issues)
yarn start --clear
npx expo start --clear
```

## Architecture

### Core Technologies
- **Framework**: React Native with Expo SDK 52
- **Language**: TypeScript (strict mode enabled)
- **State Management**: React Context API (AuthContext, ThemeContext)
- **Navigation**: React Navigation with bottom tabs
- **HTTP Client**: Axios with interceptors for auth token management
- **UI Components**: React Native Paper + custom theme system

### Directory Structure
- `src/components/`: Reusable UI components (AudioItem, VideoItem, TranscriptionModal, etc.)
- `src/screens/`: Main app screens (Audio, Download, Videos)
- `src/context/`: Global state contexts (Auth, Theme)
- `src/services/api.ts`: Backend API client with token refresh logic
- `src/styles/theme.ts`: Comprehensive theme system with light/dark modes
- `src/types/`: TypeScript type definitions

### Backend Integration
The app communicates with a backend server at `http://localhost:8000` that handles:
- YouTube video/audio downloading
- File management (CRUD operations)
- AI transcription via Groq provider
- Authentication with JWT tokens (auto-refresh mechanism)

**Backend Codebase Location**: `E:\python\youtube_downloader\app`

### Key Patterns

#### API Client Setup
The API client in `src/services/api.ts` includes:
- Automatic token refresh on 401 responses
- Request/response interceptors for auth headers
- Error handling with retry logic

#### Theme System
Located in `src/styles/theme.ts`, provides:
- Complete color palette for light/dark modes
- Component-specific styles
- Typography scales
- Shadow and elevation definitions
- Gradient configurations

#### Authentication Flow
- Token stored in AsyncStorage
- Auto-refresh mechanism in API interceptors
- Context provider wraps entire app for global auth state

## Important Considerations

### Path Imports
Use the `@` alias for absolute imports from src directory:
```typescript
import { api } from '@/services/api';
import { Theme } from '@/styles/theme';
```

### State Updates
When updating lists (audios, videos), always fetch fresh data from backend rather than relying on local state mutations to ensure consistency.

### Error Handling
Use the StatusMessage component for user feedback:
```typescript
setStatusMessage({ text: 'Error message', type: 'error' });
```

### Type Safety
All API responses and component props should have corresponding TypeScript interfaces defined in `src/types/index.ts`.

### Theme Usage
Access theme through the useTheme hook:
```typescript
const { theme, isDarkMode } = useTheme();
```

### API Endpoints
Key endpoints used throughout the app:
- `GET/POST /audios/` - Audio file management
- `GET/POST /videos/` - Video file management  
- `POST /audios/download/` - YouTube download
- `POST /audios/{id}/transcribe/` - AI transcription
- `POST /token/refresh/` - Auth token refresh