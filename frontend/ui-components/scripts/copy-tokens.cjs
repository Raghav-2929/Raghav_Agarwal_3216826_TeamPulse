// Copies the central design tokens into the published build: src/global/tokens.css -> dist/tokens.css
// (exported as "@teampulse/ui-components/tokens.css").
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const src = path.join(root, 'src', 'global', 'tokens.css');
const dest = path.join(root, 'dist', 'tokens.css');

fs.mkdirSync(path.dirname(dest), { recursive: true });
fs.copyFileSync(src, dest);
console.log(`[copy-tokens] ${path.relative(root, src)} -> ${path.relative(root, dest)}`);
