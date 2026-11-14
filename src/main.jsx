import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import AppErrorBoundary from './components/AppErrorBoundary.jsx';
import { AIProviderProvider } from './features/ai/AIProviderContext.jsx';
import { MovieAwardsProvider } from './components/MovieAwardsContext.jsx';
import { installScrollbarActivity } from './utils/scrollbarActivity.js';
import './styles/playerTheme.css';
import './styles.css';
import './styles/scrollbars.css';
import './styles/metadataAuthority.css';
import './styles/identityReview.css';
import './styles/metadataCorrection.css';
import './styles/posterEditor.css';
import './styles/smartMatch.css';
import './components/movie-card/movieCard.css';
import './styles/movieRelationships.css';
import './styles/movieAwards.css';
import './features/ai/ai.css';
import './components/ui/ui.css';

const stopScrollbarActivity = installScrollbarActivity(document);
if (import.meta.hot) import.meta.hot.dispose(stopScrollbarActivity);

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AppErrorBoundary>
      <AIProviderProvider><MovieAwardsProvider><App /></MovieAwardsProvider></AIProviderProvider>
    </AppErrorBoundary>
  </StrictMode>
);
