const fs = require('node:fs');
const path = require('node:path');
const protocol = require('./public/protocol');
function loadManifest(file = process.env.JIFF_MANIFEST) {
  if (!file) throw Error('Set JIFF_MANIFEST to the approved public codebook/manifest JSON');
  const manifest = JSON.parse(fs.readFileSync(path.resolve(file), 'utf8'));
  if (!manifest.population_id || !manifest.version || !Number.isInteger(manifest.row_count) || manifest.row_count < 1 || manifest.row_count > protocol.MAX_ROWS) throw Error('Invalid manifest');
  protocol.validateSchema(manifest.schema);
  return manifest;
}
module.exports = {loadManifest};
