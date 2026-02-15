import { test, expect } from '@playwright/test';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const APP_URL = process.env.APP_URL || 'http://localhost:3000';

test('upload, edit, export ICS', async ({ page }) => {
  // Stub backend upload and generate-ics endpoints
  await page.route(`${API_URL}/upload`, async (route) => {
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
      headers: {
        'Content-Type': 'text/calendar',
        'Content-Disposition': 'attachment; filename=syllabus-events.ics',
      },
      body: 'BEGIN:VCALENDAR\nEND:VCALENDAR',
    });
  });

  await page.goto(APP_URL);

  const fileInput = page.locator('#file-upload');
  await fileInput.setInputFiles({
    name: 'sample.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('dummy pdf'),
  });

  await expect(page.getByText('Schedule Draft')).toBeVisible();
  await expect(page.getByText('E2E Stub')).toBeVisible();

  const titleInput = page.locator('#event-title-0');
  await titleInput.fill('Lecture 1 - Edited');

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: /Export to Calendar/i }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain('syllabus-events');
});
