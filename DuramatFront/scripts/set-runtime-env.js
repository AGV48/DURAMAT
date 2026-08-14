const fs = require('fs');
const path = require('path');

const apiUrl = process.env.API_BASE_URL || '';
const outDir = path.join(__dirname, '..', 'src', 'assets');
if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
const outFile = path.join(outDir, 'runtime-config.js');
const content = `window.API_BASE_URL = ${JSON.stringify(apiUrl)};`;
fs.writeFileSync(outFile, content, 'utf8');
console.log('Wrote runtime config to', outFile);
