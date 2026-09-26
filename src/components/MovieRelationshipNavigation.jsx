import { createContext } from 'react';

// App owns cross-workspace navigation; every shared expanded card uses the same action.
export const MovieRelationshipNavigation = createContext(null);
