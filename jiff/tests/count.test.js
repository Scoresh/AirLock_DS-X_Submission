const test = require('node:test');
const assert = require('node:assert/strict');
const JIFFClient = require('jiff-mpc/lib/jiff-client');
const {createServer} = require('../server');
const protocol = require('../public/protocol');
const example = require('../public/example.json');

async function secureCount(server, profile) {
  const session = 'test-' + require('node:crypto').randomUUID();
  const clients = [];
  const started = Date.now();
  try {
    const answers = await Promise.all([1, 2].map(party => new Promise((resolve, reject) => {
      const client = new JIFFClient('http://127.0.0.1:' + server.address().port, session, {
        party_id: party, party_count: 2, Zp: protocol.PRIME, crypto_provider: true,
        onError: (_, error) => reject(Error(String(error))),
        onConnect: async instance => {
          const originalOpen = instance.open.bind(instance);
          let openings = 0;
          instance.open = (share, receivers, id) => {
            openings++;
            assert.equal(id, 'final-count');
            return originalOpen(share, receivers, id);
          };
          try {
            const value = await protocol.compute(instance, party === 1 ? profile : example.rows, example.schema, example.rows.length);
            assert.equal(openings, 1);
            resolve(value);
          } catch (err) { reject(err); }
        }
      });
      clients.push(client);
    })));
    const expected = example.rows.filter(row => Object.entries(profile).every(([f, v]) => row[f] === v)).length;
    assert.deepEqual(answers, [expected, expected]);
    return Date.now() - started;
  } finally {
    clients.forEach(c => c.disconnect(false, true));
  }
}

test('input validation fails closed', () => {
  assert.throws(() => protocol.validateInput(1, {unknown:'x'}, example.schema, 8));
  assert.throws(() => protocol.validateInput(1, {Class:'Unknown'}, example.schema, 8));
  assert.throws(() => protocol.validateInput(1, {Class:null}, example.schema, 8));
  assert.throws(() => protocol.validateInput(2, [], example.schema, 8));
  assert.throws(() => protocol.validateInput(1, {}, example.schema, 65537));
});

test('real two-party count agrees with plaintext oracle; only total opened', {timeout: 55000}, async t => {
  const {server, jiff} = createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    for (const [name, profile] of [
      ['exact profile: k=1', example.profile],
      ['affiliation omitted: k=5', {Class:'Senior', MAJfirstfield:'Clockmaking'}],
      ['zero matches', {Class:'Other', MAJfirstfield:'Clockmaking'}],
      ['all omitted: k=8', {}]
    ]) {
      await t.test(name, async () => { const elapsed = await secureCount(server, profile); t.diagnostic(name + ': ' + elapsed + 'ms'); });
    }
    await t.test('server does not serve local population or keys', async () => {
      for (const file of ['/keys/x.json','/data/NSSE-synthetic.csv','/server.js']) {
        assert.equal((await fetch('http://127.0.0.1:' + server.address().port + file)).status, 404);
      }
    });
  } finally {
    jiff.io.close();
    await new Promise(resolve => server.close(resolve));
  }
});
