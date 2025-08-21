# integration.py
from .auth import GoogleAuth
from .google_calendar_sync import GoogleCalendarSync
# from .mail_sync import GoogleMailSync
# from .processor import DataProcessor
import frappe

@frappe.whitelist()
def initiate_google_workspace_sync(user):
    try:
        integration = GoogleWorkspaceIntegration(user)
        integration.initial_setup()
        return {"status": "success", "message": "Google sync enabled"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Google Calendar Sync Setup Error")
        frappe.throw(str(e))


class GoogleWorkspaceIntegration:
    def __init__(self, user):
        self.user = user
        self.auth = GoogleAuth(user)
        self.calendar = GoogleCalendarSync(user, access_token=self.auth.access_token)

    def initial_setup(self):
        # Step 1: Full sync
        self.calendar.full_sync()

        # Step 2: Register watch channel
        self.calendar.register_watch()