from google_calendar_sync import sync_events
import uuid, json, requests, frappe
from datetime import datetime, timedelta
from auth import GoogleAuth

BASE = "https://www.googleapis.com/calendar/v3/calendars"



def stop_watch(user: str) -> None:
    """Stop an active watch channel if present."""
    channel_id = frappe.db.get_value("User", user, "google_watch_channel_id")
    resource_id = frappe.db.get_value("User", user, "google_watch_resource_id")
    if not channel_id or not resource_id:
        return

    auth = GoogleAuth(user)
    headers = {
        "Authorization": f"Bearer {auth.access_token}",
        "Content-Type": "application/json"
    }
    payload = {"id": channel_id, "resourceId": resource_id}
    url = "https://www.googleapis.com/calendar/v3/channels/stop"
    # Best-effort; do not throw on failure
    try:
        requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
    except Exception:
        pass
    # Clear locally
    frappe.db.set_value("User", user, {
        "google_watch_channel_id": None,
        "google_watch_resource_id": None,
        "google_watch_expiration": None
    })
    frappe.db.commit()


def needs_renewal(user: str, skew_minutes: int = 30) -> bool:
    """Check if channel expires within skew_minutes (renew early)."""
    exp = frappe.db.get_value("User", user, "google_watch_expiration")
    if not exp:
        return True
    return exp <= (datetime.utcnow() + timedelta(minutes=skew_minutes))

def renew_watch_if_needed(user: str, calendar_id: str = "primary"):
    if needs_renewal(user):
        # Stop previous channel (safety), then start a new one
        stop_watch(user)
        start_watch(user, calendar_id)

