# Group 3 – station group picker (Streamlit)

40 people each pick their name and one of 7 groups. A name can only be saved once and a group closes when full.

## Files
- `app.py` – the app
- `store.py` – saves picks (Google Sheet when configured, local file for testing)
- `config.py` – roster, groups, leaders, stations and **capacities** (edit `cap` to change)
- `requirements.txt`, `.streamlit/secrets.toml.example`

## Deploy (about 10 minutes)

### 1. Put the code on GitHub
Create a new GitHub repository and upload every file in this folder (keep the `.streamlit` folder).
Do NOT upload a real `secrets.toml`.

### 2. Make the Google Sheet that stores the picks
1. Create a blank Google Sheet. Copy the ID from its URL: `docs.google.com/spreadsheets/d/<THIS PART>/edit`.
2. Go to console.cloud.google.com, create a project, and enable the **Google Sheets API** and **Google Drive API**.
3. IAM & Admin → Service Accounts → create one → Keys → Add key → JSON. Download the file.
4. In the Google Sheet click **Share** and add the service account's `client_email` (from the JSON) as **Editor**.

### 3. Deploy on Streamlit Community Cloud
1. Go to share.streamlit.io, sign in with GitHub, click **Create app**, choose your repo, branch, and `app.py`.
2. Open **Advanced settings → Secrets** and paste the contents of `.streamlit/secrets.toml.example`, filled in
   (`admin_password`, `sheet_id`, and the JSON fields under `[gcp_service_account]`).
3. Deploy. Streamlit gives you the public link to send to the 40 people.

### 4. Check before sharing
Open the link, make a test pick, and confirm a row appears in the Sheet. Then open the sidebar, enter the
admin password and press **Reset** on your test pick.

## Notes
- Without the Google Sheet secrets the app runs in **test mode** and stores picks in a local file, which Streamlit
  Cloud wipes on restart. Always connect the Sheet for the real run.
- The link is public and nobody signs in, so someone could choose another person's name. If that matters, tell me and
  I'll add a per-person PIN column.
- Run locally: `pip install -r requirements.txt` then `streamlit run app.py`.
