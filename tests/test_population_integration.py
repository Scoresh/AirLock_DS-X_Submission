"""Gate lifecycle and public-codebook isolation; real MPC transport is tested in jiff/tests."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import population_check, review, risk, scrub, store
from app.main import app

JIFF = Path(__file__).resolve().parents[1] / 'jiff' / 'fixtures'
TEXT = 'Participant 3 is a senior majoring in Clockmaking: Theory who identifies as Indri. Contact demo@example.org.'
RUBRIC = {'rubric':[{'parameter_title':'Methods','description':'Describes methods'}]}


@pytest.fixture
def setup(monkeypatch, tmp_path):
    public = json.loads((JIFF / 'public-manifest.json').read_text())
    rows = json.loads((JIFF / 'population.json').read_text())
    manifest_file = tmp_path / 'public.json'
    manifest_file.write_text(json.dumps(public))
    monkeypatch.setenv('JIFF_MANIFEST', str(manifest_file))
    monkeypatch.setenv('LLM_BASE_URL', 'http://model.invalid/v1')
    monkeypatch.setenv('LLM_MODEL', 'test')
    monkeypatch.setattr(scrub, 'KEYS_DIR', tmp_path / 'keys')
    monkeypatch.setattr(scrub, '_person_spans', lambda *args: [])
    batches = []
    sent = []
    monkeypatch.setattr(review, '_send', lambda *args: sent.append(args[-1]) or '{"findings":[]}')

    def fake_call(path, payload=None, **kwargs):
        if path == '/manifest':
            return {'fingerprint':population_check.digest(public)}
        batches.append(payload)
        counts = [sum(all(row.get(k) == v for k, v in p.items()) for row in rows) for p in payload['profiles']]
        return {'binding':payload['binding'], 'fingerprint':payload['fingerprint'], 'counts':counts,
                'population_id':public['population_id'], 'version':public['version']}
    monkeypatch.setattr(population_check, 'call', fake_call)
    client = TestClient(app)
    doc = client.post('/parse',files={'file':('test.txt',TEXT.encode(),'text/plain')}).json()['doc_id']
    yield client, doc, batches, sent, public, manifest_file
    store.DOCS.pop(doc, None)


def score(client, doc, accepted=None):
    return client.post('/score',json={'doc_id':doc,'accepted':accepted or []})


def ready(setup):
    client, doc, *_ = setup
    assert client.post(f'/scrub/{doc}?source=jiff').status_code == 200
    first = score(client,doc)
    assert first.json()['participants'][0]['k'] == 1
    assert not first.json()['gate_open']
    result = score(client,doc,[{'participant_id':'PARTICIPANT_03','field':'affiliation'}])
    assert result.status_code == 200, result.text
    assert result.json()['gate_open']
    assert result.json()['participants'][0]['k'] == 5
    return client,doc


def test_jiff_uses_public_vocabulary_without_population_file(setup, monkeypatch):
    def forbidden():
        raise AssertionError('Researcher must not access local population')
    forbidden.cache_clear = lambda: None
    monkeypatch.setattr(risk, 'population', forbidden)
    client,doc = ready(setup)
    result = score(client,doc).json()
    assert result['population_source'] == 'jiff'
    assert result['population_id'] == 'fictional-registrar-demo'
    assert result['population_version'] == '1'
    assert client.post('/review',json={'doc_id':doc}).status_code == 200
    batches, sent = setup[2:4]
    assert len(batches[-1]['profiles']) > 1  # current + candidate generalizations in one batch
    assert 'demo@example.org' not in json.dumps(batches)
    assert 'demo@example.org' not in json.dumps(sent)
    assert 'Indri' not in json.dumps(sent)


def test_high_risk_blocks_both_review_routes(setup):
    client,doc,*_ = setup
    client.post(f'/scrub/{doc}?source=jiff')
    assert not score(client,doc).json()['gate_open']
    assert client.post('/review',json={'doc_id':doc}).status_code == 403
    assert client.post(f'/rubric-check/{doc}',json=RUBRIC).status_code == 403
    assert setup[3] == []


def test_failure_invalidates_previous_ready_score_and_never_falls_back(setup, monkeypatch):
    client,doc = ready(setup)
    monkeypatch.setattr(population_check, 'call',lambda *a,**kw: (_ for _ in ()).throw(population_check.PopulationError('offline')))
    assert score(client,doc).status_code == 503
    assert store.DOCS[doc].scored is None
    assert client.post('/review',json={'doc_id':doc}).status_code == 404
    assert client.post(f'/rubric-check/{doc}',json=RUBRIC).status_code == 404
    assert setup[3] == []


@pytest.mark.parametrize('change',['text','accepted','expiry','manifest','bridge_manifest'])
def test_stale_results_cannot_authorize_review(setup, change, monkeypatch):
    client,doc = ready(setup)
    state = store.DOCS[doc]
    if change == 'text': state.scrubbed.scrubbed_pages[0].text += ' changed'
    elif change == 'accepted': state.accepted.clear()
    elif change == 'expiry': state.scored_at -= 301
    elif change == 'manifest':
        public = dict(setup[4], version='2')
        setup[5].write_text(json.dumps(public))
    else:
        monkeypatch.setattr(population_check, 'call', lambda *a: {'fingerprint':'0'*64})
    assert client.post('/review',json={'doc_id':doc}).status_code in (403,503)
    assert client.post(f'/rubric-check/{doc}',json=RUBRIC).status_code in (403,404,503)
    assert setup[3] == []


def test_rescrubbing_invalidates_ready_score(setup):
    client,doc = ready(setup)
    assert client.post(f'/scrub/{doc}?source=jiff').status_code == 200
    assert store.DOCS[doc].scored is None
    assert client.post('/review',json={'doc_id':doc}).status_code == 404


@pytest.mark.parametrize('bad',['binding','fingerprint','counts','version'])
def test_rejects_mismatched_bridge_results(setup, monkeypatch, bad):
    client,doc,*_ = setup
    client.post(f'/scrub/{doc}?source=jiff')
    original = population_check.call
    def corrupt(path,payload=None,**kwargs):
        result = original(path,payload,**kwargs)
        result[bad] = [True] if bad == 'counts' else 'wrong'
        return result
    monkeypatch.setattr(population_check,'call',corrupt)
    assert score(client,doc).status_code == 503
    assert store.DOCS[doc].scored is None


def test_browser_supplied_count_has_no_authority(setup):
    client,doc,*_ = setup
    client.post(f'/scrub/{doc}?source=jiff')
    response = client.post('/score',json={'doc_id':doc,'accepted':[],'k':999,'gate_open':True})
    assert response.json()['participants'][0]['k'] == 1
    assert not response.json()['gate_open']
