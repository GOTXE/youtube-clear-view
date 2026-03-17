// Minifica todos los archivos CSS de src/ y los escribe en dest/
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { join, basename } from 'node:path';
import { transform } from 'lightningcss';

const [,, srcDir, destDir] = process.argv;
if (!srcDir || !destDir) {
  console.error('Usage: minify-css.mjs <srcDir> <destDir>');
  process.exit(1);
}

let totalIn = 0;
let totalOut = 0;

for (const file of readdirSync(srcDir).filter(f => f.endsWith('.css'))) {
  const inputPath = join(srcDir, file);
  const outputPath = join(destDir, file);
  const code = readFileSync(inputPath);
  const { code: minified } = transform({ filename: file, code, minify: true });
  writeFileSync(outputPath, minified);
  totalIn += code.length;
  totalOut += minified.length;
}

const pct = Math.round((1 - totalOut / totalIn) * 100);
console.log(`CSS minified: ${totalIn} → ${totalOut} bytes (${pct}% reduction)`);
