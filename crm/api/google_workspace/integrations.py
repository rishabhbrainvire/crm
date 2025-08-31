# integration.py
from .auth import GoogleAuth
from .google_calendar_sync import GoogleCalendarSync
from .google_mail_sync import GmailSync
import frappe

@frappe.whitelist()
def initiate_google_workspace_sync(user):
    try:
        integration = GoogleWorkspaceIntegration(user)
        integration.initial_setup()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Google Workspace Sync Setup Error")
        frappe.throw(str(e))

@frappe.whitelist()
def inc_google_workspace_cal_sync(user):
    try:
        integration = GoogleWorkspaceIntegration(user)
        integration.inc_cal_sync()
        return {"status": "success", "message": "Incremental sync complete"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Google Calendar Sync Setup Error")
        frappe.throw(str(e))

class GoogleWorkspaceIntegration:
    def __init__(self, user):
        self.user = user
        self.auth = GoogleAuth(user)
        self.calendar = GoogleCalendarSync(user, access_token=self.auth.access_token)
        self.gmail = GmailSync(user,access_token=self.auth.access_token)

    def initial_setup(self):
        self.calendar_sync_setup()
        self.gmail.sync_emails()

    def calendar_sync_setup(self):
        self.calendar.sync_events()
        self.calendar.register_watch()

    def inc_cal_sync(self):
        self.calendar.sync_events()