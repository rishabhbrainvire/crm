import frappe

frappe.flags.in_import = True

CALENDAR_DOC = "GW Calendar Event"
GMAIL_DOC = "GW Gmail Mail"
"Workspace Mail Table"
"Workspace Event Table"
IGNORE_DOMAINS = {'gmail.com','yahoo.com', 'hotmail.com', 'outlook.com', 'live.com','icloud.com', 'aol.com', 'protonmail.com', 'zoho.com', 'gmx.com', 'yandex.com'}
IGNORE_ROLES = {'info', 'support', 'admin', 'contact', 'sales', 'help', 'team','no-reply', 'noreply', 'service', 'office', 'customerservice', 'webmaster'}

def get_attendees_email_addr_from_gw_event(doc):
    if isinstance(doc, str):  # already docname
        doc = frappe.get_doc(CALENDAR_DOC, doc)
    
    attendees_email = []
    if hasattr(doc, "attendees"):
        for attendee in doc.attendees:
            attendees_email.append(attendee.email)

    return attendees_email

def get_attendees_email_addr_from_gw_gmail(docname):
    # get from,to,cc,bcc emails and return them
    pass


def get_or_create_user(email):
    # Create User/Contact if not exists
    if not frappe.db.exists('User', email):
        user = frappe.get_doc({
            'doctype':'User',
            'email': email,
            'first_name': email.split('@')[0],
            'send_welcome_email': 0  # avoid sending emails in background
        }).insert(ignore_permissions=True)
    else:
        user = frappe.get_doc("User", email)
        print(f"Skipping User Creation -- User for {email} already exists")
    
    return user

def get_or_create_organization(domain):
        # Create Domain/Company if not exists
        if not frappe.db.exists('CRM Organization', domain):
            organization = frappe.get_doc({'doctype':'CRM Organization', 'organization_name': domain}).insert(ignore_permissions=True)
        else:
            organization = frappe.get_doc('CRM Organization', domain)
            print(f"skipping domain creation -- {domain} already exists")
        
        return organization

def create_workspace_item(user_email):
    # Ignore Invalid email
    if not user_email or '@' not in user_email:
        return None 
    
    username, domain = user_email.split('@', 1)
    username = username.lower()

    domain = domain.split(".")[0]
    domain = domain.lower()

    # Ignore based on domain
    if domain in IGNORE_DOMAINS:
        return None

    # Ignore based on role/username
    if username in IGNORE_ROLES:
        return None

    get_or_create_user(user_email)
    get_or_create_organization(domain)

def associate_workspace_item(email_addr,mail_doc=None,event_doc=None):
    if mail_doc:
        pass

    if event_doc:
        user = frappe.db.get_value("User", {"email": email_addr}, "name")
        event = frappe.get_doc("Event",{"name": event_doc})
        summary = event.summary

        if user:
            user = frappe.get_doc("User", user)
        else:
            user = None

        # Avoid duplicate link
        already_linked = any(row.event == event for row in user.events_table)

        if not already_linked:
            user.append("events_table", {
                "event": event,
                "summary":summary
            })
            user.save(ignore_permissions=True)

        frappe.db.commit()

def process_workspace_item(workspace_item_docname,mail_doc=None,event_doc=None):
    try:
        if event_doc:
            email_addr_list = get_attendees_email_addr_from_gw_event(workspace_item_docname)
                
        if mail_doc:
            email_addr_list = get_attendees_email_addr_from_gw_gmail(workspace_item_docname)
        
        for email_addr in email_addr_list:
            create_workspace_item(email_addr)
        
        for email_addr in email_addr_list:
            associate_workspace_item(email_addr,mail_doc,event_doc=workspace_item_docname.name)
    except Exception as error:
        frappe.throw(error)