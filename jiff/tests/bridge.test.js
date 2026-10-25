const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const {createServer} = require('../server');
const {createBridge} = require('../bridge');
const {spawn} = require('node:child_process');
const path = require('node:path');
const {call, fingerprint} = require('../transport');
const manifest = require('../fixtures/public-manifest.json');
const rows = require('../fixtures/population.json');

async function listen(server) {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return 'http://127.0.0.1:' + server.address().port;
}

test('trusted bridge and independent registrar complete an authenticated batch', {timeout:40000}, async () => {
  const token = crypto.randomBytes(32).toString('hex');
  const coordToken = crypto.randomBytes(32).toString('hex');
  const {server, jiff} = createServer({token:coordToken});
  const relay = await listen(server);
  const bridge = createBridge({manifest, token, coordToken, relay});
  const url = await listen(bridge);
  // Separate OS process catches dropped outgoing shares on premature disconnect.
  const child = spawn(process.execPath, ['registrar.js'], {cwd:path.resolve(__dirname,'..'),
    env:{...process.env, JIFF_COORD_TOKEN:coordToken, JIFF_RELAY_URL:relay,
      JIFF_MANIFEST:path.resolve(__dirname,'../fixtures/public-manifest.json'),
      JIFF_POPULATION:path.resolve(__dirname,'../fixtures/population.json')}, stdio:'ignore'});
  const stop = async () => {
    const exited = new Promise(resolve => child.once('exit',resolve));
    child.kill();
    await exited;
  };
  try {
    assert.equal((await fetch(url+'/manifest')).status,401);
    assert.equal((await fetch(relay+'/jobs')).status,401);
    const publicInfo = await call(url+'/manifest',token);
    assert.equal(publicInfo.fingerprint,fingerprint(manifest));
    assert.equal(JSON.stringify(publicInfo).includes('rows'),false);
    const profiles = [
      {Class:'Senior',MAJfirst:'Clockmaking: Theory',affiliation:'Indri'},
      {Class:'Senior',MAJfirst:'Clockmaking: Theory'},
      {Class:'Other',MAJfirst:'Clockmaking: Theory'}, {}
    ];
    const binding = crypto.randomBytes(32).toString('hex');
    const result = await call(url+'/batch',token,'POST',{fingerprint:publicInfo.fingerprint,binding,profiles});
    assert.deepEqual(result.counts,[1,5,0,8]);
    assert.equal(result.binding,binding);
    assert.equal(result.version,manifest.version);
    const bad = await fetch(url+'/batch',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},
      body:JSON.stringify({fingerprint:'0'.repeat(64),binding,profiles})});
    assert.equal(bad.status,400);
    const unknown = await fetch(url+'/batch',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},
      body:JSON.stringify({fingerprint:publicInfo.fingerprint,binding,profiles:[{Class:'Unapproved'}]})});
    assert.equal(unknown.status,503);
  } finally {
    await stop();
    jiff.io.close();
    await Promise.all([new Promise(resolve => bridge.close(resolve)),new Promise(resolve => server.close(resolve))]);
  }

});
