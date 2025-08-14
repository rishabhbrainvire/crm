import frappe
from google_calendar_sync import sync_events

@frappe.whitelist(allow_guest=True)
def google_calendar_notify():
    """
    Google sends an empty POST with headers when the calendar changes.
    We must return 200 quickly; do actual work in a background job.
    """
    # Required headers
    resource_state = frappe.request.headers.get("X-Goog-Resource-State")
    resource_id    = frappe.request.headers.get("X-Goog-Resource-Id")
    channel_id     = frappe.request.headers.get("X-Goog-Channel-Id")
    channel_token  = frappe.request.headers.get("X-Goog-Channel-Token")  # echoed back if set
    message_num    = frappe.request.headers.get("X-Goog-Message-Number")

    # Optional: verify shared secret (global)
    expected_global = getattr(frappe.conf, "google_webhook_secret", None)

    # Find the User by channel_id or resource_id
    user = None
    users = frappe.get_all("User",
        filters=[
            ["User", "google_watch_channel_id", "=", channel_id],
            ["User", "google_watch_resource_id", "=", resource_id],
        ],
        pluck="name"
    )
    if users:
        user = users[0]

    # If not found by both, try either one (relaxes matching)
    if not user:
        users = frappe.get_all("User",
            filters=[["User", "google_watch_channel_id", "=", channel_id]],
            pluck="name"
        ) or frappe.get_all("User",
            filters=[["User", "google_watch_resource_id", "=", resource_id]],
            pluck="name"
        )
        if users:
            user = users[0]

    # Optional: also verify per-user channel token if you stored one
    if user:
        per_user_token = frappe.db.get_value("User", user, "google_watch_channel_token")
        if per_user_token and channel_token and per_user_token != channel_token:
            frappe.log_error(f"Channel token mismatch for {user}", "Google Calendar Webhook")
            return "OK"

    # Global secret check (if you want to require it via query param)
    if expected_global:
        # e.g., you called watch with .../google_calendar_notify?secret=XYZ
        req_secret = frappe.local.request.args.get("secret")
        if req_secret != expected_global:
            frappe.log_error("Global secret mismatch", "Google Calendar Webhook")
            return "OK"

    # Ignore initial 'sync' state spam if you like; otherwise just enqueue on any change
    frappe.logger("google_calendar").info(
        f"[{message_num}] Change: state={resource_state}, channel={channel_id}, resource={resource_id}, user={user}"
    )

    if user:
        # Enqueue incremental sync (fast return!)
        frappe.enqueue("crm.api.google_workspace.google_calendar_sync.GoogleAuth._run_incremental_sync", queue="long", user=user, now=False)
    return "OK"


