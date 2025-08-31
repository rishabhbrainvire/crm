import frappe
import requests
import datetime
import urllib.parse
from frappe.utils import random_string, now_datetime
from datetime import timedelta, datetime

@frappe.whitelist()
def check_google_auth_connection(user):
    conn = frappe.db.get_value(
        "Google Integration Account",
        {"user": user},
        ["access_token", "refresh_token"],
        as_dict=True
    )
    if conn and conn.access_token and conn.refresh_token:
        return {
            "connected": True,
            # "email": conn.google_account
        }
    return {"connected": False}

# 

@frappe.whitelist()
def initiate_google_auth(user=None):
    if not user:
        user = frappe.session.user

    return GoogleAuth.initiate_google_auth(user=user)

@frappe.whitelist()
def google_oauth_callback(**kwargs):
    GoogleAuth.google_oauth_callback(**kwargs)
    return 


class GoogleAuth:
    """Handles Google OAuth tokens and credentials for a given user."""
    DOMAIN_URL = "https://frappecrm.brainvire.net"
    TOKEN_DOCTYPE = "Google Integration Account"
    GOOGLE_CLIENT_ID = frappe.conf.get("google_client_id")
    GOOGLE_CLIENT_SECRET = frappe.conf.get("google_client_secret")
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    REDIRECT_URI = f"{DOMAIN_URL}/api/method/crm.api.google_workspace.auth.google_oauth_callback"
    SCOPES = "https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/gmail.readonly"

    def __init__(self, user):
        self.user = user

        if not self.GOOGLE_CLIENT_ID or not self.GOOGLE_CLIENT_SECRET:
            frappe.throw("Google Client ID and Client Secret not found")

        # Load user-specific tokens
        token_name = frappe.db.get_value(self.TOKEN_DOCTYPE, {"user": user})
        if not token_name:
            frappe.throw(f"Please Authorize Google Oauth")

        token_doc = frappe.get_doc(self.TOKEN_DOCTYPE, token_name)
        self._access_token = token_doc.access_token
        self.refresh_token = token_doc.refresh_token
        self.expiry = token_doc.token_expiry
    
    @property
    def access_token(self):
        self.refresh_if_needed()
        return self._access_token

    # -------------------------------------------------------------------
    # Token refresh handling
    # -------------------------------------------------------------------
    def refresh_if_needed(self):
        """
        Refresh the access token if it is expired or near expiry.
        Updates the token doc in the database.
        """
        try:
            BUFFER_TIME = 600 # Buffer time set to 10mins

            # Check if refresh is needed
            refresh_needed = (self.expiry - now_datetime()).total_seconds() < BUFFER_TIME 
            
            if not refresh_needed:
                return 
            
            # Refresh if its exceeding buffer time
            payload = {
                "client_id": self.GOOGLE_CLIENT_ID,
                "client_secret": self.GOOGLE_CLIENT_SECRET,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            }

            response = requests.post(self.GOOGLE_TOKEN_URL, data=payload)

            if not response.ok:
                frappe.log_error(response.text, "Google Calendar Token Refresh Failed")
                frappe.throw("Google Calendar Token Refresh Failed")
                return False

            response = response.json()

            # Save back to Frappe
            token_doc = frappe.get_doc(self.TOKEN_DOCTYPE, {"user": self.user})
            token_doc.access_token = response["access_token"]
            token_doc.token_expiry = datetime.now() + timedelta(seconds=response["expires_in"])
            token_doc.save(ignore_permissions=True)
            frappe.db.commit()
            print("Google Calendar Token Refresh Sucess")
            
            return 
        
        except Exception as error:
            frappe.throw("Token Refreshing Failed",error)
   

    # -------------------------------------------------------------------
    # Static methods for Intiating Google OAuth Process & Verification
    # -------------------------------------------------------------------

    @staticmethod
    def save_tokens(token):
        """
        Save tokens to the DB (usually after initial OAuth flow).
        Expects token to have the following (user, access_token, refresh_token, expiry, scopes, calendar_sync_token)
        """

        token_doc = frappe.get_doc({
            "doctype": GoogleAuth.TOKEN_DOCTYPE,
            "user":token["user"],
            "access_token":token["access_token"],
            "refresh_token":token["refresh_token"],
            "token_expiry":token["expiry"],
            "scopes":token["scopes"],
            "calendar_sync_token":token["calendar_sync_token"]
        })
        token_doc.insert(ignore_permissions=True)
        frappe.db.commit()
    
    # ---------- Inital OAuth Setup Methods --------------- # 
    
    @staticmethod
    def initiate_google_auth(user):

        state = random_string(16)
        frappe.cache().set_value(f"oauth_state:{state}", user)

        params = {
            "client_id": GoogleAuth.GOOGLE_CLIENT_ID,
            "redirect_uri": GoogleAuth.REDIRECT_URI,
            "response_type": "code",
            "scope": GoogleAuth.SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state":state
        }
        
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
        return auth_url

    @staticmethod
    def google_oauth_callback(**kwargs):
        code = frappe.form_dict.get("code")
        state = frappe.form_dict.get("state")

        if not code or not state:
            frappe.throw(f"Missing code or state. Got: {frappe.form_dict}")

        # Exchange code for tokens
        data = {
            "code": code,
            "client_id": GoogleAuth.GOOGLE_CLIENT_ID,
            "client_secret": GoogleAuth.GOOGLE_CLIENT_SECRET,
            "redirect_uri": GoogleAuth.REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        res = requests.post(GoogleAuth.GOOGLE_TOKEN_URL, data=data)
        token_info = res.json()
        if "error" in token_info:
            frappe.throw(f"OAuth Error: {token_info}")
        
        # return GoogleAuth.save_tokens() instead #TBD 
        # Store tokens in Google Workspace Connection
        existing = frappe.get_all("Google Integration Account", filters={"user": frappe.session.user}, limit=1)
        if existing:
            conn_doc = frappe.get_doc("Google Integration Account", existing[0].name)
            conn_doc.update({
                "access_token": token_info["access_token"],
                "refresh_token": token_info["refresh_token"],
                "token_expiry": datetime.now() + timedelta(seconds=token_info["expires_in"]),
                "last_synced": datetime.now(),
                "scopes":token_info["scope"], # need to append on a unqiue level 
                "token_type": token_info["token_type"]
            })
            conn_doc.save(ignore_permissions=True)
        else:
            connection = frappe.get_doc({
                "doctype": "Google Integration Account",
                "user": frappe.session.user,
                "access_token": token_info["access_token"],
                "refresh_token": token_info["refresh_token"],
                "token_expiry": datetime.now() + timedelta(seconds=token_info["expires_in"]),
                "last_synced": datetime.now(),
                "scopes":token_info["scope"],
                "token_type": token_info["token_type"]
            })
            connection.insert(ignore_permissions=True)


        # Update status in User
        frappe.db.commit()

        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/app/user/" + frappe.session.user  # Go back to user form
        return 









