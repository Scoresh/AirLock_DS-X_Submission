"""Launch the synthetic integrated demo; --self-test exercises the real HTTP/MPC path."""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def request(url, data=None, headers=None):
    raw = json.dumps(data).encode() if data is not None else None
    with urllib.request.urlopen(urllib.request.Request(url, data=raw, headers=headers or {"Content-Type":"application/json"}), timeout=70) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', default=shutil.which('node'))
    parser.add_argument('--port', type=int, default=int(os.getenv('PORT', '8000')))
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--hosted-demo', action='store_true', help='Explicitly enable the synthetic co-hosted demonstration')
    parser.add_argument('--relay-port', type=int, default=9111)
    parser.add_argument('--bridge-port', type=int, default=9112)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if not args.node:
        parser.error('Node.js is required; pass --node /path/to/node')
    if args.host != '127.0.0.1' and not args.hosted_demo:
        parser.error('Public binding requires --hosted-demo; this is only a fictional-data demonstration')
    env = os.environ.copy()
    if args.hosted_demo:
        env['STRANGERTHESIS_DEPLOYMENT_MODE'] = 'hosted-demo'
    def stop_on_signal(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop_on_signal)
    env.update({
        'JIFF_BRIDGE_PORT':str(args.bridge_port),
        'JIFF_RELAY_URL':f'http://127.0.0.1:{args.relay_port}',
        'JIFF_BRIDGE_URL':f'http://127.0.0.1:{args.bridge_port}',
        'JIFF_COORD_TOKEN':secrets.token_hex(32), 'JIFF_BRIDGE_TOKEN':secrets.token_hex(32),
        'JIFF_MANIFEST':str(ROOT/'jiff/fixtures/public-manifest.json'),
        'JIFF_POPULATION':str(ROOT/'jiff/fixtures/population.json'),
    })
    # Verify the integrated JIFF route works without an NSSE file on the Researcher.
    if not args.hosted_demo:
        env['NSSE_DATA_FILE'] = str(ROOT/'data'/'absent-for-jiff-demo.csv')
    if args.self_test:
        for key in ('LLM_BASE_URL','LLM_MODEL','LLM_API_KEY'):
            env.pop(key, None)
    processes = []
    with tempfile.TemporaryDirectory(prefix='strangerthesis-jiff-') as temp:
        # No documents/keys from a self-test are left in the checkout.
        if args.self_test:
            env['STRANGERTHESIS_KEYS_DIR'] = str(Path(temp)/'keys')
        with open(Path(temp)/'services.log','w+') as log:
            commands = [[args.node,'server.js'], [args.node,'bridge.js'], [args.node,'registrar.js']]
            try:
                for command in commands:
                    child_env = dict(env, PORT=str(args.relay_port)) if command[1] == 'server.js' else env
                    processes.append(subprocess.Popen(command,cwd=ROOT/'jiff',env=child_env,stdout=log,stderr=log))
                processes.append(subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host',args.host,'--port',str(args.port)],
                    cwd=ROOT/'backend',env=env,stdout=log,stderr=log))
                url = f'http://127.0.0.1:{args.port}'
                for attempt in range(100):
                    if any(p.poll() is not None for p in processes):
                        raise RuntimeError('A service exited during startup')
                    try:
                        status = request(url+'/status?source=jiff')
                        request(env['JIFF_BRIDGE_URL']+'/manifest',headers={'Authorization':'Bearer '+env['JIFF_BRIDGE_TOKEN']})
                        if not status['setup']['ready']:
                            time.sleep(.2)
                            continue
                        break
                    except (urllib.error.URLError, TimeoutError):
                        time.sleep(.2)
                else:
                    raise RuntimeError('Services did not become ready')
                print('Hosted synthetic JIFF demo:' if args.hosted_demo else 'Integrated synthetic JIFF demo:',url,flush=True)
                print('Select Secure population check · JIFF prototype, then Open sample document.',flush=True)
                if args.self_test:
                    with urllib.request.urlopen(url+'/sample?source=jiff') as response:
                        pdf = response.read()
                    boundary = 'jiff-' + secrets.token_hex(12)
                    data = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="demo.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode()
                            + pdf + f'\r\n--{boundary}--\r\n'.encode())
                    with urllib.request.urlopen(urllib.request.Request(url+'/parse',data=data,
                        headers={'Content-Type':'multipart/form-data; boundary='+boundary})) as response:
                        doc = json.load(response)['doc_id']
                    request(url+f'/scrub/{doc}?source=jiff',{})
                    result = request(url+'/score',{'doc_id':doc,'accepted':[]})
                    assert result['participants'][0]['k'] == 1 and not result['gate_open'], result
                    print('Real PDF → scrub → JIFF: k=1; gate blocked.',flush=True)
                    try:
                        request(url+'/review',{'doc_id':doc})
                        raise AssertionError('High-risk review was accepted')
                    except urllib.error.HTTPError as error:
                        assert error.code == 403
                    result = request(url+'/score',{'doc_id':doc,'accepted':[{'participant_id':'PARTICIPANT_03','field':'affiliation'}]})
                    assert result['participants'][0]['k'] == 5 and result['gate_open'], result
                    result = request(url+'/review',{'doc_id':doc,'format_only':True})
                    assert result['model_review'] == 'not_configured'
                    comparison = request(url+f'/llm-view/{doc}')
                    assert 'Indri' not in comparison['pages'][0]['sent_to_llm']
                    assert 'demo@example.org' not in comparison['pages'][0]['sent_to_llm']
                    print('Accept rewrite → JIFF: k=5; gate open; local review and comparison verified.',flush=True)
                    print('PASS: no model request was configured or sent.',flush=True)
                else:
                    while all(p.poll() is None for p in processes):
                        time.sleep(1)
            except KeyboardInterrupt:
                pass
            except Exception:
                log.flush();log.seek(0)
                print(log.read()[-6000:],file=sys.stderr)
                raise
            finally:
                for process in processes: process.terminate()
                for process in processes:
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired: process.kill();process.wait()


if __name__ == '__main__':
    main()
