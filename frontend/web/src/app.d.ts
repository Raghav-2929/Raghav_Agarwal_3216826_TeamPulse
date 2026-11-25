// See https://svelte.dev/docs/kit/types#app.d.ts
import type { ApiError } from '$lib/api/errors';

declare global {
  namespace App {
    interface Error {
      message: string;
      status?: number;
      code?: string;
    }
    // interface Locals {}
    // interface PageData {}
    interface PageState {
      _?: never;
    }
    // interface Platform {}
  }
}

export type { ApiError };
