"""Deployment readiness must not advertise an unconfigured JIFF source."""
import json
from pathlib import Path

from fastapi.testclient import TestClient
from app import population_check, scrub
from app.main import app


def test_missing_jiff_configuration_is_reported_as_unavailable(monkeypatch):
    monkeypatch.delenv('JIFF_MANIFEST', raising=False)
    monkeypatch.delenv('JIFF_BRIDGE_TOKEN', raising=False)
    monkeypatch.setattr(scrub, '_analyzer', lambda: None)
    result = TestClient(app).get('/status?source=jiff').json()
    assert not result['population_sources']['jiff']['available']
    assert not result['setup']['ready']
    assert 'not enabled' in result['setup']['issues'][0]
    assert 'JIFF_MANIFEST' not in result['setup']['issues'][0]


def test_healthy_jiff_and_hosted_mode_are_reported_without_secrets(monkeypatch):
    path = Path(__file__).resolve().parents[1]/'jiff/fixtures/public-manifest.json'
    public = json.loads(path.read_text())
    token = 'a-test-token-that-must-never-appear-in-status'
    monkeypatch.setenv('JIFF_MANIFEST',str(path))
    monkeypatch.setenv('JIFF_BRIDGE_TOKEN',token)
    monkeypatch.setenv('STRANGERTHESIS_DEPLOYMENT_MODE','hosted-demo')
    monkeypatch.setattr(scrub, '_analyzer', lambda: None)
    monkeypatch.setattr(population_check,'call',lambda *args,**kwargs:{'fingerprint':population_check.digest(public)})
    result = TestClient(app).get('/status?source=jiff')
    assert result.json()['population_sources']['jiff']['available']
    assert result.json()['setup']['ready']
    assert result.json()['deployment_mode'] == 'hosted-demo'
    assert token not in result.text


def test_mismatched_bridge_manifest_does_not_advertise_ready(monkeypatch):
    path = Path(__file__).resolve().parents[1]/'jiff/fixtures/public-manifest.json'
    monkeypatch.setenv('JIFF_MANIFEST',str(path))
    monkeypatch.setenv('JIFF_BRIDGE_TOKEN','x'*40)
    monkeypatch.setattr(population_check,'call',lambda *args,**kwargs:{'fingerprint':'wrong'})
    assert not population_check.availability()['available']


def test_busy_bridge_remains_configured_and_can_be_retried(monkeypatch):
    path = Path(__file__).resolve().parents[1]/'jiff/fixtures/public-manifest.json'
    monkeypatch.setenv('JIFF_MANIFEST',str(path))
    monkeypatch.setenv('JIFF_BRIDGE_TOKEN','x'*40)
    def busy(*args,**kwargs):
        raise population_check.PopulationError('temporary timeout')
    monkeypatch.setattr(population_check,'call',busy)
    state = population_check.availability()
    assert state['configured'] is True
    assert state['available'] is False
    assert 'temporarily unavailable' in state['message']
    assert 'not enabled' not in state['message']
    public = json.loads(path.read_text())
    monkeypatch.setattr(population_check,'call',lambda *args,**kwargs:{'fingerprint':population_check.digest(public)})
    assert population_check.availability()['available'] is True
