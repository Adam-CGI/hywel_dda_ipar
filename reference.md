# Hywel Dda IPAR — Document Miner (MVP) Reference

**Resource Group:** `RG_300000000120926_Hywel_Dda_AI`  
**Region:** UK South (except Azure OpenAI: West Europe)  
**Purpose:** Ingest IPAR PDFs → extract → chunk + embed → index → search with page-level citations.

## Services and Why
- **Storage Account** `sthdipardev` (Blob): raw PDFs, extracted JSON, page thumbnails, manifests, archive.
  - Containers: `raw`, `extracted`, `thumbs`, `manifests`, `archive`.
- **Azure AI Search** `ais-hdipar-dev`: vector + keyword retrieval over chunks.
  - Index: `ipar-chunks` (3072-dim vector, HNSW profile `veconf`).
- **Azure OpenAI** `aoai-hdipar-dev`: embeddings for chunks.
  - Deployment: `text-embedding-3-large`.
- **Document Intelligence** `di-hdipar-dev`: PDF text/layout/table extraction; page mapping for citations.
- **Cosmos DB (NoSQL, serverless)** `cosmos-hdipar-dev`: metadata, lineage, events, user roles.
  - Database: `ipar`
  - Containers: `documents`, `lineage`, `events`, `users` (partition key `/id`).
- **App Service Plan** `asp-hdipar-dev` (Linux B1): host Flask API + HTMX UI.
- **App Service** `app-hdipar-dev`: web app endpoint to upload, manage, and search.
- **Application Insights** `appi-hdipar-dev`: telemetry and logs.
- **Log Analytics** `log-hdipar-dev`: centralized logging workspace.
- **Key Vault** `kv-hdipar-dev`: optional secret storage (keys/endpoints).
- **External ID Tenant** `eid-hdipar-dev` (later): client login with username/password.

## Data Flow
1. Upload PDF → `sthdipardev/raw`.
2. Extract with `di-hdipar-dev` → JSON to `extracted`, thumbnails to `thumbs`, manifest to `manifests`.
3. Chunk + embed (Azure OpenAI) → upsert to `ais-hdipar-dev` index `ipar-chunks`.
4. Store lineage and events in `cosmos-hdipar-dev` (`ipar` DB).
5. Search API returns chunks + citations (doc id, page no, span, thumb link).

## Identifiers and Conventions
- `doc_id = sha256(file_bytes)`
- `page_no` = 1-based page index.
- `chunk_id = sha256(doc_id + page_no + start_offset + text[:256])`
- Index fields: `id`, `doc_id`, `logical_id`, `version`, `source_uri`, `title`, `origin_filename`, `page_no`, `observed_date`, `kpi_tags[]`, `text`, `spans`, `vector`.

## What to copy into `.env`
- Storage connection string.
- Search endpoint + admin key.
- OpenAI endpoint + key + deployment name.
- Document Intelligence endpoint + key.
- Cosmos endpoint (URI) + primary key.
- App Insights connection string.
- Auth settings (when External ID is wired).

## Minimum SKUs
- Search: **Free** (upgrade to Basic if limits hit).
- Doc Intelligence: **F0**.
- App Service: **B1 Linux**.
- Cosmos: **Serverless**.
- OpenAI: **S0** (pay-as-you-go).

## Post-setup Checks
- Storage has 5 containers.
- Cosmos has DB `ipar` with 4 containers.
- OpenAI has deployment `text-embedding-3-large`.
- Search has index `ipar-chunks`.
- App Service running, App Insights connected.

