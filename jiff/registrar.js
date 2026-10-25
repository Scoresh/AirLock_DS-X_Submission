/* Population records are read only in this owner-side process. */
const fs = require('node:fs');
const {loadManifest} = require('./manifest');
const {fingerprint, call, requireToken} = require('./transport');
const {count} = require('./party');
const protocol = require('./public/protocol');
function startRegistrar({manifest, rows, token, relay, onResult = () => {}}) {
  protocol.validateInput(2, rows, manifest.schema, manifest.row_count);
  let stopped = false;
  const active = new Set();
  async function poll() {
    while (!stopped) {
      try {
        const {job} = await call(relay + '/jobs', token);
        if (job && job.fingerprint === fingerprint(manifest)) {
          const work = (async () => {
            const counts = [];
            for (let i = 0; i < job.queries; i++) counts.push(await count(relay, job.id + '-' + i, 2, rows, manifest));
            return counts;
          })();
          active.add(work);
          work.then(onResult).catch(() => {}).finally(() => active.delete(work));
        }
      } catch (_) { /* relay offline: no raw-data fallback */ }
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }
  const running = poll();
  return async () => { stopped = true; await running; await Promise.allSettled([...active]); };
}
if (require.main === module) {
  if (!process.env.JIFF_POPULATION) throw Error('Set JIFF_POPULATION to the private normalized population JSON');
  const rows = JSON.parse(fs.readFileSync(process.env.JIFF_POPULATION, 'utf8'));
  startRegistrar({manifest:loadManifest(), rows, token:requireToken('JIFF_COORD_TOKEN'),
    relay:process.env.JIFF_RELAY_URL || 'http://127.0.0.1:9111',
    onResult:counts => console.log('Completed authorized demo batch; comparisons:', counts.length)});
  console.log('Registrar ready. Population stays in this process.');
}
module.exports = {startRegistrar};
