import { describe, expect, it } from 'vitest';
import { decodeJwt, isExpired } from './jwt';

function encode(payload: object): string {
  const b64url = (s: string) => Buffer.from(s, 'utf8').toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return `${b64url('{"alg":"RS256","typ":"JWT"}')}.${b64url(JSON.stringify(payload))}.signature`;
}

describe('decodeJwt', () => {
  it('reads claims including managed_team_ids and unicode names', () => {
    const token = encode({ sub: 'u1', name: 'Zoë Ångström', role: 'manager', managed_team_ids: ['t1', 't2'], exp: 2000000000 });
    const claims = decodeJwt<{ name: string; role: string; managed_team_ids: string[] }>(token);
    expect(claims?.role).toBe('manager');
    expect(claims?.managed_team_ids).toEqual(['t1', 't2']);
    expect(claims?.name).toBe('Zoë Ångström');
  });

  it('returns null for malformed tokens', () => {
    expect(decodeJwt('not-a-jwt')).toBeNull();
    expect(decodeJwt('a.%%%.c')).toBeNull();
    expect(decodeJwt(null)).toBeNull();
  });

  it('detects expiry with clock skew', () => {
    const now = 1_762_560_000_000;
    expect(isExpired({ exp: now / 1000 + 900 }, now)).toBe(false);
    expect(isExpired({ exp: now / 1000 + 10 }, now)).toBe(true);
    expect(isExpired(null, now)).toBe(true);
  });
});
