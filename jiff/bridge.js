/* Trusted researcher-side process. Bind locally; never deploy as a public count API. */
const http = require('node:http');
const crypto = require('node:crypto');
const {authorized, body, reply, requireToken, fingerprint, call} = require('./transport');
const {loadManifest} = require('./manifest');
const {count} = require('./party');
const protocol = require('./public/protocol');
function createBridge({manifest, token, coordToken, relay}) {
  const fp = fingerprint(manifest);
  let busy = false;
  return http.createServer(async (req, res) => {
    if (!authorized(req, token)) return reply(res, 401, {error:'Unauthorized'});
    if (req.method === 'GET' && req.url === '/manifest') return reply(res, 200, {manifest, fingerprint:fp});
    if (req.method !== 'POST' || req.url !== '/batch') return reply(res, 404, {});
    if (busy) return reply(res, 409, {error:'Another MPC batch is running'});
    busy = true;
    try {
      const payload = await body(req);
      if (payload.fingerprint !== fp || !/^[a-f0-9]{64}$/.test(payload.binding) ||
          !Array.isArray(payload.profiles) || !payload.profiles.length || payload.profiles.length > 32)
        return reply(res, 400, {error:'Invalid batch or stale manifest'});
      payload.profiles.forEach(p => protocol.validateInput(1, p, manifest.schema, manifest.row_count));
      const id = crypto.randomUUID();
      await call(relay + '/jobs', coordToken, 'POST', {id, fingerprint:fp, queries:payload.profiles.length});
      // One batch request; serial sessions keep independent processes synchronized.
      const counts = [];
      for (let i = 0; i < payload.profiles.length; i++) {
        counts.push(await count(relay, id + '-' + i, 1, payload.profiles[i], manifest));
      }
      return reply(res, 200, {binding:payload.binding, fingerprint:fp, counts, population_id:manifest.population_id, version:manifest.version});
    } catch (_) {
      return reply(res, 503, {error:'Secure population check failed; no local fallback was used'});
    } finally { busy = false; }
  });
}
if (require.main === module) {
  const bridge = createBridge({manifest:loadManifest(), token:requireToken('JIFF_BRIDGE_TOKEN'),
    coordToken:requireToken('JIFF_COORD_TOKEN'), relay:process.env.JIFF_RELAY_URL || 'http://127.0.0.1:9111'});
  bridge.listen(Number(process.env.JIFF_BRIDGE_PORT || 9112), '127.0.0.1', () => console.log('Researcher bridge ready on localhost'));
}
module.exports = {createBridge};
