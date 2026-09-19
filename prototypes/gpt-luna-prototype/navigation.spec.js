const { test, expect } = require('@playwright/test');

const baseUrl = 'http://127.0.0.1:4173';
const destinations = [
  ['Overview', 'world'],
  ['Personaggi', 'characters'],
  ['Luoghi', 'places'],
  ['Sessioni', 'sessions'],
  ['Storie', 'stories'],
  ['Il mondo di gioco', 'lore'],
  ['Regole e riferimenti', 'rules']
];

test('all sidebar destinations open the correct view', async ({ page }) => {
  const errors = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  await page.goto(baseUrl);
  for (const [label, view] of destinations) {
    await page.getByRole('button', { name: new RegExp(label) }).first().click();
    await expect(page.locator(`#${view}-view`)).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`#${view}$`));
  }
  expect(errors).toEqual([]);
});

test('overview cards and browser history navigate correctly', async ({ page }) => {
  await page.goto(`${baseUrl}/#world`);
  for (const view of ['characters', 'places', 'sessions', 'stories']) {
    await page.locator(`.quick-card[data-view="${view}"]`).click();
    await expect(page.locator(`#${view}-view`)).toBeVisible();
    await page.goBack();
    await expect(page.locator('#world-view')).toBeVisible();
  }
});

test('search palette and mobile drawer work', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${baseUrl}/#world`);
  await page.getByRole('button', { name: 'Apri menu' }).click();
  await expect(page.locator('#sidebar')).toHaveClass(/open/);
  await page.locator('#sidebar-search').click();
  await expect(page.locator('#palette')).toBeVisible();
  await expect(page.locator('#sidebar')).not.toHaveClass(/open/);
  await page.keyboard.press('Escape');
  await expect(page.locator('#palette')).toBeHidden();
});
