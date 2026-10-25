"""Long serial batches and busy peers must not look like broken configuration."""
import io
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest
from app import population_check as pc


@pytest.fixture
def bridge(monkeypatch):
    monkeypatch.setenv('JIFF_BRIDGE_URL', 'http://127.0.0.1:9112')
    monkeypatch.setenv('JIFF_BRIDGE_TOKEN', 'secret-token-that-must-not-be-logged-123456')
    clock = [0]
    monkeypatch.setattr(pc.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(pc.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    return clock


def response(value):
    return io.BytesIO(json.dumps(value).encode())


def test_multi_profile_batch_can_finish_after_old_sixty_five_second_cutoff(bridge, monkeypatch, caplog):
    public = json.loads((Path(__file__).resolve().parents[1]/'jiff/fixtures/public-manifest.json').read_text())
    profiles = [{'Class': value} for value in public['schema']['Class']]
    counts = [1, 6, 1]
    def slow_peer(req, timeout):
        assert timeout >= len(profiles) * 55
        bridge[0] += 75
        assert bridge[0] < timeout
        return response({'counts': counts, 'binding': 'bound', 'fingerprint': pc.digest(public),
                         'population_id': public['population_id'], 'version': public['version']})
    monkeypatch.setattr(pc, 'urlopen', slow_peer)
    with caplog.at_level('INFO'):
        assert pc.batch(profiles, 'bound', public) == counts
    assert '75.0' in caplog.text
    assert 'Senior' not in caplog.text and 'secret-token' not in caplog.text


def test_busy_replies_wait_then_complete_without_replaying_started_work(bridge, monkeypatch):
    calls = []
    def peer(req, timeout):
        calls.append(req.data)
        if len(calls) <= 2:
            raise HTTPError(req.full_url, 409, 'busy', {}, io.BytesIO())
        return response({'counts': [1]})
    monkeypatch.setattr(pc, 'urlopen', peer)
    assert pc.call('/batch', {'profiles': [{'Class': 'Senior'}]}) == {'counts': [1]}
    assert len(calls) == 3 and len(set(calls)) == 1
    assert bridge[0] == 2


def test_persistent_busy_peer_has_bounded_wait_and_clear_message(bridge, monkeypatch):
    def busy(req, timeout):
        raise HTTPError(req.full_url, 409, 'busy', {}, io.BytesIO())
    monkeypatch.setattr(pc, 'urlopen', busy)
    with pytest.raises(pc.PopulationError, match='Another document is still being checked'):
        pc.call('/batch', {'profiles': []})
    assert bridge[0] == pc.BUSY_WAIT_SECONDS


@pytest.mark.parametrize('failure', ['timeout', 'computation'])
def test_interrupted_computation_is_not_automatically_replayed(bridge, monkeypatch, caplog, failure):
    calls = []
    def broken(req, timeout):
        calls.append(req)
        if failure == 'timeout':
            raise TimeoutError('potentially sensitive details must not be logged')
        raise HTTPError(req.full_url, 503, 'private peer detail', {}, io.BytesIO())
    monkeypatch.setattr(pc, 'urlopen', broken)
    with pytest.raises(pc.PopulationError, match='Review remains paused'):
        pc.call('/batch', {'profiles': [{'Class': 'Senior'}]})
    assert len(calls) == 1
    assert 'Senior' not in caplog.text and 'secret-token' not in caplog.text
    assert 'potentially sensitive' not in caplog.text and 'private peer detail' not in caplog.text
