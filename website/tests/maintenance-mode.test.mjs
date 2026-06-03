import {readFileSync} from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';

const rootTheme = readFileSync(new URL('../src/theme/Root.tsx', import.meta.url), 'utf8');

test('site root renders maintenance mode', () => {
  assert.match(rootTheme, /Nous Hermes is in maintenance mode/);
  assert.match(rootTheme, /noindex,nofollow/);
  assert.match(rootTheme, /children/);
  assert.match(rootTheme, /return <MaintenancePage \/>/);
});
