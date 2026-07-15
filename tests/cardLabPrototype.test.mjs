import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const appSource = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf-8');
const cardLabSource = readFileSync(new URL('../src/features/card-lab/CardLab.jsx', import.meta.url), 'utf-8');
const stylesSource = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf-8');

test('card lab route is hidden from primary navigation', () => {
  const navBlock = appSource.slice(appSource.indexOf('const navItems = ['), appSource.indexOf('const APP_VERSION'));

  assert.match(appSource, /pathname === '\/card-lab'/);
  assert.doesNotMatch(navBlock, /card-lab/);
});

test('card lab uses isolated static prototype data and class namespace', () => {
  assert.match(appSource, /import\('\.\/features\/card-lab\/CardLab\.jsx'\)/);
  assert.match(cardLabSource, /function CardLab/);
  assert.match(cardLabSource, /const cardLabMovies = \[/);
  assert.match(cardLabSource, /card-lab-card/);
  assert.match(cardLabSource, /card-lab-expanded/);
  assert.match(stylesSource, /Card Lab Prototype/);
  assert.match(stylesSource, /\.card-lab-/);
});
