import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './styles.css';
import './styles/metadataAuthority.css';
import './styles/identityReview.css';
import './styles/metadataCorrection.css';
import './styles/posterEditor.css';
import './styles/smartMatch.css';
import './components/movie-card/movieCard.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>
);
