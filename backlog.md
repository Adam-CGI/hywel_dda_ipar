# Hywel Dda IPAR — Document Miner Backlog (MVP)

**Environment:** `dev`  
**Prefix convention:** `hdipar-<service>-<env>`  
**Stack:** Python (Flask + HTMX) | Azure OpenAI | Azure AI Search | Azure Document Intelligence | Azure Blob | Azure Cosmos DB | Entra External ID

---

## EPIC A — Azure Foundation

### 1. Create Azure Resources
**User Story:**  
As an engineer, I need a secure, reproducible Azure baseline to host the Document Miner and support external user access.

| **Service**            | **Name**              | **Purpose**                          |
|-------------------------|-----------------------|--------------------------------------|
| **Resource Group**      | `RG_300000000120926_Hywel_Dda_AI`       | Logical container                    |
| **Storage Account**     | `sthdipardev`         | Store PDFs, extracted JSON, thumbnails, manifests |
| **Blob Containers**     | `raw`, `extracted`, `thumbs`, `manifests`, `archive` | File segregation                     |
| **Azure AI Search**     | `ais-hdipar-dev`      | Chunk + vector index                 |
| **Azure OpenAI**        | `aoai-hdipar-dev`     | Embeddings (`text-embedding-3-large`) |
| **Document Intelligence** | `di-hdipar-dev`     | PDF text + layout extraction         |
| **Cosmos DB Account**   | `cosmos-hdipar-dev`   | Metadata + lineage                   |
| **Cosmos Database**     | `ipar`               | Logical DB                           |
| **Containers**          | `documents`, `lineage`, `events`, `users` | Entity segregation                   |
| **App Service Plan**    | `asp-hdipar-dev`      | Linux B1 tier                        |
| **App Service (Flask Web App)** | `app-hdipar-dev` | API + UI                            |
| **Key Vault**           | `kv-hdipar-dev`       | Secrets management                   |
| **Managed Identity**    | `mi-hdipar-dev`       | Secure Azure resource access         |
| **Log Analytics Workspace** | `log-hdipar-dev` | Central logging                      |
| **Application Insights** | `appi-hdipar-dev`    | Telemetry                            |
| **External ID Tenant**  | `eid-hdipar-dev`      | External authentication for clients  |

**Acceptance Criteria:**
- All resources deployed and tagged.
- App Service uses Managed Identity for Blob, Search, Cosmos.
- EasyAuth configured with External ID login.

---

## EPIC B — Ingestion Pipeline

### 2. Upload API
**User Story:**  
As a user, I upload PDFs for analysis via the web UI.  
**Endpoint:** `/api/documents/upload`  
**Storage:** `sthdipardev/raw/<sha256>.pdf`

### 3. Extraction
**User Story:**  
As the system, I extract text/tables from PDFs using Document Intelligence.  
**Outputs:**
- `sthdipardev/extracted/<doc_id>.json`  
- `sthdipardev/thumbs/<doc_id>/pN.png`  
- `sthdipardev/manifests/<doc_id>.json`

### 4. Manifest + Lineage
**Persistence:**
- Record in `cosmos-hdipar-dev.ipar.documents`  
- Event log in `ipar.events`

---

## EPIC C — Chunking, Embedding & Indexing

### 5. Chunker
**User Story:**  
As the system, I split extracted text into deterministic, traceable chunks.  
**Acceptance Criteria:**
- Unique `chunk_id` = hash of `{doc_id,page_no,span}`  
- Mapped spans for citation.
- Using llama-index for chunking configuration.

### 6. Embeddings
**Service:** `aoai-hdipar-dev`  
**Model:** `text-embedding-3-large`  
**Acceptance Criteria:**
- ≤512 chunks per batch  
- Vector dimension = 3072

### 7. AI Search Index
**Service:** `ais-hdipar-dev`  
**Index Name:** `ipar-chunks`  
**Profile:** `veconf`  
**Key Field:** `id`  
**Acceptance Criteria:**
- index doesnt exist yet.
- Hybrid BM25 + vector search working.

---

## EPIC D — Duplicate & Version Control

### 8. Exact Duplicate Detection
**Logic:**
- Compute `sha256`.  
- Check Cosmos `documents`.  
- Block re-upload if duplicate found.

### 9. Logical Duplicate / Versioning
**Logic:**
- Compute normalized text hash → `logical_id`.  
- On match → prompt user for “Create new version?”.  
- Mark prior version as `superseded`.  
- Only latest version indexed.

### 10. Near-Duplicate Detection
**Logic:**
- Compare document embeddings (cosine > 0.995).  
- Store relation in `lineage`.

---

## EPIC E — Document Management UI

