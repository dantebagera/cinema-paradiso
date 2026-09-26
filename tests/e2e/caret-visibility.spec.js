import { expect, test } from '@playwright/test';

test('only text-editable controls display a caret', async ({ page }) => {
  await page.goto('/discover');

  const caretColors = await page.evaluate(() => {
    const host = document.createElement('section');
    host.innerHTML = `
      <input id="default-input">
      <input id="text-input" type="text">
      <input id="search-input" type="search">
      <input id="password-input" type="password">
      <input id="number-input" type="number">
      <textarea id="textarea"></textarea>
      <div id="contenteditable" contenteditable="true"></div>
      <div id="textbox-role" role="textbox"></div>
      <label class="selection-checkbox" id="selection-label">
        <input id="checkbox-input" type="checkbox">
        <span id="checkbox-marker"></span>
      </label>
      <input id="radio-input" type="radio">
      <input id="file-input" type="file">
      <select id="select"><option>One</option></select>
      <button id="button" type="button">Button</button>
      <span id="static-text">Static text</span>
    `;
    document.body.append(host);

    const caret = (id) => getComputedStyle(document.getElementById(id)).caretColor;
    const result = {
      editable: [
        caret('default-input'),
        caret('text-input'),
        caret('search-input'),
        caret('password-input'),
        caret('number-input'),
        caret('textarea'),
        caret('contenteditable'),
        caret('textbox-role'),
      ],
      nonEditable: [
        caret('selection-label'),
        caret('checkbox-input'),
        caret('checkbox-marker'),
        caret('radio-input'),
        caret('file-input'),
        caret('select'),
        caret('button'),
        caret('static-text'),
      ],
    };

    host.remove();
    return result;
  });

  expect(caretColors.editable.every((color) => color !== 'rgba(0, 0, 0, 0)')).toBe(true);
  expect(caretColors.nonEditable).toEqual(
    Array(caretColors.nonEditable.length).fill('rgba(0, 0, 0, 0)'),
  );
});
