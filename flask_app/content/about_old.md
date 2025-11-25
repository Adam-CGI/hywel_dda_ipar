# About the Hywel Dda IPAR Document Intelligence RAG System

This page describes the current (pilot) state of the Hywel Dda IPAR Document Intelligence platform, clarifies scope boundaries, and outlines future development directions. Edit this file (`flask_app/content/about.md`) to change the content without touching templates or Python code.

## What It Is
- A Retrieval-Augmented Generation (RAG) pilot focused on NHS IPAR (Integrated Performance & Assurance Report) PDF documents.
- A deterministic ingestion and indexing pipeline: PDF → extract → chunk → embed → hybrid index (keyword + vector).
- Page-level semantic search with citations (thumbnails + source metadata) for transparent traceability.
- Duplicate-aware: exact, logical (content hash), and near-duplicate (embedding similarity) detection.
- Designed for data integrity, auditability, and reproducibility (stable chunk identifiers).
- Built on Azure services (Blob Storage, Document Intelligence, Cosmos DB, Azure OpenAI, Azure AI Search) with healthcare governance in mind.

## What It Isn’t
- Not a general-purpose chatbot for arbitrary medical advice or patient data.
- Not a clinical decision support tool; it does NOT replace professional judgment.
- Not a full production deployment yet (pilot / pre-production phase).
- Not performing real-time analytics beyond document-level metadata and chunk embeddings.
- Not an automated summarisation pipeline for all IPAR KPIs (future roadmap item).
- Not a system for storing or processing confidential patient-level data.

## Current Capabilities
- Upload detection: exact and logical duplicate prompts + optional versioning.
- Chunking tuned for balanced retrieval granularity (deterministic chunk IDs for reindex stability).
- Hybrid search (vector + keyword) with relevance-ranked results and page thumbnails for citations.
- RAG chat constrained to strictly cite retrieved page sources.
- Embedding dimension consistency (3072-d vectors with `text-embedding-3-large`).
- Cosmos lineage tracking for version supersession and near-duplicate relationships.
- Event logging of major pipeline stages (upload, extract, index) for auditability.

## Future Development
- KPI-aware semantic tagging and structured extraction enrichment.
- Automated summarisation / section-level abstraction for executive overview generation.
- Role-based access control and user tenancy model (Cosmos `users` collection).
- Fine-tuned retrieval scoring incorporating document version lineage.
- Vector reindexing optimisation and partial refresh strategies.
- Expanded monitoring dashboards (latency, embedding drift, retrieval quality metrics).
- Formal quality evaluations and guardrail policies for clinical governance.
- Multi-modal ingestion (Excel tables, structured data exports) beyond PDFs.
- Optional scheduled revalidation of logical duplicates against evolving corpora.

## Governance & Safety
- All responses cite explicit page sources to prevent hallucinated claims.
- No patient-identifiable data is ingested or surfaced.
- Embeddings stored only for IPAR text content; no sensitive fields.
- Deterministic processing ensures reproducibility and audit traces.

## How to Change This Page
1. Edit `flask_app/content/about.md`.
2. Save and refresh `/about` — no restart required (file is read at request time).
3. Maintain clear section headings for readability.
4. Avoid adding confidential or patient-level information.

_Last updated: 2025-11-04_
