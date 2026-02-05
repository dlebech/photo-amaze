import less from 'less';
import { readFileSync, writeFileSync, mkdirSync, readdirSync } from 'fs';
import { resolve, basename } from 'path';
import CleanCSS from 'clean-css';

const CSS_SRC = 'static/css/src';
const CSS_DIST = 'static/css/dist';

mkdirSync(CSS_DIST, { recursive: true });

const files = readdirSync(CSS_SRC).filter(f => f.endsWith('.less'));

for (const file of files) {
  const input = readFileSync(resolve(CSS_SRC, file), 'utf8');
  const result = await less.render(input, {
    filename: resolve(CSS_SRC, file),
    paths: [resolve(CSS_SRC)],
  });

  const minified = new CleanCSS().minify(result.css);
  const outName = basename(file, '.less') + '.css';
  writeFileSync(resolve(CSS_DIST, outName), minified.styles);
  console.log(`Built ${outName}`);
}
