import { test, expect } from '@playwright/test';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const APP_URL = process.env.APP_URL || 'http://localhost:3000';

test('upload, edit, export ICS', async ({ page }) => {
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.message));
  page.on('requestfailed', request => console.log('REQUEST FAILED:', request.url(), request.failure()?.errorText));

  // Stub backend upload and generate-ics endpoints
  await page.route(`${API_URL}/upload`, async (route) => {
    console.log('Intercepted /upload');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        events: [
          {
            title: 'Lecture 1',
            date: '2026-02-20',
            type: 'lecture',
            description: 'Intro',
            module: 'CS101',
          },
        ],
        extraction_source: 'E2E Stub',
      }),
    });
  });

  await page.route(`${API_URL}/generate-ics`, async (route) => {
    await route.fulfill({
      status: 200,
      status: 200,
fill({
URL}/generate-ics`, async (rr',
                                                            s-events.ics',
      },
      body: 'BEGIN:VCALENDAR\nEND:VCALENDAR',      body: 'BEGIN:VCALENDAR\nEND:VCALENDAR',      body: 'BEGIN:VCALE.lo      body: 'BEGIN:VCALENDAR\nEND:VCALENDAR',      body: 'BEGIN:VCALENDAR\nEND:VCALENDAR',      body: 'BEGIN:VCAL
                                                     ex                                aft')).toBeVisible();
  awa  awa  awa  awa  awa  awa  awa  awa  atoBeVisible();

  const titleInput = page.locat  const titleInput = page.locat  connpu  const titleInput = page.l);  const tidownload  const = pa  const titleInput = page.loc  a  const titleInput = page.loca{ name: /Export to Calendar/i }).click();
  const download = await downloadPromise;
  expect(download.sugge  expilenam  expect(download.sugge  expilenam  e;
