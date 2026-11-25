/** Colour-scheme preference: follows the OS by default, can be forced light/dark (persisted). */
export type ThemePreference = 'system' | 'light' | 'dark';

const KEY = 'teampulse.theme';

function read(): ThemePreference {
  try {
    const value = localStorage.getItem(KEY);
    return value === 'light' || value === 'dark' ? value : 'system';
  } catch {
    return 'system';
  }
}

class ThemeStore {
  preference = $state<ThemePreference>('system');

  init(): void {
    if (typeof document === 'undefined') return;
    this.preference = read();
    this.#apply();
  }

  set(preference: ThemePreference): void {
    this.preference = preference;
    try {
      if (preference === 'system') localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, preference);
    } catch {
      /* ignore */
    }
    this.#apply();
  }

  cycle(): void {
    this.set(this.preference === 'system' ? 'light' : this.preference === 'light' ? 'dark' : 'system');
  }

  #apply(): void {
    if (typeof document === 'undefined') return;
    // tokens.css reads `data-theme` on <html>; absent = follow prefers-color-scheme.
    if (this.preference === 'system') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', this.preference);
  }
}

export const theme = new ThemeStore();
