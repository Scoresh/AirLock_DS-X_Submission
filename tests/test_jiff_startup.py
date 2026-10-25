"""Startup should tolerate a slow cold start and report actual readiness failures."""
import importlib.util
from pathlib import Path
import urllib.error

import pytest

SPEC = importlib.util.spec_from_file_location('run_jiff_demo', Path(__file__).resolve().parents[1]/'backend/scripts/run_jiff_demo.py')
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class Clock:
    now = 0
    def read(self): return self.now
    def sleep(self, seconds): self.now += seconds


class Process:
    def __init__(self, code=None): self.code = code
    def poll(self): return self.code


def test_cold_start_can_take_longer_than_old_twenty_second_loop():
    clock = Clock()
    calls = []
    def fetch(url, **kwargs):
        calls.append((url, kwargs))
        if clock.now < 25:
            raise urllib.error.URLError('connection refused')
        return {'setup':{'ready':True,'issues':[]}}
    result = launcher.wait_for_services([('FastAPI',Process())], 'http://localhost:8000', timeout=30,
        fetch=fetch,clock=clock.read,sleep=clock.sleep,report=lambda *a,**kw:None)
    assert result['setup']['ready']
    assert clock.now == 25
    assert len(calls) == 26
    assert calls[0][1]['timeout'] == 30


def test_timeout_includes_backend_setup_cause():
    clock = Clock()
    with pytest.raises(RuntimeError,match='spaCy model is missing'):
        launcher.wait_for_services([('FastAPI',Process())], 'http://localhost:8000', timeout=3,
            fetch=lambda *a,**kw:{'setup':{'ready':False,'issues':['spaCy model is missing']}},
            clock=clock.read,sleep=clock.sleep,report=lambda *a,**kw:None)
    assert clock.now == 3


def test_reports_the_specific_exited_process():
    with pytest.raises(RuntimeError,match=r'Registrar exited during startup \(exit code 137\)'):
        launcher.wait_for_services([('Registrar',Process(137))],'http://localhost:8000')
