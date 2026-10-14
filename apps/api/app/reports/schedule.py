"""The one recurring job of the monthly report: a draft for the month that just ended."""

REPORT_WORKFLOW_KEY = "reports.generate_monthly"
# `ensure:` marks a schedule that scripts/ensure_client_schedules.py owns and corrects.
REPORT_SCHEDULE_KEY = f"ensure:{REPORT_WORKFLOW_KEY}"
# 8:00 AM on the 1st, in Pacific time.
REPORT_CRON = "0 8 1 * *"
REPORT_TIMEZONE_NAME = "America/Los_Angeles"
