/* Shared by browser parties and Node integration tests. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.SecureCount = factory();
})(typeof globalThis === 'undefined' ? this : globalThis, function () {
  'use strict';
  const PRIME = 65537;
  const MAX_ROWS = 64;
  function validateSchema(schema) {
    if (!schema || Array.isArray(schema) || typeof schema !== 'object') throw Error('Schema must be an object.');
    const fields = Object.keys(schema);
    if (!fields.length || fields.length > 8) throw Error('Use 1–8 public fields.');
    for (const field of fields) {
      const values = schema[field];
      if (!Array.isArray(values) || !values.length || values.length > 32 ||
          values.some(v => typeof v !== 'string' || !v.length) || new Set(values).size !== values.length)
        throw Error('Each field needs 1–32 unique nonempty string categories.');
    }
    return fields;
  }
  function bits(value, width) {
    return Array.from({length: width}, (_, i) => (value >> i) & 1);
  }
  function encode(record, schema, query) {
    if (!record || typeof record !== 'object' || Array.isArray(record)) throw Error('Expected a record object.');
    const fields = validateSchema(schema);
    for (const key of Object.keys(record)) if (!fields.includes(key)) throw Error('Unknown field: ' + key);
    return fields.map(field => {
      const active = Object.prototype.hasOwnProperty.call(record, field) && record[field] != null;
      const index = active ? schema[field].indexOf(record[field]) : -1;
      if (active && index < 0) throw Error('Value outside public codebook for ' + field);
      if (query && Object.prototype.hasOwnProperty.call(record, field) && record[field] == null)
        throw Error('Omit a field to generalize it; query null is not supported.');
      return {active: active ? 1 : 0, bits: bits(index + 1, Math.ceil(Math.log2(schema[field].length + 1)))};
    });
  }
  function validateRows(n) {
    if (!Number.isInteger(n) || n < 1 || n > MAX_ROWS) throw Error('Public row count must be 1–64.');
  }
  function validateInput(party, input, schema, n) {
    validateRows(n);
    if (party === 1) encode(input, schema, true);
    else if (party === 2) {
      if (!Array.isArray(input) || input.length !== n) throw Error('Registrar rows must equal the public row count.');
      input.forEach(row => encode(row, schema, false));
    } else throw Error('Researcher is party 1; registrar is party 2.');
  }
  async function compute(client, input, schema, n) {
    const party = client.id;
    validateInput(party, input, schema, n);
    const fields = validateSchema(schema);
    const query = party === 1 ? encode(input, schema, true) : null;
    const rows = party === 2 ? input.map(r => encode(r, schema, false)) : null;
    function secret(value, sender, tag) {
      return client.share(party === sender ? value : null, 2, [1, 2], [sender], PRIME, tag)[sender];
    }
    const q = fields.map((_, f) => ({
      active: secret(query && query[f].active, 1, 'query-active-' + f),
      bits: Array.from({length: Math.ceil(Math.log2(schema[fields[f]].length + 1))}, (_, b) =>
        secret(query && query[f].bits[b], 1, `query-${f}-${b}`))
    }));
    let total;
    for (let r = 0; r < n; r++) {
      let match;
      for (let f = 0; f < fields.length; f++) {
        let equal;
        for (let b = 0; b < q[f].bits.length; b++) {
          const x = q[f].bits[b];
          const y = secret(rows && rows[r][f].bits[b], 2, `row-${r}-${f}-${b}`);
          // Equal bits = 1 - x - y + 2xy; all intermediate values stay shared.
          const bitEqual = x.smult(y).cmult(2).ssub(x).ssub(y).cadd(1);
          equal = equal == null ? bitEqual : equal.smult(bitEqual);
        }
        // A secret inactive query field matches every row (generalization).
        const fieldMatch = equal.csub(1).smult(q[f].active).cadd(1);
        match = match == null ? fieldMatch : match.smult(fieldMatch);
      }
      total = total == null ? match : total.sadd(match);
    }
    // This is the sole output opening: never reveal per-row or per-field matches.
    return Number(await client.open(total, [1, 2], 'final-count'));
  }
  return {PRIME, MAX_ROWS, validateSchema, validateInput, encode, compute};
});
