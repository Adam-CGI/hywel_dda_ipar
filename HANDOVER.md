# Hywel Dda IPAR Document Miner (RAG) Handover

## Branch Context

This handover is written for the **current branch**:

- `deployment_branch`

It reflects the repository state on this branch, not the mixed historical state from other branches or older notes.

Recent branch themes from git history:

- Azure deployment hardening
- Azure Document Intelligence SDK v4 upgrade
- Cosmos-backed authentication and admin user management
- UI/chat refinements
- removal/reorganisation of older files

---

## 1. What This Branch Is

This branch contains a Flask-based document ingestion, search, and RAG chat application for Hywel Dda IPAR documents.

Core workflow:

1. upload a document
2. store the original file in Azure Blob Storage
3. extract text/layout with Azure Document Intelligence
4. generate thumbnails where supported
5. chunk the content
6. generate embeddings with Azure OpenAI
7. upload chunks to Azure AI Search
8. store metadata, lineage, users, events, and query history in Cosmos DB
9. expose search and grounded chat through the web UI and API

This branch is not just a document miner anymore. It now also includes:

- Cosmos-backed username/password authentication
- admin UI for managing users
- query history persistence in Cosmos
- broader document upload support beyond PDF

---

## 2. Active Repo Structure

## Source of truth

The active application is the self-contained Flask app under:

- `flask_app/`

Important files and folders:

- `flask_app/application.py` - Flask entry point
- `flask_app/config.py` - environment loading and Azure client configuration
- `flask_app/routes/documents.py` - upload, search, chat, reindex, delete, UI endpoints
- `flask_app/routes/admin.py` - admin user management routes
- `flask_app/routes/pages.py` - About page
- `flask_app/services/` - Azure and business logic services
- `flask_app/templates/` - HTML templates
- `flask_app/static/` - current CSS/JS assets
- `flask_app/content/about.md` - editable About page content

Other notable root-level items:

- `deploy.sh` - safer branch deployment path targeting a `v2` app by default
- `scripts/` - operational and diagnostic scripts
- `services/` - root shims re-exporting `flask_app.services.*`
- `data/` - sample IPAR PDFs for local/manual testing

## What is not present on this branch

Compared with older states of the repo, this branch does **not** contain:

- `DEPLOYMENT_GUIDE.md`
- `reference.md`
- `tests/`
- `test_extract/`
- a root-level `app/` package

That matters because some older assumptions no longer apply.

---

## 3. Azure Resources And Purpose

The branch still points at the same core Azure estate for shared AI/data services.

## Main documented/shared resource group

- `RG_300000000120926_Hywel_Dda_AI`

Purpose:

- primary resource group for the Hywel Dda AI/RAG resources used by this app

## Core Azure resources referenced in code and config

| Resource Type | Name | Purpose |
| --- | --- | --- |
| Resource Group | `RG_300000000120926_Hywel_Dda_AI` | main Azure container for the solution |
| Storage Account | `sthdipardev` | stores raw uploads, extracted JSON, thumbnails, manifests, archived files |
| Blob Containers | `raw`, `extracted`, `thumbs`, `manifests`, `archive` | pipeline storage layers |
| Azure AI Search | `ais-hdipar-dev` | hybrid keyword + vector retrieval |
| Search Index | `ipar-chunks` | chunk store with metadata and embeddings |
| Azure OpenAI | `aoai-hdipar-dev` | embeddings and chat completions |
| OpenAI Deployment | `text-embedding-3-large` | chunk/document embeddings |
| OpenAI Deployment | `gpt-4o` | current chat generation model on this branch |
| Document Intelligence | `di-hdipar-dev` | extraction of text/layout/tables from uploaded documents |
| Cosmos DB | `cosmos-hdipar-dev` | metadata, lineage, users, events, query history |
| Cosmos Database | `ipar` | main application database |
| Cosmos Containers | `documents`, `lineage`, `events`, `users`, `queries` | application persistence |
| Application Insights | configured via connection string | telemetry/log export |

