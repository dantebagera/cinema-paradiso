import process from 'node:process';
import { buildLibraryViewModel } from '../src/utils/libraryUtils.js';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const payload = JSON.parse(input || '{}');
const results = {};
for (const testCase of payload.cases || []) {
  const view = buildLibraryViewModel({
    items: testCase.people ? (payload.peopleItems || []) : (payload.items || []),
    pageSize: Number.MAX_SAFE_INTEGER,
    currentPage: 1,
    mode: 'movie',
    lists: payload.lists || [],
    showAdultMovies: true,
    ...(testCase.view || {})
  });
  results[testCase.name] = view.filteredItems.map((item) => item.shadow_path_key);
}
process.stdout.write(JSON.stringify(results));
