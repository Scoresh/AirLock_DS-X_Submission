const crypto = require('node:crypto');
function authorized(req, token) {
  const actual = Buffer.from(req.headers.authorization || '');
  const expected = Buffer.from('Bearer ' + token);
  return Boolean(token && token.length >= 32 && actual.length === expected.length && crypto.timingSafeEqual(actual, expected));
}
async function body(req) {
  let text = '';
  for await (const chunk of req) {
    text += chunk;
    if (Buffer.byteLength(text) > 128 * 1024) throw Error('Request too large');
  }
  return JSON.parse(text);
}
function reply(res, status, data) {
  res.writeHead(status, {'Content-Type':'application/json','Cache-Control':'no-store'});
  res.end(JSON.stringify(data));
}
function requireToken(name) {
  const token = process.env[name];
  if (!token || token.length < 32) throw Error(name + ' must be a random token of at least 32 characters');
  return token;
}
function fingerprint(manifest) {
  return crypto.createHash('sha256').update(JSON.stringify(manifest)).digest('hex');
}
async function call(url, token, method = 'GET', data) {
  const response = await fetch(url, {method, headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},
    body:data === undefined ? undefined : JSON.stringify(data), signal:AbortSignal.timeout(65000)});
  if (!response.ok) throw Error('Peer request failed: ' + response.status);
  return response.json();
}
module.exports = {authorized, body, reply, requireToken, fingerprint, call};