### 11. Document List View
**Columns:** Title, Version, Pages, Status, UploadedBy, UploadedAt  
**Actions:** Upload, Delete, View Details

### 12. Upload UX
- Drag/drop upload → `/api/documents/upload`.  
- Duplicate/near-duplicate check before indexing.

### 13. Document Detail View
- Carousel of thumbnails from `thumbs/`.  
- Extraction stats and manifest summary.  
- “Reindex” button for regenerating chunks.

### 14. Delete
**Endpoint:** `DELETE /api/documents/{doc_id}`  
**Process:**
- Delete chunks from `ais-hdipar-dev.ipar-chunks`.  
- Mark Cosmos doc as deleted.  
- Move to Blob `/archive/`.

---

## EPIC F — Search & Citations

### 15. Search API
**Endpoint:** `/api/search`  
**Search Type:** Hybrid BM25 + vector retrieval.  
**Output:** Chunk hits with metadata.

### 16. Citations
**Fields Returned:**
- `doc_id`, `title`, `page_no`, `span`, `snippet`, `thumb_url` (SAS).  
**UI:**
- Numbered citation chips.  
- Click opens page preview.

---

## EPIC G — Persistence & Lineage

### 17. Cosmos Models
| **Container** | **Purpose**              |
|---------------|--------------------------|
| `documents`   | File metadata            |
| `lineage`     | Links: doc→chunk, version→version |
| `events`      | Audit trail              |
| `users`       | Role mapping for External ID users |

### 18. Idempotent Ingest
- Ingest keyed by `sha256` + `ingest_run_id`.  
- Re-running ingestion does not duplicate chunks.

---

## EPIC H — Security & Access (External ID)

### 19. Entra External ID Authentication
**User Story:**  
As an admin, I can create client accounts that can log in with their own password, without accessing our Microsoft tenant.

**Resources:**
| **Component**          | **Name**              | **Purpose**                          |
|-------------------------|-----------------------|--------------------------------------|
| **External ID Tenant**  | `eid-hdipar-dev`      | Authentication tenant                |
| **User Flow (Sign-In)** | `B2C_1_hdipar_susi_dev` | Email + password flow              |
| **User Flow (Password Reset)** | `B2C_1_hdipar_pwreset_dev` | Password recovery         |
| **App Registration**    | `appreg-hdipar-docminer-dev` | Web app registration         |

**Configuration:**
- Redirect URI:  
  `https://app-hdipar-dev.azurewebsites.net/.auth/login/aad/callback`
- Disable self-signup; admin invites users.
- Password reset flow enabled.
- Roles stored in Cosmos `users` container.

**Environment Variables:**
```bash
AUTH_PROVIDER=external-id
EXTERNAL_ID_TENANT=eid-hdipar-dev.onmicrosoft.com
EXTERNAL_ID_CLIENT_ID=<GUID_from_appreg-hdipar-docminer-dev>
EXTERNAL_ID_ISSUER=https://eid-hdipar-dev.b2clogin.com/<tenant_guid>/v2.0/
EXTERNAL_ID_POLICY=B2C_1_hdipar_susi_dev
```

**User Provisioning:**
- Create user in External ID (portal or PowerShell).
- Temporary password set; forced change on first login.
- Assign role in users container (admin, user, viewer).

**Authentication Flow:**
1. Client opens app URL.
2. Redirect to External ID login page.
3. Login token validated by App Service or Flask middleware.
4. Role lookup in Cosmos.
5. Access granted per role.

---

## EPIC I — Observability

### 20. Application Insights
**Resource:** `appi-hdipar-dev`  
**Metrics:** Extraction time, embedding latency, search latency, API errors.

### 21. Structured Logging
**Sink:** `log-hdipar-dev`  
**Format:** JSON with `run_id`, `doc_id`, `latency_ms`, `user_id`.

---

## EPIC J — Tooling & Tests

### 22. Makefile Targets
```bash
make run
make ingest FILE=path.pdf
make reindex DOC_ID=...
make deploy
```

### 23. Tests
**Framework:** Pytest  
**Coverage:** Chunking, duplicate detection, search index upsert, ingestion idempotence.

---

### ✅ Definition of Done (MVP)
- ✅ All Azure and External ID resources created (`rg-hdipar-dev`, `eid-hdipar-dev`).
- ✅ App Service (`app-hdipar-dev`) authenticates via External ID and Managed Identity.
- ✅ Full ingestion → extraction → chunking → indexing pipeline operational.
- ✅ Duplicate and version checks work.
- ✅ Document management UI functional.
- ✅ Search returns page-level citations with previews.
- ✅ Client users authenticate using username/password without internal tenant access.
- ✅ Observability (App Insights + Logs) active and verified.