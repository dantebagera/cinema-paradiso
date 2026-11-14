import { test } from 'node:test';
import assert from 'node:assert/strict';
import { presentationSites, auditSites } from '../tools/check_ui_reuse.mjs';

test('new feature must use Button, fields and shared shells', () => {
  const bad = presentationSites('src/features/new/New.jsx', 'function New(){return <div className="empty-state"><button>Save</button><input /><select /></div>}');
  assert.equal(auditSites(bad, {}).length, 4);
  assert.equal(auditSites(presentationSites('src/features/new/New.jsx', "import {WorkspaceEmptyState, Button, Input, Select} from './ui'; function New(){return <WorkspaceEmptyState><Button>Save</Button><Input /><Select /></WorkspaceEmptyState>}"), {}).length, 0);
});
test('existing specialized control does not permit a copy or a new file', () => {
  const source = 'function Rail(){return <button className="rail-arrow" aria-label="Next" />}';
  const sites = presentationSites('src/components/Rail.jsx', source);
  const allowed = { [sites[0].key]: { count: 1 } };
  assert.deepEqual(auditSites(sites, allowed), []);
  assert.equal(auditSites([...sites, ...sites], allowed).length, 1);
  assert.equal(auditSites(presentationSites('src/features/new/Rail.jsx', source), allowed).length, 1);
});
test('feature CSS cannot repaint a shared button', () => {
  assert.equal(auditSites(presentationSites('src/features/new/new.css', '.page .btn { color: purple; }'), {}).length, 1);
  assert.equal(presentationSites('src/components/ui/ui.css', '.btn { color: green; }').length, 0);
  assert.equal(auditSites(presentationSites('src/features/new/new.css', '.new-action { color: purple; }', new Set(['new-action'])), {}).length, 1);
});

test('newly named dialogs cannot bypass the shared shell', () => {
  assert.equal(auditSites(presentationSites('src/features/new/New.jsx', 'function New(){return <section className="new-feature-popup" role="dialog" />}'), {}).length, 1);
});
