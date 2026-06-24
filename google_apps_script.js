/**
 * AWS Re/Start Job Tracker — Google Apps Script
 * 
 * HOW TO SET UP:
 * 1. In your Google Sheet, go to Extensions > Apps Script
 * 2. Delete any existing code and paste this entire script
 * 3. Fill in the CONFIG section below with your values
 * 4. Click Save, then run "createButton" once to add the button to your sheet
 * 5. Click the button in your sheet to trigger the scraper!
 *
 * REQUIRED: Push your latest code to GitHub first, then set up GitHub Actions.
 */

// ─── CONFIG ───────────────────────────────────────────────
const CONFIG = {
  // Your GitHub username
  GITHUB_USER: "akhryss22",

  // Your GitHub repository name (the one you pushed the code to)
  GITHUB_REPO: "job_automation",

  // The workflow file name inside .github/workflows/
  WORKFLOW_FILE: "job_monitor.yaml",

  // Your GitHub Personal Access Token (PAT)
  // How to get one:
  //   1. Go to https://github.com/settings/tokens
  //   2. Click "Generate new token (classic)"
  //   3. Give it a name, select "repo" and "workflow" scopes
  //   4. Copy the token and paste it below
  GITHUB_TOKEN: "PASTE_YOUR_GITHUB_PAT_HERE",
};
// ──────────────────────────────────────────────────────────

/**
 * Creates a floating button on Sheet1 that triggers the scraper.
 * Run this function once from the Apps Script editor to set it up.
 */
function createButton() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheets()[0];

  // Remove any existing button first
  const drawings = sheet.getDrawings();
  drawings.forEach(d => d.remove());

  // Create a drawing as a button
  const button = sheet.newChart()
    .setChartType(Charts.ChartType.BAR)
    .build();

  // Use a text button via Over The Grid image
  const drawing = sheet.insertImage(
    Utilities.newBlob(createButtonPng(), 'image/png', 'button.png'),
    1, 1
  );
  drawing.setWidth(200);
  drawing.setHeight(50);
  drawing.assignScript("runScraper");

  SpreadsheetApp.getUi().alert(
    "✅ Button created! Look for the '🔍 Run Job Scraper' button at the top of your sheet.\n\n" +
    "IMPORTANT: Before clicking the button, make sure you have:\n" +
    "1. Pushed your code to GitHub\n" +
    "2. Added GEMINI_API_KEY, SPREADSHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON as GitHub Secrets\n" +
    "3. Added your GitHub PAT in the CONFIG section of this script"
  );
}

/**
 * Creates a simple PNG image for the button using HTML service.
 * Returns raw bytes.
 */
function createButtonPng() {
  // Simple approach: use a URL fetch to create a colored button image
  // We'll use a Google Charts API to create a button image
  const url = "https://chart.googleapis.com/chart?chst=d_bubble_text_small&chld=bb|🔍 Run Job Scraper|0066FF|FFFFFF";
  const response = UrlFetchApp.fetch(url);
  return response.getContent();
}

/**
 * Main function called when button is clicked.
 * Triggers the GitHub Actions workflow to run the scraper remotely.
 */
