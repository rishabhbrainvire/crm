# integration.py
from .auth import GoogleAuth
from .google_calendar_sync import GoogleCalendarSync
from .google_mail_sync import GmailSync
import frappe

@frappe.whitelist()
def initiate_google_workspace_sync(user):
    try:
        integration = GoogleWorkspaceIntegration(user)
        integration.calendar_sync_setup()
        integration.mail_sync_setup()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Google Calendar Sync Setup Error")
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

@frappe.whitelist()
def inc_google_workspace_mail_sync(user):
    try:
        integration = GoogleWorkspaceIntegration(user)
        integration.inc_mail_sync()
        return {"status": "success", "message": "Incremental mail sync complete"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Google Calendar Sync Setup Error")
        frappe.throw(str(e))


class GoogleWorkspaceIntegration:
    def __init__(self, user):
        self.user = user
        self.auth = GoogleAuth(user)
        self.calendar = GoogleCalendarSync(user, access_token=self.auth.access_token)
        self.gmail = GmailSync(user,access_token=self.auth.access_token)


    def calendar_sync_setup(self):
        self.calendar.sync_events()
        self.calendar.register_watch()

    def mail_sync_setup(self):
        self.gmail.sync_emails()
        # self.gmail.register_watch()

    def inc_cal_sync(self):
        self.calendar.sync_events() 
    
    def inc_mail_sync(self):
        self.gmail.sync_emails()


def calendar_event_handler_enqueue(doc,method):
    process_workspace_item(docname=doc.name,event_doc=True)

def process_workspace_item(docname,mail_doc=None,event_doc=None):
    frappe.flags.in_import = True

    CALENDAR_DOC = "Google Calendar Events"
    GMAIL_DOC = "Gmail Email"
    "Workspace Mail Table"
    "Workspace Event Table"
    IGNORE_DOMAINS = {'gmail.com','yahoo.com', 'hotmail.com', 'outlook.com', 'live.com','icloud.com', 'aol.com', 'protonmail.com', 'zoho.com', 'gmx.com', 'yandex.com'}
    IGNORE_ROLES = {'info', 'support', 'admin', 'contact', 'sales', 'help', 'team','no-reply', 'noreply', 'service', 'office', 'customerservice', 'webmaster'}
    
    print("autocreation started")

    def get_attendees_emails_from_event_doc_instance(docname):
        doc = frappe.get_doc(CALENDAR_DOC, docname)        
        attendees_email = []

        if hasattr(doc, "attendees"):
            for attendee in doc.attendees:
                attendees_email.append(attendee.email)
        
        return attendees_email


    # def get_emails_from_mail_doc_instace():
    #     pass
        
    # if mail_doc:
    #     pass

    def associate_events(event,user):
        pass
        

    def create_user(email):
        # Create User/Contact if not exists
        if not frappe.db.exists('User', email):
            user_doc = frappe.get_doc({
                'doctype':'User',
                'email': email,
                'first_name': email.split('@')[0],
                'send_welcome_email': 0  # avoid sending emails in background
            }).insert(ignore_permissions=True)
        else:
            print("skipping user creation - user already exists")

    def create_organization(domain):
        # Create Domain/Company if not exists
        domain = email.split("@")[1]    
        domain = domain.split(".")[0]

        if not frappe.db.exists('CRM Organization', domain):
            domain_doc = frappe.get_doc({'doctype':'CRM Organization', 'organization_name': domain}).insert(ignore_permissions=True)
        else:
            print("skipping domain creation - domain already exists")

    def process_email_record(email):
        # 1️⃣ Apply ignore filters
        if not email or '@' not in email:
            return None  # Invalid email
        
        username, domain = email.split('@', 1)
        username = username.lower()
        domain = domain.lower()

        # Ignore based on domain
        if domain in IGNORE_DOMAINS:
            print(f"Ignored domain: {domain}")
            return None

        # Ignore based on role/username
        if username in IGNORE_ROLES:
            print(f"Ignored role: {username}")
            return None
        print(f"shooting for {email}")
        create_user(email)
        create_organization(domain)

    try:
        if event_doc:
            emails = get_attendees_emails_from_event_doc_instance(docname)
            for email in emails:
                process_email_record(email)
    except Exception as errr:
        print(errr)