## App Service targets on this branch

There are two distinct App Service stories in this branch.

### Existing dev target

- App Service: `app-hdipar-dev`
- App Service Plan: `asp-hdipar-dev`

This target is still referenced by:

- `flask_app/deploy_webapp.ps1`
- `flask_app/appsettings.json`

### Safer branch deployment target

- App Service: `app-hdipar-v2`
- App Service Plan: `asp-hdipar-v2`

This target is the default in:

- `deploy.sh`

Important branch behavior:

- `deploy.sh` contains a safety check that will **not** deploy to `app-hdipar-dev`

Practical interpretation:

- shared AI/data services appear to remain the `*-dev` resources
- this branch adds a safer application deployment path to a separate `v2` web app

---

## 4. Current Runtime Behavior

## Authentication

Authentication is now handled against Cosmos DB user records, not a hardcoded username/password.

Runtime behavior in `flask_app/application.py`:

- user submits username/password at `/login`
- `CosmosService.verify_user()` checks the `users` container
- session is populated with:
  - `logged_in`
  - `username`
  - `user_id`
  - `is_admin`

Admin-only access is enforced for:

- `/admin/users`

## Admin user management

This branch includes a real admin UI and flows for:

- create user
- activate/deactivate user
- grant/revoke admin
- reset password

Those are implemented in:

- `flask_app/routes/admin.py`
- `flask_app/templates/admin_users.html`

## Query history

Chat requests are now persisted to a Cosmos `queries` container.

Stored data includes:

- user id
- username
- query
- response
- simplified source metadata
- token usage
- created timestamp

This is implemented in:

- `flask_app/routes/documents.py`
- `flask_app/services/cosmos_service.py`

## Chat model

Current code defaults to:

- `gpt-4o`

This is defined in:

- `flask_app/config.py`
- `flask_app/services/chat_service.py`
- `flask_app/appsettings.json`

## Supported upload formats

This branch supports more than PDFs.

Allowed upload extensions in `flask_app/routes/documents.py`:

- `.pdf`
- `.png`
- `.jpg`
- `.jpeg`
- `.tiff`
- `.bmp`
- `.docx`
- `.xlsx`
- `.pptx`

Explicitly rejected legacy Office formats:

- `.doc`
- `.xls`
- `.ppt`

## Document Intelligence SDK

This branch uses:

- `azure-ai-documentintelligence`
- `DocumentIntelligenceClient`

The extraction service was updated for the newer SDK and supports broader document types.

---

## 5. Data Flow On This Branch

## Upload flow

1. file upload hits `/api/documents/upload`
2. file extension is validated
3. `doc_id` is computed from SHA256 of file bytes
4. exact duplicate detection checks Cosmos
5. file is uploaded to Blob Storage
6. extraction runs through Azure Document Intelligence `prebuilt-layout`
7. extraction JSON, thumbnails, and manifest are written to storage
8. `logical_id` is computed from normalized text
9. logical duplicate/version workflow runs
10. document embedding is created for near-duplicate detection
11. metadata is saved to Cosmos
12. chunks are generated and enriched
13. temporal metadata is extracted from filename where possible
14. embeddings are generated for chunks
15. chunks are uploaded to Azure AI Search

## Search flow

1. query embedding is generated
2. AI Search runs hybrid BM25 + vector retrieval
3. results come back with citations, metadata, and optional thumbnail SAS URLs

## Chat flow

1. user submits a question to `/api/documents/chat`
2. relevant chunks are retrieved from AI Search
3. GPT-4o generates a grounded answer
4. an event is logged
5. full query history is saved into Cosmos `queries`

---

## 6. Search Index Notes

Search index name:

- `ipar-chunks`

Important characteristics from `flask_app/services/search_index_service.py`:

- vector dimension: `3072`
- embedding model alignment: `text-embedding-3-large`
- HNSW vector profile: `veconf`
- semantic config present for title/content relevance

