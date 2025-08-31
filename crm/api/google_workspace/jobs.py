# from google_calendar_sync import sync_events
# import frappe

# def renew_all_watches():
#     users = frappe.get_all("User", filters={"google_access_token": ["!=", ""]}, pluck="name")
#     for uid in users:
#         try:
#             renew_watch_if_needed(uid, "primary")
#         except Exception:
#             frappe.log_error(frappe.get_traceback(), f"Renew watch failed for {uid}")

# def fallback_polling():
#     """In case watch fails or is delayed, do a light periodic incremental sync."""
#     users = frappe.get_all("User", filters={"google_access_token": ["!=", ""]}, pluck="name")
#     for uid in users:
#         try:
#             sync_events(uid, "primary")
#         except Exception:
#             frappe.log_error(frappe.get_traceback(), f"Polling sync failed for {uid}")
