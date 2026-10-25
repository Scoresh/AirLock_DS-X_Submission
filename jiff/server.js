const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const JIFFServer = require('jiff-mpc/lib/jiff-server');
function createServer(options = {}) {
  const {authorized, body, reply} = require('./transport');
  const token = options.token || process.env.JIFF_COORD_TOKEN;
  const jobs = [];

  // Fixed allowlist: never expose population files, keys, or node_modules as static roots.
  const files = {
    '/': ['public/index.html', 'text/html'],
    '/client.js': ['public/client.js', 'text/javascript'],
    '/protocol.js': ['public/protocol.js', 'text/javascript'],
    '/example.json': ['public/example.json', 'application/json'],
    '/jiff-client.js': [require.resolve('jiff-mpc/dist/jiff-client.js'), 'text/javascript']
  };
  const server = http.createServer(async (req, res) => {
    if (req.url === '/jobs') {
      if (!authorized(req, token)) return reply(res, 401, {error:'Unauthorized'});
      try {
        while (jobs.length && jobs[0].expires < Date.now()) jobs.shift();
        if (req.method === 'GET') return reply(res, 200, {job: jobs.shift() || null});
        if (req.method !== 'POST') return reply(res, 405, {});
        const job = await body(req);
        if (!/^[a-f0-9-]{36}$/.test(job.id) || !/^[a-f0-9]{64}$/.test(job.fingerprint) || !Number.isInteger(job.queries) || job.queries < 1 || job.queries > 32 || jobs.length >= 32) return reply(res, 400, {error:'Invalid public job metadata'});
        jobs.push({id:job.id, fingerprint:job.fingerprint, queries:job.queries, expires:Date.now()+60000});
        return reply(res, 200, {ok:true});
      } catch (_) { return reply(res, 400, {error:'Invalid job'}); }
    }
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
