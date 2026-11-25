/**
 * Minimal JWT payload decoding (no signature verification — the gateway verifies tokens; the UI
 * only reads non-sensitive claims such as `managed_team_ids`, which `UserOut` does not carry).
 */
export function decodeJwt<T = Record<string, unknown>>(token: string | null | undefined): T | null {
  if (!token) return null;
  const parts = token.split('.');
  if (parts.length < 2 || !parts[1]) return null;
  try {
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
    const binary = atob(padded);
    const bytes = Uint8Array.from(binary, (ch) => ch.charCodeAt(0));
    const json = new TextDecoder().decode(bytes);
    const payload = JSON.parse(json);
    return payload && typeof payload === 'object' ? (payload as T) : null;
  } catch {
    return null;
  }
}

/** True when the `exp` claim is in the past (with a small clock-skew allowance). */
export function isExpired(claims: { exp?: number } | null, nowMs = Date.now(), skewSeconds = 30): boolean {
  if (!claims || typeof claims.exp !== 'number') return true;
  return claims.exp * 1000 <= nowMs + skewSeconds * 1000;
}
