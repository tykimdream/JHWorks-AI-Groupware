export const IDENTITY_CHANGED_EVENT = 'jhworks:identity-changed';
export const SESSION_EXPIRED_EVENT = 'jhworks:session-expired';

// Browser-only request generation, never an identity or a persisted credential.
let generation = 0;
export const getSessionGeneration = () => generation;
export const advanceSessionGeneration = () => ++generation;

export const notifyIdentityChanged = (guest = false) => {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(IDENTITY_CHANGED_EVENT, { detail: { guest } }));
  }
};

export const notifySessionExpired = (requestGeneration: number) => {
  if (typeof window !== 'undefined' && requestGeneration === generation) {
    window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT, { detail: { generation } }));
  }
};
