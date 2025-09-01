import frappe
from more_itertools import chunked


CALENDAR_DOC = "GW Calendar Event"
GMAIL_DOC = "GW Gmail Mail"
"Workspace Mail Table"
"Workspace Event Table"
IGNORE_DOMAINS = {'gmail.com','yahoo.com', 'microsoft.com','hotmail.com', 'outlook.com', 'live.com','icloud.com', 'aol.com', 'protonmail.com', 'zoho.com', 'gmx.com', 'yandex.com'}
IGNORE_ROLES = {"hrms","hrmssuport","hr","timekeeping","mum",'info', 'support', 'admin', 'contact', 'sales', 'help', 'team','no-reply', 'noreply', 'service', 'office', 'customerservice', 'webmaster'}

def get_attendees_email_addr_from_gw_event(doc):
    if isinstance(doc, str):  # already docname
        doc = frappe.get_doc(CALENDAR_DOC, doc)
    
    attendees_email = []
    if hasattr(doc, "attendees"):
        for attendee in doc.attendees:
            attendees_email.append(attendee.email)

    return attendees_email

def get_attendees_email_addr_from_gw_gmail(docname):
    if isinstance(docname, str):  # already docname
        doc = frappe.get_doc(GMAIL_DOC, docname)

    email_addrs_list = []

    for header in doc.email_headers:
        email_addrs_list.append(header.email_address)
    
    return email_addrs_list

def get_or_create_user(email):
    frappe.flags.in_import = True
    frappe.flags.mute_emails = True

    # Create User/Contact if not exists
    if not frappe.db.exists('User', email):
        user = frappe.get_doc({
            'doctype':'User',
            'email': email,
            'first_name': email.split('@')[0],
            'send_welcome_email': 0  # avoid sending emails in background
        }).insert(ignore_permissions=True)
    else:
        print(f"Skipping User Creation -- User for {email} already exists")
    
    return 

def get_or_create_organization(domain):
    frappe.flags.in_import = True
    frappe.flags.mute_emails = True


    # Create Domain/Company if not exists
    if not frappe.db.exists('CRM Organization', domain):
        organization = frappe.get_doc({'doctype':'CRM Organization', 'organization_name': domain}).insert(ignore_permissions=True)
    else:
        print(f"skipping domain creation -- {domain} already exists")
    
    return 

def provision_users_and_orgs(user_email):
    frappe.flags.in_import = True
    frappe.flags.mute_emails = True

    # Ignore Invalid email
    if not user_email or '@' not in user_email:
        return None 
    
    username, domain = user_email.split('@', 1)
    username = username.lower()

    # Ignore based on domain
    if domain in IGNORE_DOMAINS:
        return None

    # Ignore based on role/username
    if username in IGNORE_ROLES:
        return None
    
    domain = domain.split(".")[0]
    domain = domain.lower()

    # tbd make it create only 
    get_or_create_user(user_email)
    get_or_create_organization(domain)

def provision_GWI_association(docname, email_addr, is_mail=None,is_event=None):
    # TBD to associate it to orgs too

    """
    Associate the docname/GWI to user & orgs based on email
    Currently only doing it for user  
    """

    if is_mail:
        # Get the user
        user_docname = frappe.db.get_value("User", {"email": email_addr}, "name")

        if not user_docname:
            print("User doesn't exist to associate",docname,email_addr)
            return None
        else:
            user = frappe.get_doc("User",user_docname)

        mail = frappe.get_doc(GMAIL_DOC,{"name": docname})
        mail_subject = mail.subject 

        # Avoid duplicate link -- 
        already_linked = any(row.email == mail.name for row in user.workspace_emails)

        if not already_linked:
            user.append("workspace_emails", {
                "email": mail.name,
                "email_subject":mail_subject
            })
            user.save(ignore_permissions=True)

        frappe.db.commit()
        


    if is_event:

        user_docname = frappe.db.get_value("User", {"email": email_addr}, "name")

        if not user_docname:
            print("user didn't exist to associate",docname,email_addr)
            return None
        else:
            user = frappe.get_doc("User",user_docname)

        event = frappe.get_doc(CALENDAR_DOC,{"name": docname})
        summary = event.summary

        # Avoid duplicate link -- 
        already_linked = any(row.event == event.name for row in user.workspace_events)

        if not already_linked:
            user.append("workspace_events", {
                "event": event.name,
                "event_summary":summary
            })
            user.save(ignore_permissions=True)

        frappe.db.commit()


def GWI_provisioning(docnames,is_mail=None,is_event=None):
    if not is_mail and not is_event:
        frappe.throw("GWI provisioning Failed - No GWI type provided ")

    try:
        # Backup the original enqueue method
        original_enqueue = frappe.enqueue

        # Define a no-op function to replace the original enqueue
        def noop(*args, **kwargs):
            return None

        # Temporarily replace the enqueue method
        frappe.enqueue = noop

        for docname in docnames:

            if is_event:
                GWI_emails = get_attendees_email_addr_from_gw_event(docname)

                for email_addr in GWI_emails:
                    provision_users_and_orgs(email_addr) 
            
                for email_addr in GWI_emails:
                    provision_GWI_association(docname,email_addr,is_event=True)
            
            if is_mail:
                GWI_emails = get_attendees_email_addr_from_gw_gmail(docname)

                for email_addr in GWI_emails:
                    provision_users_and_orgs(email_addr) 
            
                for email_addr in GWI_emails:
                    provision_GWI_association(docname,email_addr,is_mail=True)

        # Restore the original enqueue method
        frappe.enqueue = original_enqueue

    except Exception as error:
        frappe.throw(error)

def GWI_provisioning_in_batches(docnames, is_mail=None, is_event=None, batch_size=50):
    """
    Dispatch provisioning in batches so we don't enqueue too many jobs.
    """
    if not is_mail and not is_event:
        frappe.throw("GWI provisioning Failed - No GWI type provided ")

    # Deduplicate docnames in case of overlap
    docnames = list(set(docnames))

    for batch in chunked(docnames, batch_size):

        frappe.enqueue(
            "crm.api.google_workspace.workspace_items.GWI_provisioning",
            docnames=batch,
            is_mail=is_mail,
            is_event=is_event,
            queue="long"
        )

"""
GWI_provisioning process for a GWI instance 
    step 1 - get relevant emails from GWI
    
    step 2 based on GWI Emails do
        1. provision_user
        2. provision_orgs

    step 3 provision_GWI_association ( of base instance with relevant user & orgs) 
"""


# Step 1 - get all GWI instances 
# Step 2 - save all GWI instances
# Step 3 - Process GWI_provisioning for all GWI instances


# Step 3 Detail
# GWI_provisioning process for a GWI instance 
#     provision_user
#     provision_orgs
#     provision_GWI_association ( of base instance with relevant user & orgs) 

