app_name = "my_app"
app_title = "My App"
# ...

# Webhook (Google will call this)
# Endpoint URL: <your-site>/api/method/my_app.api.google_calendar_notify

scheduler_events = {
    # Renew watches hourly (cheap), fallback poll every 10 min
    "cron": {
        "0 * * * *": ["my_app.calendar_jobs.renew_all_watches"],  # hourly
        "*/10 * * * *": ["my_app.calendar_jobs.fallback_polling"] # every 10 min
    }
}
