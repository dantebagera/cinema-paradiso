import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { buildSync } from 'esbuild';

const root = path.resolve(import.meta.dirname, '..');
const owners = ['Button', 'Badge', 'FormField', 'DialogShell', 'SectionTabs'];
const missing = owners.filter(name => !fs.existsSync(path.join(root, `src/components/ui/${name}.jsx`)));
let ui;
test('selected UI families have shared production owners', () => assert.deepEqual(missing, []));
if (!missing.length) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cp-shared-ui-'));
  const output = path.join(dir, 'owners.cjs');
  buildSync({ stdin: { contents: `
    export {createElement as h} from 'react';
    export {renderToStaticMarkup as render} from 'react-dom/server';
    export {default as Button, StreamButton} from './src/components/ui/Button.jsx';
    export {default as Badge} from './src/components/ui/Badge.jsx';
    export {default as FormField, Input, Select} from './src/components/ui/FormField.jsx';
    export {default as DialogShell, DialogHeader, DialogActions} from './src/components/ui/DialogShell.jsx';
    export {default as SectionTabs, SectionTab} from './src/components/ui/SectionTabs.jsx';
    export {default as Pagination} from './src/components/Pagination.jsx';
    export {default as SelectionBar} from './src/components/WorkspaceSelectionBar.jsx';
    export {default as EmptyState} from './src/components/WorkspaceEmptyState.jsx';
  `, resolveDir: root, loader: 'jsx' }, outfile: output, bundle: true, platform: 'node', format: 'cjs', jsx: 'automatic', logLevel: 'silent' });
  ui = createRequire(import.meta.url)(output);
  fs.rmSync(dir, { recursive: true, force: true });
}

const check = (name, fn) => test(name, { skip: !ui }, fn);
const html = (component, props, ...children) => ui.render(ui.h(component, props, ...children));
check('button preserves native submit, disabled state, Arabic label and caller accessibility', () => {
  const markup = html(ui.Button, { type: 'submit', disabled: true, variant: 'primary', 'aria-describedby': 'reason', name: 'action', value: 'save' }, 'حفظ الفيلم');
  assert.match(markup, /type="submit"/);
  assert.match(markup, /disabled=""/);
  assert.match(markup, /aria-describedby="reason"/);
  assert.match(markup, /name="action"/);
  assert.match(markup, /value="save"/);
  assert.match(markup, /حفظ الفيلم/);
  assert.doesNotMatch(html(ui.Button, {}, 'Native default'), /type=/);
});
check('Stream has one green presentation and keeps supplied label', () => {
  const markup = html(ui.StreamButton, { type: 'button' }, 'Stream episode');
  assert.match(markup, /btn-green-outline/);
  assert.match(markup, /lucide-monitor-play/);
  assert.match(markup, /Stream episode/);
});
check('button loading is presentation, not an invented disabled policy', () => {
  const markup = html(ui.Button, { loading: true, disabled: false }, 'Saving');
  assert.match(markup, /spin/);
  assert.doesNotMatch(markup, /disabled=/);
});
check('badge preserves meaning and compact size without rewriting labels', () => {
  assert.match(html(ui.Badge, { kind: 'status', tone: 'following' }, 'Following'), /unified-status-following/);
  const markup = html(ui.Badge, { size: 'compact', dir: 'auto' }, 'العربية');
  assert.match(markup, /cp-badge-compact/);
  assert.match(markup, /dir="auto"/);
  assert.match(markup, /العربية/);
});
check('unknown-total pagination never invents totals or NaN ranges', () => {
  const markup = html(ui.Pagination, { page: 2, hasNext: true, onPageChange() {} });
  assert.match(markup, /Page 2/);
  assert.doesNotMatch(markup, /NaN|undefined|of 0/);
});
check('pagination can retain a one-page caller summary without enabled page controls', () => {
  const markup = html(ui.Pagination, { page: 1, totalPages: 1, summary: 'Three results', showSinglePage: true, onPageChange() {} });
  assert.match(markup, /Three results/);
  assert.equal((markup.match(/disabled=""/g) || []).length, 2);
  assert.equal(html(ui.Pagination, { page: 1, totalPages: 1, onPageChange() {} }), '');
});
check('AI zero-selection display can remain visible and disabled without changing default bars', () => {
  const props = { selectedCount: 0, onClear() {}, showZeroCount: true, showActionsWhenEmpty: true, clearDisabled: true };
  const markup = html(ui.SelectionBar, props, ui.h(ui.Button, { disabled: true }, 'Add to list'));
  assert.match(markup, /0 selected/);
  assert.match(markup, /Clear/);
  assert.equal((markup.match(/disabled=""/g) || []).length, 2);
  assert.doesNotMatch(html(ui.SelectionBar, { selectedCount: 0, onClear() {} }), />Clear</);
});
check('empty-state shell preserves alert role and supplied recovery action', () => {
  const markup = html(ui.EmptyState, { size: 'compact', role: 'alert', title: 'Could not load', description: 'Incomplete results' }, ui.h(ui.Button, {}, 'Retry'));
  assert.match(markup, /role="alert"/);
  assert.match(markup, /cp-empty-compact/);
  assert.match(markup, /Incomplete results/);
  assert.match(markup, />Retry</);
});
check('field and dialog shells preserve native form boundaries and labels', () => {
  const markup = html(ui.DialogShell, { as: 'form', role: 'dialog', 'aria-label': 'Edit', method: 'post' }, ui.h(ui.FormField, { htmlFor: 'name', label: 'Name' }, ui.h(ui.Input, { id: 'name', name: 'name', required: true })));
  assert.match(markup, /^<form/);
  assert.match(markup, /method="post"/);
  assert.match(markup, /for="name"/);
  assert.match(markup, /required=""/);
  assert.doesNotMatch(markup, /modal-backdrop|tabindex/);
});
check('tabs preserve caller roles and roving tabIndex without inventing navigation', () => {
  const markup = html(ui.SectionTabs, { role: 'tablist', 'aria-label': 'Media' }, ui.h(ui.SectionTab, { active: true, role: 'tab', 'aria-selected': true, tabIndex: 0 }, 'Movies'));
  assert.match(markup, /role="tablist"/);
  assert.match(markup, /role="tab"/);
  assert.match(markup, /aria-selected="true"/);
  assert.match(markup, /tabindex="0"/);
});
