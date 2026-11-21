// Build-time maths: reads [{tex, display}] (JSON, stdin), writes [{html, error}] (JSON, stdout).
// Uses the vendored KaTeX (site/vendor/katex/katex.min.js). Called once per build by site/madasite/mathrender.py.
'use strict';
const path = require('path');
const katex = require(path.join(__dirname, '..', 'vendor', 'katex', 'katex.min.js'));
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (c) => { input += c; });
process.stdin.on('end', () => {
  const items = JSON.parse(input);
  const out = items.map(({ tex, display }) => {
    try {
      return { html: katex.renderToString(tex, {
        displayMode: !!display, throwOnError: true, trust: false, strict: 'ignore',
        output: 'htmlAndMathml', maxExpand: 500, maxSize: 20,
      }), error: null };
    } catch (e) {
      return { html: null, error: String(e && e.message || e) };
    }
  });
  process.stdout.write(JSON.stringify(out));
});
