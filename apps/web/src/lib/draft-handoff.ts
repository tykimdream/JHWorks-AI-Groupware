const keyFor = (employeeId: string) => `jhworks:draft-request:${employeeId}`;

// A tab-local handoff avoids exposing business text in URLs, history and access logs.
export function storeDraftRequest(employeeId: string, request: string): boolean {
  try {
    window.sessionStorage.setItem(keyFor(employeeId), request.slice(0, 2000));
    return true;
  } catch {
    return false;
  }
}

export function readDraftRequest(employeeId: string): string {
  try {
    return window.sessionStorage.getItem(keyFor(employeeId))?.slice(0, 2000) ?? '';
  } catch {
    return '';
  }
}

export function clearDraftRequest(employeeId: string): void {
  try {
    window.sessionStorage.removeItem(keyFor(employeeId));
  } catch {
    /* Storage may be disabled; the API remains the authorization boundary. */
  }
}
