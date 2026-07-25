const API_CREDENTIAL_STORAGE_KEY = 'mindsight-api-key'

export function readApiCredential(): string {
  if (typeof sessionStorage === 'undefined') return ''
  try {
    return sessionStorage.getItem(API_CREDENTIAL_STORAGE_KEY)?.trim() ?? ''
  } catch {
    return ''
  }
}

export function saveApiCredential(value: string): void {
  if (typeof sessionStorage === 'undefined') return
  try {
    const normalized = value.trim()
    if (normalized) {
      sessionStorage.setItem(API_CREDENTIAL_STORAGE_KEY, normalized)
    } else {
      sessionStorage.removeItem(API_CREDENTIAL_STORAGE_KEY)
    }
  } catch {
    // Storage can be unavailable in hardened/private browser contexts. The
    // next request will simply proceed without an Authorization header.
  }
}
