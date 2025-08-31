#!/bin/bash

bench --site frappecrm.brainvire.net migrate
bench --site frappecrm.brainvire.net clear-cache
bench --site frappecrm.brainvire.net clear-website-cache
bench restart


# bench --site frappecrm.brainvire.net export-fixtures
# bench --site frappecrm.brainvire.net backup


bench --site frappecrm.brainvire.net install-app erpnext
bench --site frappecrm.brainvire.net install-app hrms
bench --site frappecrm.brainvire.net install-app crm



bench --site frappecrm.brainvire.net clear-queue
bench --site frappecrm.brainvire.net purge-jobs
bench restart



import frappe


def da(doctype):
    # fetch all document names
    docs = frappe.get_all(doctype, pluck="name")

    for name in docs:
        frappe.delete_doc(doctype, name, force=1, ignore_permissions=True)

    frappe.db.commit()
    print(f"✅ Deleted {len(docs)} documents from {doctype}")




import frappe, os, json

site = frappe.local.site
export_path = os.path.join(frappe.get_site_path(), "doctype_exports")
os.makedirs(export_path, exist_ok=True)

# fetch all doctypes (including custom ones)
doctypes = frappe.get_all("DocType", fields=["name", "custom"])

for dt in doctypes:
    try:
        doc = frappe.get_doc("DocType", dt.name)
        filepath = os.path.join(export_path, f"{doc.name}.json")
        with open(filepath, "w") as f:
            f.write(json.dumps(doc.as_dict(), indent=2, default=str))
        print(f"✅ Exported {doc.name} → {filepath}")
    except Exception as e:
        print(f"❌ Failed {dt.name}: {e}")



ALTER USER '_322784eab57fe8cc'@'%' IDENTIFIED BY 'frappepass';
ALTER USER '_38adf462385fea20'@'%' IDENTIFIED BY 'frappepass';
ALTER USER '_fd92f56b0cd97285'@'%' IDENTIFIED BY 'frappepass';


 _322784eab57fe8cc   bad
 _38adf462385fea20  
  _fd92f56b0cd97285  bad





# Append a new row in the child table 'emails'
user_doc.append("events", {"event": event.name,"event_summary":event.summary })

# Save the doc
user_doc.save(ignore_permissions=True)  # ignore_permissions if running server-side
frappe.db.commit()  # ensure D