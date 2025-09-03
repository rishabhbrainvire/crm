## Custom DocType List for Google Workspace

1. User GW Account

2. GW Calendar Account
3. GW Calendar Event
4. GW Calendar Event Attendee

5. GW Gmail Account
6. GW Gmail Mail

7. User GW Calendar Table
8. User GW Gmail Table

## Commands for exports

- `bench export-fixtures` -> will export all the fixtures (fixtures definition is writting in hooks.py file of the app)
- `bench --site frappecrm.brainvire.net migrate` -> will import all the fixtures


##  Rebase CRM APP

- Initialize a new Git repository
`git init`

- Add a remote origin (replace with your repo URL)
`git remote add origin https://github.com/rishabhbrainvire/crm.git`

- Verify that the remote is set
`git remote -v`

- Fetch latest remote data
`git fetch origin`

- Reset local branch to remote branch
`git reset --hard origin/main`


`bench --site frappecrm.brainvire.net reinstall`
bench --site frappecrm.brainvire.net --force reinstall


bench --site frappecrm.brainvire.net rename-doctype "User GW Gmail Child Table" "User GW Gmail Account"


## Create a Webpage