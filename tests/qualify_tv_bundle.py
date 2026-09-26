"""Verify the built bundle through CP routes without launching the application."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


def main():
    source = Path('dist').resolve()
    root = Path(tempfile.mkdtemp(prefix='cp-tv-served-bundle-'))
    target = root/'dist'
    shutil.copytree(source, target)
    os.environ.update(CP_TEST_MODE='1', CP_TEST_ROOT=str(root), CP_TEST_DIST_DIR=str(target))
    import app
    client = app.app.test_client()
    routes = []
    for route in ('/library', '/discover', '/tv/series/1'):
        with client.get(route) as response:
            assert response.status_code == 200, (route,response.status_code)
            assert response.data == (source/'index.html').read_bytes(), route
        routes.append(route)
    assets = {}
    for path in sorted((source/'assets').rglob('*')):
        if not path.is_file(): continue
        route = '/'+path.relative_to(source).as_posix()
        with client.get(route) as response:
            assert response.status_code == 200 and response.data == path.read_bytes(), route
        assets[route] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = {'verification':'Production route owner via Flask test client; no normal server started',
        'routes_matching_built_index':routes, 'asset_count':len(assets), 'sha256':assets,
        'index_sha256':hashlib.sha256((source/'index.html').read_bytes()).hexdigest()}
    Path('docs/verification/tv-parity/build-evidence.json').write_text(json.dumps(report,indent=2))
    print(f'Verified {len(routes)} page routes and {len(assets)} compiled assets byte for byte.')


if __name__ == '__main__':
    main()
