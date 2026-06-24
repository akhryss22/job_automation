// ─── CONFIG ───────────────────────────────────────────────
const CONFIG = {
  GITHUB_USER: "akhryss22",
  GITHUB_REPO: "job_automation",
  WORKFLOW_FILE: "job_monitor.yaml",
  GITHUB_TOKEN: "PASTE_YOUR_GITHUB_PAT_HERE",  // Replace this in Apps Script only — never commit real tokens
};
// ──────────────────────────────────────────────────────────

function runScraper() {
  const ui = SpreadsheetApp.getUi();
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];

  const response = ui.alert(
    "Run Job Scraper",
    "This will trigger the job scraper on GitHub Actions and update the sheet in 1-3 minutes. Continue?",
    ui.ButtonSet.YES_NO
  );

  if (response !== ui.Button.YES) return;

  sheet.getRange("C1").setValue("Running scraper... check back in 2 minutes.");
  SpreadsheetApp.flush();

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
      sheet.getRange("C1").setValue("Scraper triggered. Refresh this sheet in 1-3 minutes to see results.");
      ui.alert("Done", "Job scraper is running on GitHub Actions. Refresh the sheet in a few minutes.", ui.ButtonSet.OK);
    } else {
      const body = apiResponse.getContentText();
      sheet.getRange("C1").setValue("Error code " + code + " — see details below.");
      ui.alert("Error (Code " + code + ")", "GitHub API response: " + body.substring(0, 300), ui.ButtonSet.OK);
    }
  } catch (e) {
    sheet.getRange("C1").setValue("Network error.");
    ui.alert("Network Error", e.message, ui.ButtonSet.OK);
  }
}

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("Job Tracker")
    .addItem("Run Job Scraper Now", "runScraper")
    .addToUi();
}
