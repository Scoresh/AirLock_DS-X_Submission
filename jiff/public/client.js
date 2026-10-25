/* Private inputs remain in this tab; only protocol shares go to JIFF. */
const $ = id => document.getElementById(id);
const role = new URLSearchParams(location.search).get('party');
if (role === '1' || role === '2') $('party').value = role;
let client;
$('file').onchange = async () => {
  if ($('file').files[0]) $('input').value = await $('file').files[0].text();
};
$('sample').onclick = async () => {
  const sample = await (await fetch('/example.json')).json();
  $('schema').value = JSON.stringify(sample.schema, null, 2);
  $('input').value = JSON.stringify($('party').value === '1' ? sample.profile : sample.rows, null, 2);
  $('count').value = sample.rows.length;
};
$('run').onclick = async () => {
  let timer;
  try {
    const session = $('session').value.trim();
    if (!/^[a-zA-Z0-9_-]{12,80}$/.test(session)) throw Error('Use a fresh session ID with 12–80 letters, numbers, underscores or hyphens.');
    const schema = JSON.parse($('schema').value);
    const input = JSON.parse($('input').value);
    const count = Number($('count').value);
    const party = Number($('party').value);
    SecureCount.validateInput(party, input, schema, count);
    // Public transcript parameters bound to the computation ID: mismatched peers never compute together.
    const publicContract = JSON.stringify({fields: Object.entries(schema), count, version: 1});
    const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(publicContract));
    const fingerprint = Array.from(new Uint8Array(hash), b => b.toString(16).padStart(2, '0')).join('');
    $('run').disabled = true;
    $('status').textContent = 'Waiting for the other party with the same session, schema and row count…';
    timer = setTimeout(() => {
      $('status').textContent = 'Timed out. Check both parties’ public parameters, then reload both windows with a fresh session ID.';
      if (client) client.disconnect(false, true);
    }, 60000);
    client = new JIFFClient(location.origin, session + '-' + fingerprint, {
      party_id: party, party_count: 2, Zp: SecureCount.PRIME, crypto_provider: true,
      onError: () => {
        clearTimeout(timer);
        $('status').textContent = 'Connection or protocol failed. Reload both windows with a fresh session ID.';
        if (client) client.disconnect(false, true);
      },
      onConnect: async instance => {
        try {
          const start = performance.now();
          const k = await SecureCount.compute(instance, input, schema, count);
          clearTimeout(timer);
          $('status').textContent = `${k} matching records · ${(performance.now() - start).toFixed(0)} ms · ${k < 5 ? 'below the review threshold' : 'review threshold met'}. This standalone result does not change the application’s privacy gate.`;
          instance.disconnect(true, true);
        } catch (_) {
          clearTimeout(timer);
          $('status').textContent = 'Computation failed. Reload both windows with a fresh session ID.';
          instance.disconnect(false, true);
        }
      }
    });
  } catch (err) {
    clearTimeout(timer);
    $('status').textContent = err.message;
  }
};
