from google_calendar_sync import sync_events
import uuid, json, requests, frappe
from datetime import datetime, timedelta
from auth import GoogleAuth

BASE = "https://www.googleapis.com/calendar/v3/calendars"

def start_watch(user, auth, calendar_id: str = "primary", ) -> dict:
    """Create a watch channel for a user's calendar and store channel info on User."""
    headers = {
        "Authorization": f"Bearer {auth.access_token}",
        "Content-Type": "application/json"
    }

    # Unique channel id per user (or per calendar if you support many)
    channel_id = str(uuid.uuid4())

    # Optional per-user secret echoed by Google in X-Goog-Channel-Token for verification
    channel_token = frappe.db.get_value("User", user, "google_watch_channel_token") or str(uuid.uuid4())

    payload = {
        "id": channel_id,
        "type": "web_hook",
        "address": f"{frappe.utils.get_url()}/api/method/crm.api.google_workspace.api.google_calendar_notify",
        # Token is echoed back in the webhook headers (X-Goog-Channel-Token)
        "token": channel_token,
        # NOTE: Calendar often ignores custom TTL; rely on returned 'expiration'
        # "params": {"ttl": "604800"}  # up to 7 days; ignored by Calendar in many cases
    }

    url = f"{BASE}/{calendar_id}/events/watch"
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
    resp = r.json()

    if r.status_code >= 300 or "resourceId" not in resp:
        frappe.throw(f"Failed to start watch: {resp}")

    # Save channel info
    expiration_ms = resp.get("expiration")  # milliseconds since epoch (string)
    expiration_dt = None
    if expiration_ms:
        expiration_dt = datetime.utcfromtimestamp(int(expiration_ms) / 1000.0)

    frappe.db.set_value("User", user, {
        "google_watch_channel_id": resp["id"],
        "google_watch_resource_id": resp["resourceId"],
        "google_watch_expiration": expiration_dt,
        "google_watch_channel_token": channel_token
    })
    frappe.db.commit()
    return resp

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

