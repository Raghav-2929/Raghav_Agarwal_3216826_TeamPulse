import { Config } from '@stencil/core';

/**
 * Build configuration for @teampulse/ui-components.
 *
 * Outputs:
 *  - `dist`                    lazy-loading bundle + `loader/` (defineCustomElements()) for plain HTML / CDN use
 *  - `dist-custom-elements`    tree-shakable, self-defining custom elements in `dist/components/`
 *                              (what bundlers such as Vite/SvelteKit should consume)
 *  - `docs-readme`             per-component readme.md generated from JSDoc
 *  - `www`                     local playground (`npm start`)
 *
 * The central design-token sheet (`src/global/tokens.css`) is copied verbatim to
 * `dist/tokens.css` by `scripts/copy-tokens.cjs` (npm `postbuild`) and exported as
 * `@teampulse/ui-components/tokens.css`.
 */
export const config: Config = {
  namespace: 'teampulse',
  taskQueue: 'async',
  sourceMap: true,
  outputTargets: [
    {
      type: 'dist',
      esmLoaderPath: '../loader',
    },
    {
      type: 'dist-custom-elements',
      // index.js exports defineCustomElements() (registers every tag) plus each component's
      // defineCustomElement* for tree-shaking.
      customElementsExportBehavior: 'bundle',
      externalRuntime: false,
      generateTypeDeclarations: true,
    },
    {
      type: 'docs-readme',
      footer: '*Part of @teampulse/ui-components*',
    },
    {
      type: 'www',
      serviceWorker: null,
      copy: [{ src: 'global/tokens.css', dest: 'build/tokens.css' }],
    },
  ],
  testing: {
    browserHeadless: 'shell',
  },
};
