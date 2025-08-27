import requests
import frappe
from datetime import datetime, timezone
import html

import requests
import frappe
from datetime import datetime
import html

class GmailSync:
    GMAIL_API_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    HISTORY_API_URL = "https://gmail.googleapis.com/gmail/v1/users/me/history"
    WATCH_URL = "https://gmail.googleapis.com/gmail/v1/users/me/watch"

    def __init__(self, user, access_token):
        self.user = user

        # Get or create Gmail Integration Account doc
        doc_list = frappe.get_all("Gmail Integration Account", filters={"user": user}, limit=1)
        if doc_list:
            self.doc = frappe.get_doc("Gmail Integration Account" ,doc_list[0].name)
        else:
            self.doc = frappe.get_doc({
                "doctype": "Gmail Integration Account",
                "user": user,
                "sync_token": None,
                "history_id": None,
                "watch_channel_id": None,
                "watch_resource_id": None,
                "watch_expiration": None,
                "watch_topic": None,
                "label_ids": "INBOX",
                "last_sync": None
            })
            self.doc.insert(ignore_permissions=True)
            frappe.db.commit()

        self.access_token = access_token
        self.headers = {"Authorization": f"Bearer {self.access_token}"}
        self.sync_token = self.doc.sync_token
        self.history_id = self.doc.history_id
        self.label_ids = getattr(self.doc, "label_ids", ["INBOX"])

    # ------------------------------
    # Logging helper
    # ------------------------------
    def _log(self, *args):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] [GmailSync:{self.user}] ", *args)

    # ------------------------------
    # Clean HTML entities
    # ------------------------------
    def clean_html_entities(self, text):
        if not text:
            return text
        return html.unescape(text)

    # ------------------------------
    # Update sync info in doc
    # ------------------------------
    def _update_sync_info(self, sync_token=None, history_id=None):
        updated = False
        if sync_token and sync_token != self.doc.sync_token:
            self.doc.sync_token = sync_token
            updated = True
            print(f"Updated sync_token: {sync_token}")
        if history_id and history_id != self.doc.history_id:
            self.doc.history_id = history_id
            updated = True
            print(f"Updated history_id: {history_id}")

        if updated:
            self.doc.last_sync = datetime.now()
            self.doc.save(ignore_permissions=True)
            frappe.db.commit()
            print("Gmail Integration Account doc saved.")

    # ------------------------------
    # Fetch emails
    # ------------------------------
    def fetch_emails(self, query=None):
        """
        Automatically chooses first-time full sync or incremental via historyId.
        """
        if not self.history_id:
            print("No history_id found, performing first-time full sync")
            return self._full_sync(query)
        else:
            print(f"History_id found ({self.history_id}), performing incremental sync")
            return self._incremental_sync(query)

    def _full_sync(self, query=None):
        params = {"labelIds": self.label_ids}
        if query:
            params["q"] = query

        all_messages = []
        last_response = {}
        while True:
            res = requests.get(self.GMAIL_API_URL, headers=self.headers, params=params)
            data = res.json()
            last_response = data

            if "error" in data:
                print("Gmail API Error:", data["error"])
                frappe.throw(f"Gmail API Error: {data['error']}")

            messages = data.get("messages", [])
            print(f"Fetched {len(messages)} messages this page")
            all_messages.extend(messages)

            if "nextPageToken" in data:
                params["pageToken"] = data["nextPageToken"]
                print("Next page detected, continuing fetch...")
            else:
                break

        # ------------------------------
        # Get historyId from a message
        # ------------------------------
        history_id = None
        if all_messages:
            latest_msg_id = all_messages[0]["id"]  # pick most recent
            url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{latest_msg_id}"
            res = requests.get(url, headers=self.headers, params={"format": "metadata"})
            msg_detail = res.json()
            history_id = msg_detail.get("historyId")
            if history_id:
                self._update_sync_info(history_id=history_id)
                print(f"historyId saved: {history_id}")

        # ------------------------------
        # Get nextSyncToken from history.list
        # ------------------------------
        if history_id:
            url = f"https://gmail.googleapis.com/gmail/v1/users/me/history"
            res = requests.get(url, headers=self.headers, params={"startHistoryId": history_id})
            hist_data = res.json()
            sync_token = hist_data.get("nextSyncToken")
            if sync_token:
                self._update_sync_info(sync_token=sync_token)
                print("nextSyncToken saved for future incremental sync")
            else:
                print("⚠️ No nextSyncToken received, will fallback to historyId")

        print(f"Total messages fetched: {len(all_messages)}")
        return all_messages


    # ------------------------------
    # Incremental sync using historyId
    # ------------------------------
    def _incremental_sync(self, query=None):
        """
        Use Gmail history.list API to fetch changes since last historyId
        """
        params = {"startHistoryId": self.history_id, "labelId": "INBOX", "maxResults": 500}
        all_messages = []

        while True:
            res = requests.get(self.HISTORY_API_URL, headers=self.headers, params=params)
            data = res.json()

            if "error" in data:
                print("Gmail history API error:", data["error"])
                # If historyId expired, do full sync
                if data["error"].get("code") == 404:
                    print("HistoryId expired, falling back to full sync")
                    return self._full_sync(query)
                frappe.throw(f"Gmail history API Error: {data['error']}")

            for history in data.get("history", []):
                for msg in history.get("messages", []):
                    all_messages.append(msg)

            # Pagination (nextPageToken)
            if "nextPageToken" in data:
                params["pageToken"] = data["nextPageToken"]
            else:
                break

        # Update historyId for next incremental sync
        if "historyId" in data:
            self._update_sync_info(history_id=data["historyId"])

        print(f"Incremental messages fetched: {len(all_messages)}")
        return all_messages

    # ------------------------------
    # Fetch message details by ID
    # ------------------------------
    def fetch_message_detail(self, message_id):
        url = f"{self.GMAIL_API_URL}/{message_id}"
        res = requests.get(url, headers=self.headers)
        data = res.json()
        if "error" in data:
            frappe.throw(f"Failed to fetch Gmail message: {data['error']}")
        return data


    def extract_email(self,raw_value: str) -> str:
        """
        Extracts the email address from a string like:
        "New User <new.user@domain.com>" → "new.user@domain.com"
        """
        from email.utils import parseaddr
        if not raw_value:
            return ""
        print(raw_value)
        name, addr = parseaddr(raw_value)
        print(addr.strip().lower())
        return addr.strip().lower()  # normalize


    # ------------------------------
    # Save Gmail message to Doctype
    # ------------------------------
    def save_email_to_doctype(self, message):
        headers = message.get("payload", {}).get("headers", [])
        header_map = {h["name"]: h.get("value") for h in headers}

        # Check if email already exists
        existing = frappe.get_all(
            "Gmail Email",
            filters={
                "user": self.user,
                "google_message_id": message.get("id")
            },
            limit=1
        )
        if existing:
            return frappe.get_doc("Gmail Email", existing[0].name)

        doc = frappe.get_doc({
            "doctype": "Gmail Email",
            "user": self.user,
            "google_message_id": message.get("id"),
            "subject": self.clean_html_entities(header_map.get("Subject")),
            "snippet": self.clean_html_entities(message.get("snippet")),
            "internal_date": datetime.fromtimestamp(
                int(message.get("internalDate", 0)) / 1000
            ).replace(tzinfo=None),
        })

        # Add attendees from headers
        for header_type in ["From", "To", "Cc", "Bcc"]:
            header_value = header_map.get(header_type)
            if header_value:
                # Some headers may contain multiple addresses separated by commas
                emails = [e.strip() for e in header_value.split(",")]
                for email in emails:
                    print(email)
                    doc.append("email_headers", {
                        "email_address": self.extract_email(email),
                        "type": header_type.lower()   # store as 'from', 'to', 'cc', 'bcc'
                    })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        print("exiting the save logic now")
        return doc


    # ------------------------------
    # Register Gmail watch
    # ------------------------------
    def register_watch(self, topic_name, expiration=None):
        print('Attempting to register watch')
        payload = {
            "labelIds": self.label_ids,
            "topicName": topic_name
        }
        if expiration:
            payload["expiration"] = expiration

        res = requests.post(self.WATCH_URL, headers=self.headers, json=payload)
        data = res.json()
        print(data.status,data)
        if "error" in data:
            frappe.throw(f"Gmail Watch registration failed: {data['error']}")

        # Save watch details
        self.doc.watch_channel_id = data.get("channelId")
        self.doc.watch_resource_id = data.get("resourceId")
        self.doc.watch_expiration = datetime.fromtimestamp(data.get("expiration", 0)/1000) if data.get("expiration") else None
        self.doc.watch_topic = topic_name
        self.doc.save(ignore_permissions=True)
        frappe.db.commit()
        print("Watch registered and saved.")
        return data



    # ------------------------------
    # Full sync method
    # ------------------------------
    def sync_emails(self, query=None):
        print("Starting email sync...")
        messages = self.fetch_emails(query=query)

        if not messages:
            print("No new messages to sync.")
            return 0

        count = 0
        for msg in messages:
            detail = self.fetch_message_detail(msg["id"])
            doc = self.save_email_to_doctype(detail)
            if doc:
                count += 1

        print(f"Email sync completed. Total messages processed: {len(messages)}, saved: {count}")
        return count