Important fields include:

- `id`
- `doc_id`
- `logical_id`
- `version`
- `source_uri`
- `title`
- `origin_filename`
- `page_no`
- `observed_date`
- `document_date`
- `year`
- `month`
- `quarter`
- `fiscal_year`
- `kpi_tags`
- `text`
- `spans`
- `vector`

---

## 7. Cosmos DB Notes

This branch expects these Cosmos containers:

- `documents`
- `lineage`
- `events`
- `users`
- `queries`

Purpose of each:

- `documents` - document metadata and status
- `lineage` - duplicate / supersession / relationship tracking
- `events` - operational and audit-style events
- `users` - login and admin-managed user records
- `queries` - stored user chat history

Operational implication:

- this branch cannot be treated as read-only document indexing anymore
- a working `users` container is required for normal login

---

## 8. Local Setup

## Python and dependencies

This branch targets:

- Python `3.11`

Install from the self-contained app:

```bash
cd flask_app
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment files

Current branch reality is slightly inconsistent:

- `flask_app/.env.example` exists
- there is **no** root `.env.example`
- `flask_app/deploy_webapp.ps1` expects `flask_app/.env`
- `deploy.sh` expects a root `.env` by default
- `scripts/seed_admin_user.py` also loads a root `.env`

Practical working approach:

1. keep a root `.env` for `deploy.sh` and root scripts
2. keep `flask_app/.env` for the self-contained PowerShell deployment flow
3. ensure both contain the same actual values if you use both workflows

## Run locally

```bash
cd flask_app
python application.py
```

Useful endpoints:

- `/health`
- `/ready`
- `/login`
- `/about`
- `/admin/users`
- `/api/documents/ui/`
- `/api/documents/ui/chat`

---

## 9. Seeding The First Admin User

Because auth now depends on Cosmos users, you need an initial user.

Use:

```bash
python scripts/seed_admin_user.py
```

What it does:

- creates an admin user if one does not exist
- generates a secure password
- stores credentials in `.admin_credentials`
- can reset an existing admin password with `--force`

Important:

- delete `.admin_credentials` after capturing the credentials

---

## 10. Deployment Paths On This Branch

## Recommended branch-safe deployment path

Use:

- `deploy.sh`

Why this is the safer path on `deployment_branch`:

- defaults to `app-hdipar-v2`
- defaults to `asp-hdipar-v2`
- explicitly refuses to deploy to `app-hdipar-dev`
- enables Oryx build during deployment
- sets a 600s start time limit
- handles the case where `az webapp deploy` returns a 504 while the build continues in the background
- performs a health-check wait loop after deployment

Command example:

```bash
./deploy.sh
```

Or with explicit parameters:

```bash
./deploy.sh --name app-hdipar-v2 --plan asp-hdipar-v2 --group RG_300000000120926_Hywel_Dda_AI --location uksouth --env-file .env
```

## Existing PowerShell deployment path

Also present:

- `flask_app/deploy_webapp.ps1`

That script still targets:

- `app-hdipar-dev`
- `RG_300000000120926_Hywel_Dda_AI`

Use it only if you intentionally want to deploy to the existing dev app.

## Startup command

Current startup command:

```bash
gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 4 --worker-class sync --access-logfile '-' --error-logfile '-' application:app
```

## Post-deploy checks

```bash
curl https://<app-name>.azurewebsites.net/health
curl https://<app-name>.azurewebsites.net/ready
az webapp log tail --name <app-name> --resource-group RG_300000000120926_Hywel_Dda_AI
```

---

## 11. Scripts Worth Knowing

- `deploy.sh` - branch-safe deployment to `v2` app target
- `scripts/seed_admin_user.py` - create/reset initial admin user
- `scripts/recreate_index.py` - recreate the AI Search index
- `scripts/recreate_index_with_temporal.py` - related temporal reindex workflow
- `scripts/reindex_with_temporal.py` - clear and rebuild indexed content with temporal metadata
- `scripts/bulk_reindex_all.py` - call the reindex endpoint for multiple docs
- `scripts/check_upload_status.py` - inspect document/index status
- `scripts/test_search_and_chat.py` - smoke test search/chat
- `scripts/pilot_test_new_sdk.py` - validate the new Document Intelligence SDK behavior

---

## 12. Known Inconsistencies On This Branch

These are the main things the next engineer should know.

### 1. Deployment docs are not fully aligned

`flask_app/README.md` and `flask_app/DEPLOYMENT.md` still reference older names like:

- `hdipar-app-dev`
- `rg-hdipar-dev`

But current branch deployment code uses:

- `app-hdipar-dev`
- `RG_300000000120926_Hywel_Dda_AI`
- `app-hdipar-v2`
- `asp-hdipar-v2`

### 2. Env template is behind runtime in a few places

`flask_app/.env.example` still contains outdated assumptions:

- `RESOURCE_GROUP=rg-hdipar-dev`
- `AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o-mini`
- no `COSMOS_COLL_QUERIES`

But current code expects:

- main RG is the long `RG_300000000120926_Hywel_Dda_AI`
- default chat model is `gpt-4o`
- queries container is part of the app model

### 3. External ID variables are present but not active auth

`flask_app/config.py` still defines:

- `AUTH_PROVIDER`
- `EXTERNAL_ID_*`

But runtime login on this branch is Cosmos-backed local auth, not External ID.

### 4. There is no checked-in IaC

This branch still has no Terraform/Bicep/ARM to recreate the Azure estate from code.

### 5. No `tests/` directory on this branch

Validation on this branch relies on:

- local/manual smoke tests
- deployment health checks
- operational scripts

---

## 13. Rebuilding Or Replicating This Branch

There is no single automated environment bootstrap in the repo.

To replicate the branch end to end, you need:

1. an Azure resource group
2. Blob Storage with the required containers
3. Azure AI Search with index `ipar-chunks`
4. Azure OpenAI with:
   - `text-embedding-3-large`
   - `gpt-4o`
5. Azure Document Intelligence
6. Cosmos DB with containers:
   - `documents`
   - `lineage`
   - `events`
   - `users`
   - `queries`
7. an App Service Plan and Web App
8. App Service settings matching the app config
9. an initial seeded admin user

If rebuilding the app tier for this branch specifically, prefer:

- `app-hdipar-v2`
- `asp-hdipar-v2`

while keeping the shared AI/data services aligned with the current `*-dev` resources unless Azure proves otherwise.

---

## 14. First-Day Checklist For The Next Engineer

1. read this file first
2. treat `flask_app/` as the source of truth
3. decide whether you are targeting:
   - existing `app-hdipar-dev`
   - safer branch target `app-hdipar-v2`
4. verify Azure resources and app settings in Portal
5. ensure Cosmos has the `users` and `queries` containers
6. create or reset an admin user with `scripts/seed_admin_user.py`
7. run the app locally
8. verify `/health`, `/ready`, `/login`, `/admin/users`
9. upload one sample file from `data/`
10. test search and chat
11. if deploying this branch, prefer `deploy.sh`
12. update stale env/deployment docs before relying on them for others

---

## 15. Files Used To Build This Handover

- `flask_app/application.py`
- `flask_app/config.py`
- `flask_app/routes/documents.py`
- `flask_app/routes/admin.py`
- `flask_app/routes/pages.py`
- `flask_app/services/cosmos_service.py`
- `flask_app/services/chat_service.py`
- `flask_app/services/search_service.py`
- `flask_app/services/search_index_service.py`
- `flask_app/services/extraction_service.py`
- `flask_app/appsettings.json`
- `flask_app/startup.txt`
- `flask_app/requirements.txt`
- `flask_app/README.md`
- `flask_app/DEPLOYMENT.md`
- `flask_app/.env.example`
- `deploy.sh`
- `scripts/seed_admin_user.py`
- `git log` on `deployment_branch`

