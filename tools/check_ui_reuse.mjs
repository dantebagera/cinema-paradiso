import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { parse } from '@babel/parser';
import traverseModule from '@babel/traverse';
import postcss from 'postcss';

const traverse = traverseModule.default;
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const hash = text => crypto.createHash('sha256').update(text.replace(/\s+/g, ' ').trim()).digest('hex').slice(0, 20);
const ownerFiles = new Set(['src/components/ui/Button.jsx', 'src/components/ui/Badge.jsx',
  'src/components/ui/FormField.jsx', 'src/components/ui/DialogShell.jsx', 'src/components/ui/SectionTabs.jsx',
  'src/components/WorkspaceEmptyState.jsx', 'src/features/search/SearchField.jsx']);
const sharedNames = new Set(['Button', 'StreamButton', 'ActionLink', 'Badge', 'Input', 'Select', 'Textarea', 'FormField',
  'DialogShell', 'DialogHeader', 'DialogActions', 'SectionTabs', 'SectionTab', 'WorkspaceEmptyState', 'SearchField']);
const appearance = /^(?:background(?:-.*)?|color|border(?:-.*)?|box-shadow|font(?:-.*)?|text-shadow)$/;

// Existing specialized controls are bounded by exact signatures AND occurrence counts.
// There is no wildcard exemption for a feature or for newly added files.
export function presentationSites(file, source, sharedClasses = new Set()) {
  const sites = [];
  const add = (kind, signature, line, owner) => sites.push({ key: `${file}|${kind}|${hash(signature)}`, file, kind, line, owner });
  if (file.endsWith('.jsx') && !ownerFiles.has(file)) {
    const ast = parse(source, { sourceType: 'module', plugins: ['jsx'] });
    traverse(ast, { JSXOpeningElement(p) {
      const n = p.node, tag = n.name.name;
      if (tag && /^[A-Z]/.test(tag) && !p.scope.hasBinding(tag)) {
        add('unbound', tag, n.loc.start.line, tag);
      }
      const attrs = source.slice(n.start, n.end);
      if (sharedNames.has(tag)) {
        const style = n.attributes.find(a => a.name?.name === 'style')?.value?.expression;
        if (style?.type === 'ObjectExpression' && style.properties.some(a => appearance.test((a.key?.name || a.key?.value || '').replace(/[A-Z]/g, c => '-' + c.toLowerCase())))) {
          add('inline-appearance', attrs, n.loc.start.line, tag);
        }
      }
      const type = n.attributes.find(a => a.name?.name === 'type')?.value?.value;
      const ordinaryField = ['input', 'select', 'textarea'].includes(tag) && !['checkbox', 'radio', 'range', 'file', 'color', 'hidden'].includes(type);
      const classes = n.attributes.find(a => a.name?.name === 'className');
      const classText = classes ? source.slice(classes.start, classes.end) : '';
      const duplicateShell = /^[a-z]/.test(tag || '') && /(?:['"`\s])(?:btn|mini-action|primary-button|secondary-button|unified-chip|unified-status-chip|status-badge|dialog-field|dialog-header|dialog-actions|small-dialog|empty-state|iptv-empty|discover-tabs|library-search)(?:['"`\s])/.test(classText);
      const nativeDialog = /^[a-z]/.test(tag || '') && (tag === 'dialog' || n.attributes.some(a => a.name?.name === 'role' && ['dialog', 'alertdialog'].includes(a.value?.value)));
      if (tag === 'button' || ordinaryField || duplicateShell || nativeDialog) {
        const fn = p.findParent(x => x.isFunctionDeclaration() || x.isVariableDeclarator());
        const owner = fn?.node.id?.name || 'module';
        add('markup', `${owner}:${attrs}`, n.loc.start.line, owner);
      }
    } });
  }
  if (file.endsWith('.css') && file !== 'src/components/ui/ui.css') {
    postcss.parse(source).walkRules(rule => {
      const styledClass = (rule.selector.match(/\.[\w-]+/g) || []).some(token => sharedClasses.has(token.slice(1)));
      const repaints = rule.nodes.some(n => n.type === 'decl' && appearance.test(n.prop));
      if ((styledClass && repaints) || /\.(?:cp-(?:button|badge|dialog|input|select|section-tab)|btn(?:\b|-)|mini-action(?:\b|-)|unified-(?:chip|status-chip|owned-badge)|dialog-(?:field|header|actions))/.test(rule.selector)) {
        add('css', rule.toString(), rule.source.start.line, rule.selector);
      }
    });
  }
  return sites;
}

export function auditSites(sites, allowances) {
  const used = new Map(), errors = [];
  for (const site of sites) {
    const count = (used.get(site.key) || 0) + 1;
    used.set(site.key, count);
    if (site.kind === 'unbound' || site.kind === 'inline-appearance' || count > (allowances[site.key]?.count || 0)) errors.push(`${site.file}:${site.line}: reuse the shared ${site.kind === 'css' ? 'appearance owner; feature overrides are forbidden' : 'component; missing imports, new native controls and copied shells are forbidden'} (${site.owner}).`);
  }
  return errors;
}

export function currentSites() {
  const sources = [], sharedClasses = new Set();
  function walk(dir) { for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const file = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(file);
    else if (/\.(jsx|css)$/.test(file)) sources.push([path.relative(root, file).replaceAll('\\', '/'), fs.readFileSync(file, 'utf8')]);
  } }
  walk(path.join(root, 'src'));
  for (const [file, source] of sources) if (file.endsWith('.jsx')) {
    traverse(parse(source, { sourceType: 'module', plugins: ['jsx'] }), { JSXOpeningElement(p) {
      if (!sharedNames.has(p.node.name.name)) return;
      const attr = p.node.attributes.find(a => a.name?.name === 'className');
      function collect(n) {
        if (!n || typeof n !== 'object') return;
        if (n.type === 'StringLiteral' || n.type === 'TemplateElement') {
          for (const token of (n.type === 'StringLiteral' ? n.value : n.value.raw).split(/\s+/)) if (/^[\w-]+$/.test(token)) sharedClasses.add(token);
        } else for (const value of Object.values(n)) if (Array.isArray(value)) value.forEach(collect); else if (value && typeof value === 'object') collect(value);
      }
      collect(attr?.value);
    } });
  }
  return sources.flatMap(([file, source]) => presentationSites(file, source, sharedClasses));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const allowances = JSON.parse(fs.readFileSync(path.join(root, 'tools/ui-specialized-owners.json'), 'utf8'));
  const errors = auditSites(currentSites(), allowances);
  if (errors.length) { console.error(errors.join('\n')); process.exitCode = 1; }
  else console.log('UI reuse gate passed: shared families and bounded specialized owners.');
}
