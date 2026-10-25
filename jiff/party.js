const JIFFClient = require('jiff-mpc/lib/jiff-client');
const protocol = require('./public/protocol');
function count(relay, session, party, input, manifest) {
  protocol.validateInput(party, input, manifest.schema, manifest.row_count);
  return new Promise((resolve, reject) => {
    let client;
    const timer = setTimeout(() => finish(Error('MPC timed out; registrar may be offline')), 55000);
    let done = false;
    function finish(error, value) {
      if (done) return;
      done = true;
      clearTimeout(timer);
      if (client) client.disconnect(!error, true);
      error ? reject(error) : resolve(value);
    }
    client = new JIFFClient(relay, session, {
      party_id:party, party_count:2, Zp:protocol.PRIME, crypto_provider:true,
      onError:() => finish(Error('MPC connection failed')),
      onConnect:c => c.wait_for([1, 2], async () => {
        try { finish(null, await protocol.compute(c, input, manifest.schema, manifest.row_count)); }
        catch (_) { finish(Error('MPC computation failed')); }
      })
    });
  });
}
module.exports = {count};
