import frappe
from .integrations import inc_google_workspace_cal_sync, inc_google_workspace_mail_sync


@frappe.whitelist(allow_guest=True)
def google_calendar_notify():
    """
    Google sends an empty POST with headers when the calendar changes.
    We must return 200 quickly; do actual work in a background job.
    """
    try:
        # Required headers from Google push notifications
        resource_state = frappe.request.headers.get("X-Goog-Resource-State")
        resource_id    = frappe.request.headers.get("X-Goog-Resource-Id")
        channel_id     = frappe.request.headers.get("X-Goog-Channel-Id")
        channel_token  = frappe.request.headers.get("X-Goog-Channel-Token")  # echoed back if set
        message_num    = frappe.request.headers.get("X-Goog-Message-Number")

        # Optional: global webhook secret check
        expected_global = getattr(frappe.conf, "google_webhook_secret", None)

        # Find the GW Calendar Account by channel_id or resource_id
        account = None
        accounts = frappe.get_all("GW Calendar Account",
            filters=[
                ["GW Calendar Account", "watch_channel_id", "=", channel_id],
                ["GW Calendar Account", "watch_resource_id", "=", resource_id],
            ],
            pluck="name"
        )
        if accounts:
            account = accounts[0]

        # If not found by both, try either one (relaxes matching)
        if not account:
            accounts = frappe.get_all("GW Calendar Account",
                filters=[["GW Calendar Account", "watch_channel_id", "=", channel_id]],
                pluck="name"
            ) or frappe.get_all("GW Calendar Account",
                filters=[["GW Calendar Account", "watch_resource_id", "=", resource_id]],
                pluck="name"
            )
            if accounts:
                account = accounts[0]

        # Optional: per-account channel token verification
        if account:
            per_acc_token = frappe.db.get_value("GW Calendar Account", account, "watch_channel_token")
            if per_acc_token and channel_token and per_acc_token != channel_token:
                frappe.log_error(f"Channel token mismatch for account {account}", "Google Calendar Webhook")
                return "OK"

        # Global secret check (if you want to require it via query param)
        if expected_global:
            req_secret = frappe.local.request.args.get("secret")
            if req_secret != expected_global:
                frappe.log_error("Global secret mismatch", "Google Calendar Webhook")
                return "OK"

        # Log the incoming notification
        frappe.logger("google_calendar").info(
            f"[{message_num}] Change: state={resource_state}, channel={channel_id}, resource={resource_id}, account={account}"
        )

        if account:
            print("account exsist")
            # Update watch details on the account
            frappe.db.set_value("GW Calendar Account", account, {
                "watch_status": resource_state,
                "watch_channel_id": channel_id,
                "watch_resource_id": resource_id,
                "last_full_sync": frappe.utils.now(),
                "is_active": 1
            })
            frappe.db.commit()

            user_email = frappe.get_value("GW Calendar Account", account, "user")
            inc_google_workspace_cal_sync(user=user_email)
            print(f"Google watch called for {user_email}")
        return "OK"
    except Exception as error:
        frappe.throw(str(error))
        print(str(error))