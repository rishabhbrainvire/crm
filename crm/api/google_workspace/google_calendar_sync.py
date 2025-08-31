import frappe
import requests
import datetime
from datetime import datetime, timedelta
import pytz
import json
import uuid

class GoogleCalendarSync:
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    BASE_URL = "https://www.googleapis.com/calendar/v3/calendars"
    # WEBHOOK_ENDPOINT = "/api/method/crm.google_calendar.webhook"  Update this
    TOKEN_DOCTYPE = "User GW Account"
    CALENDAR_DOCTYPE = "GW Calendar Account" 

    # Centralized status options
    STATUS_NOT_SYNCED = "Not Synced"
    STATUS_SYNCING_CALENDAR = "Syncing Calendar Events"
    STATUS_SYNCING_MAILS = "Syncing Mails"
    STATUS_SYNCING = "Syncing"
    STATUS_FAILED = "Sync Failed"
    STATUS_SYNCED = "Synced"

    # Tuple for easy iteration/validation
    SYNC_STATUS_CHOICES = (
        STATUS_NOT_SYNCED,
        STATUS_SYNCING_CALENDAR,
        STATUS_SYNCING_MAILS,
        STATUS_SYNCING,
        STATUS_FAILED,
        STATUS_SYNCED,
    )

    def __init__(self, user, access_token):
        if not user:
            raise ValueError("User must be provided")
        
        self.user = user
        self.access_token = access_token

        user_ca = frappe.db.exists(self.CALENDAR_DOCTYPE, {"user": self.user})
        if not user_ca:
            token_doc = frappe.get_doc({
                "doctype": self.CALENDAR_DOCTYPE,
                "user": self.user,
            })
            token_doc.insert()
            frappe.db.commit()

        user_ca = frappe.get_doc(self.CALENDAR_DOCTYPE, {"user": self.user})
        self.sync_token = user_ca.sync_token 
        
    # def set_sync_status(self, status: str):
    #     """
    #     Update the user's workspace sync status.

    #     :param status: One of the SYNC_STATUS_CHOICES values.
    #     """
    #     if status not in self.SYNC_STATUS_CHOICES:
    #         frappe.throw(f"Invalid sync status: {status}")

    #     doc = frappe.get_doc("User", self.user)
    #     doc.sync_workspace_status = status
    #     doc.save(ignore_permissions=True)
    #     frappe.db.commit()
    #     return 

    def set_sync_token(self,sync_token):
        try:
            token_doc = frappe.get_doc(self.CALENDAR_DOCTYPE, {"user": self.user})
            token_doc.sync_token = sync_token
            token_doc.save(ignore_permissions=True)
            frappe.db.commit()
            return
        except Exception as error:
            frappe.log_error(str(error))
            print(str(error))

    def sync_events(self): #tbd - better name
        # self.set_sync_status(self.STATUS_SYNCING_CALENDAR)
        try:
            frappe.log(f"Workspace Calendar Sync Starting ... ")
            events = self.get_events()
            self.save_events(events) 
        except Exception as error:
            frappe.throw("Calendar Full Sync Failed")
            frappe.frappe.log_error(title="Calendar Full Sync Failed", message=f"{str(error)}\n\nTraceback:\n{frappe.get_traceback()}")
            # self.set_sync_status(self.STATUS_FAILED)
            return 
        else:
            # self.set_sync_status(self.STATUS_SYNCED)
            frappe.log(f"Workspace Calendar Full Sync Complete - Fetched {len(events)} Items ")
            return {"status":"sucess","message":f"Workspace Calendar Full Sync Complete - Fetched {len(events)} Items"}
    
    def get_events(self, calendar_id="primary"):
        """Sync GW Calendar Event. Works for first-time and incremental sync."""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"

            events = []
            params = {"maxResults": 2500}

            # Check if we already have a stored sync token
            last_sync_token = self.sync_token

            if last_sync_token:
                # Incremental sync (Google only returns changes)
                params["syncToken"] = last_sync_token
                print(f"🔄 Incremental sync with token: {last_sync_token}")
            else:
                # First-time sync — must be full list, no filters
                params["singleEvents"] = True
                params["showDeleted"] = True
                params["singleEvents"]=True
                print("🌱 First-time sync (fetching all events)")

            while True:
                res = requests.get(url, headers=headers, params=params)
                data = res.json()
                # Handle expired/invalid sync token → must re-sync full
                if data.get("error", {}).get("reason") == "fullSyncRequired":
                    print("⚠ Sync token expired — doing full sync again")
                    self.set_sync_token(None)  # Clear stored token
                    return False
                events.extend(data.get("items", []))
                if "nextPageToken" in data:
                    params["pageToken"] = data["nextPageToken"]
                else:
                    next_token = data.get("nextSyncToken")
                    if next_token:
                        self.set_sync_token(next_token)
                        print(f"✅ Saved new sync token: {next_token}")
                    break

            return events
        except Exception as error:
            frappe.throw(str(error))
            frappe.log_error(str(error))
        
    def save_events(self, events):
        """
        Save GW Calendar Event into the `GW Calendar Event` DocType.
        """
        try:            
            for ev in events:
                if ev.get("eventType") == "default": # TBD - handle this properly later
                    google_event_id = ev.get("id")
                    existing_event = frappe.get_all(
                        "GW Calendar Event",
                        filters={"google_event_id": google_event_id, "user": self.user},
                        limit=1
                    )
                    doc = None
                    if existing_event:
                        doc = frappe.get_doc("GW Calendar Event", existing_event[0].name)
                        print(doc)
                        print("fullevent",ev)
                    else:
                        doc = frappe.new_doc("GW Calendar Event")
                        doc.user = self.user
                        doc.google_event_id = google_event_id

                    # Map fields
                    doc.summary = ev.get("summary")
                    doc.description = ev.get("description")
                    doc.start_datetime = self._parse_datetime(ev.get("start"))
                    doc.end_datetime = self._parse_datetime(ev.get("end"))
                    doc.all_day_event = self._is_all_day(ev.get("start"))
                    doc.status = ev.get("status", "Confirmed").capitalize()
                    doc.location = ev.get("location")
                    doc.created_on = self._parse_google_datetime(ev.get("created"))
                    doc.updated_on = self._parse_google_datetime(ev.get("updated"))
                    doc.etag = ev.get("etag")
                    doc.recurring_event_id = ev.get("recurringEventId")
                    print(doc.summary,'summary')
                    # Handle attendees table
                    doc.attendees = []

                    attendees = ev.get("attendees", [])
                    if attendees:
                        for attendee in attendees:
                            email = attendee.get("email")
                            doc.append("attendees", {
                                "email": email,
                                "response_status": attendee.get("responseStatus"),
                                "display_name": attendee.get("displayName"),
                                "self": 1 if attendee.get("self") else 0 
                            })
                    doc.save(ignore_permissions=True)
            frappe.db.commit()
        except Exception as err:
            frappe.throw(str(err))
            # self.set_sync_status(status=self.STATUS_FAILED)
        else:
            # self.set_sync_status(status=self.STATUS_SYNCED)
            return True

    def register_watch(self, calendar_id: str = "primary", ) -> dict:
        try:
            """Create a watch channel for a user's calendar and store channel info on User."""

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }

            # Unique channel id per user (or per calendar if you support many)
            channel_id = str(uuid.uuid4())

            # Optional per-user secret echoed by Google in X-Goog-Channel-Token for verification
            channel_token = frappe.db.get_value(self.CALENDAR_DOCTYPE, self.user, "watch_channel_token") or str(uuid.uuid4())

            payload = {
                "id": channel_id,
                "type": "web_hook",
                "address": f"{frappe.utils.get_url()}/api/method/crm.api.google_workspace.api.google_calendar_notify",
                # Token is echoed back in the webhook headers (X-Goog-Channel-Token)
                "token": channel_token,
                # NOTE: Calendar often ignores custom TTL; rely on returned 'expiration'
                # "params": {"ttl": "604800"}  # up to 7 days; ignored by Calendar in many cases
            }

            url = f"{self.BASE_URL}/{calendar_id}/events/watch"
            r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
            print(r.status_code,r.content)
            resp = r.json()

            if r.status_code >= 300 or "resourceId" not in resp:
                frappe.throw(f"Failed to start watch: {resp}")

            # Save channel info
            expiration_ms = resp.get("expiration")  # milliseconds since epoch (string)
            expiration_dt = None
            if expiration_ms:
                expiration_dt = datetime.fromtimestamp(int(expiration_ms) / 1000.0)

            doc = frappe.get_doc(self.CALENDAR_DOCTYPE,{"user": self.user})
            doc.watch_channel_id = resp["id"]
            doc.watch_resource_id = resp["resourceId"]
            doc.watch_expiration = expiration_dt
            doc.watch_channel_token = channel_token
            # doc.created_on = now_datetime  # uncomment if field exists
            doc.save(ignore_permissions=True)
            frappe.db.commit()
            print("Calendar Watch Created Succesfully")
            return True
        except Exception as error:
            frappe.throw(str(error))

    def _parse_datetime(self, date_dict):
        """
        Google Calendar's start/end fields can be:
        - {"dateTime": "2024-07-15T20:30:00+05:30", "timeZone": "Asia/Kolkata"}
        - {"date": "2024-07-15"} for all-day events
        """
        if "dateTime" in date_dict:
            # Parse aware datetime
            dt = datetime.fromisoformat(date_dict["dateTime"])
        elif "date" in date_dict:
            # All-day event → midnight UTC conversion
            dt = datetime.fromisoformat(date_dict["date"])
            dt = pytz.timezone("Asia/Kolkata").localize(dt)
        else:
            return None

        # If not aware, assume Asia/Kolkata
        if dt.tzinfo is None:
            dt = pytz.timezone("Asia/Kolkata").localize(dt)

        # Convert to UTC, then remove tzinfo for MariaDB
        return dt.astimezone(pytz.UTC).replace(tzinfo=None)

    def _parse_google_datetime(self, dt_str):
        """Parses Google datetime strings into naive UTC datetimes for MariaDB."""
        if not dt_str:
            return None
        dt = datetime.fromisoformat(dt_str)  # Handles offset like +05:30
        if dt.tzinfo is None:
            dt = pytz.timezone("Asia/Kolkata").localize(dt)
        return dt.astimezone(pytz.UTC).replace(tzinfo=None)

    def _is_all_day(self, dt_obj):
        """Detect if the event is an all-day event."""
        return bool(dt_obj and "date" in dt_obj)

    @staticmethod
    def _run_incremental_sync(user: str,access_token):
        sync_instance = GoogleCalendarSync(user,access_token)

        try:
            processed = GoogleCalendarSync.get_events(user, "primary")
            frappe.logger("google_calendar").info(f"Incremental sync for {user}: {processed} items")
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Google Calendar incremental sync failed for {user}")
    

from .workspace_items import process_workspace_item

def calendar_event_handler_enqueue(doc,method):
    process_workspace_item(doc,event_doc=True)
