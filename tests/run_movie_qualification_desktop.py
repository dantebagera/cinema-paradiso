"""One owned fixture and one desktop worker, inside the cumulative job budget."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request


def main():
    root = Path(os.environ['CP_TEST_ROOT']).resolve()
    existing = sorted(root.glob('remaining-*/bounded-4000-reads.json'), key=lambda p: p.stat().st_mtime)
    if not existing:
        raise RuntimeError('Already-seeded 4000-film read-bound fixture required')
    prior = json.loads(existing[-1].read_text())
    fixture_root = Path(prior.get('fixture_root', str(existing[-1].parent / 'bounded')))
    port = 5141
    environment = {**os.environ, 'CP_PORT': str(port), 'CP_E2E_PORT': str(port),
        'CP_TEST_DIST_DIR': str(root / 'dist-corrective'),
        'PLAYWRIGHT_JSON_OUTPUT_FILE': str(root / 'qualification-desktop-results.json')}
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', port))
    actual_pid = None
    with (root / 'qualification-desktop-server.log').open('wb') as output:
        process = subprocess.Popen([sys.executable, '-m', 'tests.movie_qualification_backend', 'server', str(fixture_root)],
            env=environment, stdout=output, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline and process.poll() is None:
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/test/qualification/status', timeout=1) as response:
                        status = json.load(response)
                    actual_pid = status['pid']
                    break
                except OSError:
                    time.sleep(.1)
            if actual_pid is None:
                raise RuntimeError('Owned server did not become ready: ' + (root / 'qualification-desktop-server.log').read_text(errors='replace')[-3000:])
            result = subprocess.run(['node', 'node_modules/@playwright/test/cli.js', 'test',
                'tests/e2e/movie-remaining-qualification.spec.js', '--workers=1', '--max-failures=1',
                '--output', str(root / 'qualification-desktop-artifacts'), '--reporter=json'],
                env=environment, timeout=145)
            if (root / 'qualification-desktop-results.json').exists():
                report = json.loads((root / 'qualification-desktop-results.json').read_text())
                print(json.dumps(report.get('stats', {})), flush=True)
            return result.returncode
        finally:
            if actual_pid is not None:
                try: os.kill(actual_pid, signal.SIGTERM)
                except OSError: pass
            if process.poll() is None:
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == '__main__':
    sys.exit(main())
