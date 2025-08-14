frappe.ui.form.on('User', {
    sync_workspace: function(frm) {
        frappe.call({
            method: "crm.api.google_workspace.integrations.run_full_sync",
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
                            "authorize_google_account",
                            "label",
                            "Re-Authorize Google Account"
                        );
                    } else {
                        frm.set_df_property(
                            "authorize_google_account",
                            "label",
                            "Authorize Google Account"
                        );
                    }
                }
            });
        }
    },

    authorize_google_account(frm) {
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
