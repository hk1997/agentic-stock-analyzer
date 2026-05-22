import { test, expect } from '@playwright/test';

test.describe('Financial Super App E2E Flows', () => {
  const TEST_EMAIL = `e2e_user_${Date.now()}@example.com`;
  const TEST_PASSWORD = 'SecurePassword123!';

  test('Authentication, Dashboard, and Net Worth Flows', async ({ page }) => {
    // 1. Authentication Flow
    await page.goto('http://localhost:5173');

    // App should redirect to /auth
    await expect(page).toHaveURL(/.*\/auth/);

    // Toggle to Register mode
    await page.getByRole('button', { name: 'Need an account? Register' }).click();
    
    // Fill Registration Form
    await page.getByPlaceholder('Name').fill('E2E Tester');
    await page.getByPlaceholder('Email').fill(TEST_EMAIL);
    await page.getByPlaceholder('Password').fill(TEST_PASSWORD);
    await page.getByRole('button', { name: 'Register' }).click();

    // Check if redirected to dashboard
    await expect(page).toHaveURL('http://localhost:5173/');
    await expect(page.getByText('Welcome back, E2E Tester')).toBeVisible();

    // 2. Net Worth Flow
    // Navigate to Net Worth page via sidebar
    await page.getByRole('button', { name: 'Net Worth' }).click();
    await expect(page).toHaveURL(/.*\/net-worth/);

    // Add Manual Asset
    await page.getByLabel('Asset Type').selectOption('cash');
    await page.getByPlaceholder('e.g. Checking Account').fill('Emergency Fund');
    await page.getByPlaceholder('0.00').fill('15000');
    await page.getByRole('button', { name: 'Add Record' }).click();

    // Verify asset appears in list
    await expect(page.getByText('Emergency Fund')).toBeVisible();
    await expect(page.getByText('$15,000.00')).toBeVisible();

    // 3. Expenses Flow
    // Navigate to Expenses page
    await page.getByRole('button', { name: 'Expenses' }).click();
    await expect(page).toHaveURL(/.*\/expenses/);

    // Add an expense
    await page.getByPlaceholder('e.g. Groceries').fill('Groceries');
    await page.getByPlaceholder('0.00').fill('120.50');
    await page.getByRole('button', { name: 'Add Record' }).click();

    // Verify expense appears in ledger
    await expect(page.getByText('Groceries', { exact: true })).toBeVisible();
    await expect(page.getByText('$120.50')).toBeVisible();

    // 4. Portfolio Unified View
    // Navigate to Portfolio page
    await page.getByRole('button', { name: 'Portfolio' }).click();
    await expect(page).toHaveURL(/.*\/portfolio/);

    // Default is personal mode, add a holding
    await page.getByRole('button', { name: 'Add Holding' }).click();
    await page.getByPlaceholder('e.g. AAPL').fill('AAPL');
    await page.locator('input[type="number"]').first().fill('10'); // Shares
    await page.locator('input[type="number"]').nth(1).fill('150'); // Cost basis
    await page.getByRole('button', { name: 'Save' }).click();

    // Verify holding appears
    await expect(page.getByText('AAPL', { exact: true })).toBeVisible();

    // Toggle to Unified View
    await page.getByRole('button', { name: 'Unified' }).click();
    // Verify unified portfolio renders and still contains our holding
    await expect(page.getByText('AAPL', { exact: true })).toBeVisible();
  });
});