function runScraper() {
  const ui = SpreadsheetApp.getUi();
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];

  // Validate config
  if (CONFIG.GITHUB_TOKEN === "PASTE_YOUR_GITHUB_PAT_HERE") {
    ui.alert(
      "⚠️ Setup Required",
      "Please open Extensions > Apps Script and paste your GitHub Personal Access Token in the CONFIG section (GITHUB_TOKEN field).",
      ui.ButtonSet.OK
    );
    return;
  }

  // Show confirmation dialog
  const response = ui.alert(
    "🔍 Run Job Scraper",
    "This will trigger the job scraper on GitHub Actions. It will scrape all companies in your list and update the 'Chosen Roles' column.\n\nThis usually takes 1-3 minutes. Continue?",
    ui.ButtonSet.YES_NO
  );

  if (response !== ui.Button.YES) return;

  // Show progress
  sheet.getRange("C1").setValue("⏳ Scraper running... (check back in 2 minutes)");
  SpreadsheetApp.flush();

  // Trigger GitHub Actions workflow_dispatch
  const apiUrl = `https://api.github.com/repos/${CONFIG.GITHUB_USER}/${CONFIG.GITHUB_REPO}/actions/workflows/${CONFIG.WORKFLOW_FILE}/dispatches`;

  const options = {
    method: "POST",
    headers: {
      Authorization: `Bearer ${CONFIG.GITHUB_TOKEN}`,
      Accept: "application/vnd.github.v3+json",
      "Content-Type": "application/json",
      "X-GitHub-Api-Version": "2022-11-28"
    },
    payload: JSON.stringify({ ref: "master" }),
    muteHttpExceptions: true
  };

  try {
    const apiResponse = UrlFetchApp.fetch(apiUrl, options);
    const code = apiResponse.getResponseCode();

    if (code === 204) {
      // 204 = No Content = success
      sheet.getRange("C1").setValue("✅ Scraper triggered! Results will appear in 1-3 minutes. Refresh the sheet to see updates.");
      SpreadsheetApp.flush();
      ui.alert(
        "✅ Scraper Started!",
        "The job scraper has been triggered on GitHub Actions.\n\n" +
        "It will take about 1-3 minutes to complete. After that, refresh this Google Sheet to see the updated job listings in Column C.",
        ui.ButtonSet.OK
      );
    } else if (code === 401 || code === 403) {
      sheet.getRange("C1").setValue("❌ Auth error — check your GitHub PAT token");
      ui.alert(
        "❌ Authentication Error",
        `GitHub returned code ${code}. Please check:\n` +
        "1. Your GITHUB_TOKEN is correct in the Apps Script CONFIG\n" +
        "2. The token has 'repo' and 'workflow' scopes\n" +
        "3. The token hasn't expired",
        ui.ButtonSet.OK
      );
    } else if (code === 422) {
      sheet.getRange("C1").setValue("❌ Workflow not found — check your workflow file name");
      ui.alert(
        "❌ Workflow Error",
        `GitHub returned code ${code} (Unprocessable Entity).\n\n` +
        "Please check:\n" +
        "1. The workflow file name in CONFIG.WORKFLOW_FILE matches exactly\n" +
        "2. The workflow has 'workflow_dispatch' trigger enabled\n" +
        "3. The repository name in CONFIG.GITHUB_REPO is correct",
        ui.ButtonSet.OK
      );
    } else {
      const body = apiResponse.getContentText();
      sheet.getRange("C1").setValue(`❌ Error code ${code} — check Apps Script logs`);
      ui.alert(
        `❌ Unexpected Error (Code ${code})`,
        `GitHub API response: ${body.substring(0, 300)}`,
        ui.ButtonSet.OK
      );
    }
  } catch (e) {
    sheet.getRange("C1").setValue("❌ Network error — check your internet connection");
    ui.alert("❌ Network Error", `Failed to contact GitHub: ${e.message}`, ui.ButtonSet.OK);
  }
}

/**
 * Adds a custom menu to the spreadsheet for easy access.
 * This runs automatically when the spreadsheet opens.
 */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("🔍 Job Tracker")
    .addItem("Run Job Scraper Now", "runScraper")
    .addItem("Setup Button on Sheet", "createButton")
    .addSeparator()
    .addItem("ℹ️ About", "showAbout")
    .addToUi();
}

function showAbout() {
  SpreadsheetApp.getUi().alert(
    "About AWS Re/Start Job Tracker",
    "This tool automatically scrapes job openings from the companies in your list\n" +
    "and filters them for AWS Re/Start graduates using Gemini AI.\n\n" +
    "Results are written to the 'Chosen Roles' column (Column C).\n\n" +
    "Criteria:\n" +
    "• AWS/Cloud-focused roles\n" +
    "• Junior to mid-level (max 2 years experience)\n" +
    "• Posted within the last 5 days\n" +
    "• No strict degree requirements",
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}
