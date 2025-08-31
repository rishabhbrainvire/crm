frappe.ui.form.on('User', {
    sync_workspace: function(frm) {
        frappe.call({
            method: "crm.api.google_workspace.integrations.initiate_google_workspace_sync",
            args: { user: frappe.session.user },
            callback: function(r) {
                if (r.message) {
                    frappe.msgprint(r.message);
                }
            }
        });
    }
});

frappe.ui.form.on('User', {
    refresh(frm) {
        if (!frm.doc.__islocal) { // only run for saved users
            frappe.call({
                method: "crm.api.google_workspace.auth.check_google_auth_connection",
                args: { user: frappe.session.user },
                callback: function(r) {
                    if (r.message && r.message.connected) {
                        frm.set_df_property(
                            "authorize_via_google_auth",
                            "label",
                            "Re-Authorize your Google Account"
                        );
                    } else {
                        frm.set_df_property(
                            "authorize_via_google_auth",
                            "label",
                            "Authorize your Google Account"
                        );
                    }
                }
            });
        }
    },

    authorize_via_google_auth(frm) {
        frappe.call({
            method: "crm.api.google_workspace.auth.initiate_google_auth",
            args: { user: frappe.session.user },
            callback: function(r) {
                if (r.message) {
                    window.location.href = r.message;
                }
            }
        });
    }
});
