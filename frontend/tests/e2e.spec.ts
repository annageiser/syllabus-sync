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
            title: 'Lecture 1 - This is a very long title that should wrap to the next line and not be truncated because we are using an AutoResizeTextarea component now.',
            date: '2026-02-20',
            time: '14:30',
            type: 'lecture',
            description: 'This is a very long description that should definitely wrap to the next line and not be truncated. It contains more than 100 characters to ensure that the AutoResizeTextarea component is working correctly and expanding its height to fit the content.',
            module: 'CS101 - Introduction to Computer Science and Programming',
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
