# integration.py
from .auth import GoogleAuth
from .google_calendar_sync import GoogleCalendarSync
# from .mail_sync import GoogleMailSync
# from .processor import DataProcessor
import frappe

@frappe.whitelist()
def run_full_sync(user):
    try:
        integration = GoogleWorkspaceIntegration(user)
        integration.full_sync()
        return {"status": "success", "message": "Full sync completed"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Google Workspace Full Sync Error")
        frappe.throw(str(e))


class GoogleWorkspaceIntegration:
    def __init__(self, user):
        self.auth = GoogleAuth(user)
        self.calendar = GoogleCalendarSync(user,access_token=self.auth.access_token)

        # self.mail = GoogleMailSync(user, self.auth)
        # self.processor = DataProcessor(user)

    def full_sync(self):
        self.calendar.full_sync()

        # self.mail.sync()
        # self.processor.process(self.calendar.events, self.mail.emails)
