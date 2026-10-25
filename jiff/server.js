const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const JIFFServer = require('jiff-mpc/lib/jiff-server');
function createServer() {
  // Fixed allowlist: never expose population files, keys, or node_modules as static roots.
  const files = {
    '/': ['public/index.html', 'text/html'],
    '/client.js': ['public/client.js', 'text/javascript'],
    '/protocol.js': ['public/protocol.js', 'text/javascript'],
    '/example.json': ['public/example.json', 'application/json'],
    '/jiff-client.js': [require.resolve('jiff-mpc/dist/jiff-client.js'), 'text/javascript']
  };
  const server = http.createServer((req, res) => {
    const file = files[req.url.split('?')[0]];
    if (!file || req.method !== 'GET') { res.writeHead(404); return res.end(); }
    res.setHeader('Content-Type', file[1]);
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Content-Type-Options', 'nosniff');
    fs.createReadStream(path.resolve(__dirname, file[0])).pipe(res);
  });
  const jiff = new JIFFServer(server, {logs: false});
  return {server, jiff};
}
if (require.main === module) {
  const {server} = createServer();
  server.listen(Number(process.env.PORT || 9111), '127.0.0.1', () => {
    console.log('JIFF demo: http://127.0.0.1:' + server.address().port);
  });
}
module.exports = {createServer};
