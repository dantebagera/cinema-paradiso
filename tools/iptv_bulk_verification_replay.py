"""Read-only replay of saved GPT identity evidence; never imports app or writes a catalogue."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.iptv_metadata_settings import IPTVMetadataSettings
from services.iptv_movie_service import IPTVMovieService
from services.iptv_tmdb import (IPTVTMDBClient, IPTVTMDBError, bounded_search_candidates,
                                choose_automatic_match, interpreted_title_evidence)


class ReplayClient:
    def __init__(self, data, output):
        self.client = IPTVTMDBClient(IPTVMetadataSettings(data))
        self.cache = output / 'tmdb-cache'
        self.cache.mkdir(parents=True, exist_ok=True)
        self.locks = {}
        self.guard = threading.Lock()
        self.requests = 0

    def call(self, method, *args):
        key = hashlib.sha256(json.dumps([method, args]).encode()).hexdigest()
        path = self.cache / (key + '.json')
        with self.guard:
            lock = self.locks.setdefault(key, threading.Lock())
        with lock:
            if path.exists():
                return json.loads(path.read_text(encoding='utf-8'))
            result = getattr(self.client, method)(*args)
            path.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
            with self.guard:
                self.requests += 1
            return result

    def movie(self, identity, language=''):
        return self.call('movie', identity, language)

    def search_movies(self, title, year=0, page=1):
        return self.call('search_movies', title, year, page)

    def collection(self, identity):
        return self.call('collection', identity)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True, type=Path)
    parser.add_argument('--provider', required=True)
    parser.add_argument('--job', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    verifier_hash = hashlib.sha256((Path(__file__).resolve().parents[1] /
                                   'services/iptv_tmdb.py').read_bytes()).hexdigest()
    data, output = args.data.resolve(), args.output.resolve()
    if output == data or output.is_relative_to(data):
        parser.error('Replay output must be outside production data.')
    output.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect((data / 'ai/ai.sqlite').as_uri() + '?mode=ro', uri=True) as db:
        results = [json.loads(row[0]) for row in db.execute(
            'SELECT payload FROM result_items WHERE job_id=? ORDER BY position', (args.job,))]
    results = [row for row in results if row.get('outcome') == 'review' and row.get('evidence', {}).get('identity')]
    with sqlite3.connect((data / 'iptv/providers' / args.provider / 'movies.sqlite').as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        sources = {row['source_key']: dict(db.execute('SELECT * FROM movie_sources WHERE source_key=?',
                                                     (row['source_key'],)).fetchone()) for row in results}
    client = ReplayClient(data, output)
    def replay(row):
        identity = row['evidence']['identity']
        aliases = identity['interpreted_aliases']
        interpretation = {'title': aliases[0] if aliases else '', 'aliases': aliases[1:],
                          'year': identity['interpreted_year']}
        parsed = interpreted_title_evidence(IPTVMovieService._source_title_evidence(sources[row['source_key']]), interpretation)
        # Preserve the actual evidence used during this job, even if provider
        # details have subsequently changed. No new model answer is invented.
        parsed['bulk_identity'] = identity
        parsed['aliases'] = list(dict.fromkeys(aliases + identity['provider_aliases']))
        parsed['year'] = identity['interpreted_year'] or identity['provider_year']
        result = {'source_key': row['source_key'], 'title': row['provider_title'],
                  'old_reason': row['review_reason'], 'identity': identity}
        try:
            search_aliases = list(dict.fromkeys(parsed['aliases'] + row['evidence'].get('search_hints', [])))
            candidates, attempts = bounded_search_candidates(client, parsed, search_aliases=search_aliases)
            decision = choose_automatic_match(parsed, parsed['year'], candidates)
            result.update(state=decision['state'], reason=decision.get('reason', ''), attempts=attempts,
                          accepted_id=(decision['accepted'] or {}).get('id'),
                          candidates=[{key: candidate.get(key) for key in
                              ('id', 'title', 'original_title', 'release_date', 'match_score',
                               'collection_first_movie_id', 'runtime', 'original_language', 'overview',
                               'identity_conflict', 'rival_score')}
                              for candidate in decision['candidates']])
        except IPTVTMDBError as error:
            result.update(state='verification-error', reason=str(error), status=error.status)
        return result
    started = time.monotonic()
    counts = Counter()
    with (output / 'results.jsonl').open('w', encoding='utf-8') as stream, ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(replay, row) for row in results]
        for index, future in enumerate(as_completed(futures), 1):
            result = future.result()
            counts[result['state']] += 1
            stream.write(json.dumps(result, ensure_ascii=False) + '\n')
            stream.flush()
            if index % 25 == 0 or index == len(results):
                print(json.dumps({'done': index, 'total': len(results), 'counts': counts,
                                  'requests': client.requests, 'seconds': round(time.monotonic()-started)}), flush=True)
    summary = {'job': args.job, 'provider': args.provider, 'total': len(results), 'counts': counts,
               'requests': client.requests, 'seconds': round(time.monotonic()-started),
               'gpt_requests': 0, 'catalogue_writes': 0, 'verifier_sha256': verifier_hash}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
