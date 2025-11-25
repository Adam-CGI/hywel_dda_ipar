"""
Document upload routes for IPAR Document Intelligence.
"""
import logging
import json
from flask import Blueprint, request, jsonify, render_template
from datetime import datetime
from services.storage_service import StorageService
from services.extraction_service import ExtractionService
from services.cosmos_service import CosmosService
from services.embedding_service import EmbeddingService
from services.search_index_service import SearchIndexService
from services.search_service import SearchService
from services.chat_service import ChatService
from services.chunking_service import ChunkingService

logger = logging.getLogger(__name__)

documents_bp = Blueprint('documents', __name__, url_prefix='/api/documents')

# Initialize services
storage_service = StorageService()
extraction_service = ExtractionService()
cosmos_service = CosmosService()
embedding_service = EmbeddingService()
search_index_service = SearchIndexService()
search_service = SearchService()
chat_service = ChatService()
chunking_service = ChunkingService()


@documents_bp.route('/upload', methods=['POST'])
def upload_document():
    """
    Upload a PDF document for processing.
    Includes duplicate detection and versioning logic.
    
    Expected: multipart/form-data with 'file' field
    Optional query param: create_version=true to force version creation
    
    Returns:
        JSON response with doc_id and processing status
    """
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({
                'error': 'No file provided',
                'message': 'Please upload a PDF file'
            }), 400
        
        file = request.files['file']
        
        # Check if filename is empty
        if file.filename == '':
            return jsonify({
                'error': 'No file selected',
                'message': 'Please select a file to upload'
            }), 400
        
        # Check file type
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({
                'error': 'Invalid file type',
                'message': 'Only PDF files are supported'
            }), 400
        
        # Read file bytes
        file_bytes = file.read()
        origin_filename = file.filename
        
        # Get query param for version creation
        create_version = request.args.get('create_version', 'false').lower() == 'true'
        
        logger.info(f"Received upload request for {origin_filename}, create_version={create_version}")
        
        # Step 1: Compute doc_id (SHA256 of file bytes) - EPIC D.8 Exact Duplicate Detection
        doc_id = storage_service.compute_sha256(file_bytes)
        
        # Check if exact duplicate exists (but allow re-upload of deleted documents)
        existing_doc = cosmos_service.get_document(doc_id)
        if existing_doc and not existing_doc.get('is_deleted', False):
            # Document exists and is NOT deleted - true duplicate
            logger.info(f"Exact duplicate found: {doc_id}")
            return jsonify({
                'message': 'Exact duplicate detected - document already exists',
                'doc_id': doc_id,
                'origin_filename': origin_filename,
                'existing_record': existing_doc,
                'duplicate_type': 'exact',
                'duplicate': True
            }), 200
        elif existing_doc and existing_doc.get('is_deleted', False):
            # Document was previously deleted - allow re-upload
            logger.info(f"Re-uploading previously deleted document: {doc_id}")
            # Continue with normal processing to restore the document
        
        # Step 2: Upload to raw container
        doc_id, blob_url = storage_service.upload_to_raw(file_bytes, origin_filename)
        
        # Step 3: Process document (extract, thumbnails, manifest)
        processing_result = extraction_service.process_document(
            doc_id,
            file_bytes,
            origin_filename
        )
        
        # Step 4: Compute logical_id for logical duplicate detection - EPIC D.9
        full_text = processing_result['extraction_data'].get('full_text', '')
        logical_id = storage_service.compute_logical_id(full_text)
        
        # Check for logical duplicates (same content, different file)
        logical_duplicates = cosmos_service.find_by_logical_id(logical_id)
        
        version = 1
        superseded_doc_id = None
        
        if logical_duplicates:
            logger.info(f"Logical duplicate found for logical_id {logical_id}, {len(logical_duplicates)} match(es)")
            
            if not create_version:
                # Return prompt to user asking if they want to create a new version
                latest_version = cosmos_service.get_latest_version(logical_id)
                return jsonify({
                    'message': 'Logical duplicate detected - same content, different file',
                    'prompt': 'This document has the same content as an existing document. Create a new version?',
                    'doc_id': doc_id,
                    'logical_id': logical_id,
                    'existing_documents': logical_duplicates,
                    'latest_version': latest_version,
                    'duplicate_type': 'logical',
                    'duplicate': True,
                    'requires_user_decision': True,
                    'action_url': '/api/documents/upload?create_version=true'
                }), 409  # 409 Conflict - requires user decision
            else:
                # User confirmed version creation
                latest_version_doc = cosmos_service.get_latest_version(logical_id)
                if latest_version_doc:
                    version = latest_version_doc['version'] + 1
                    superseded_doc_id = latest_version_doc['doc_id']
                    
                    # Mark previous version as superseded
                    cosmos_service.mark_as_superseded(superseded_doc_id)
                    logger.info(f"Marked {superseded_doc_id} as superseded, creating version {version}")
        
        # Step 5: Generate document-level embedding for near-duplicate detection - EPIC D.10
        doc_embedding = embedding_service.embed_document(full_text)
        
        # Check for near-duplicates (high similarity but not exact logical match)
        near_duplicates = []
        all_docs = cosmos_service.query_documents(
            "SELECT c.doc_id, c.doc_embedding FROM c WHERE IS_DEFINED(c.doc_embedding) AND c.is_deleted = false"
        )
        
        for existing in all_docs:
            if existing.get('doc_id') == doc_id:
                continue  # Skip self
            
            existing_embedding = existing.get('doc_embedding')
            if existing_embedding and embedding_service.is_near_duplicate(doc_embedding, existing_embedding):
                near_duplicates.append(existing['doc_id'])
                
                # Store near-duplicate relation in lineage
                cosmos_service.save_lineage({
                    'source_doc_id': doc_id,
                    'target_doc_id': existing['doc_id'],
                    'relationship_type': 'near_duplicate',
                    'similarity_score': embedding_service.compute_cosine_similarity(doc_embedding, existing_embedding)
                })
        
        if near_duplicates:
            logger.info(f"Found {len(near_duplicates)} near-duplicate(s) for {doc_id}")
        
        # Step 6: Save document metadata to Cosmos
        doc_metadata = {
            'id': doc_id,
            'doc_id': doc_id,
            'logical_id': logical_id,
            'origin_filename': origin_filename,
            'source_uri': blob_url,
            'page_count': processing_result['manifest']['page_count'],
            'table_count': processing_result['manifest']['table_count'],
            'text_length': processing_result['manifest']['text_length'],
            'status': 'extracted',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'version': version,
            'is_deleted': False,
            'superseded': False,
            'doc_embedding': doc_embedding,
            'near_duplicates': near_duplicates
        }
        
        if superseded_doc_id:
            doc_metadata['supersedes'] = superseded_doc_id
        
        cosmos_service.save_document(doc_metadata)
        
        # Step 7: Log event
        cosmos_service.log_event(
            event_type='upload',
            doc_id=doc_id,
            details={
                'origin_filename': origin_filename,
                'page_count': processing_result['manifest']['page_count'],
                'file_size_bytes': len(file_bytes),
                'logical_id': logical_id,
                'version': version,
                'has_near_duplicates': len(near_duplicates) > 0,
                'near_duplicate_count': len(near_duplicates)
            }
        )
        
        # Step 8: Index document (chunk → embed → upload to search index)
        logger.info(f"Starting indexing for document {doc_id}")
        try:
            # Chunk the extracted text
            chunks = chunking_service.chunk_document(
                doc_id=doc_id,
                extraction_data=processing_result['extraction_data']
            )
            
            # Extract temporal metadata from filename
            from services.date_parser_service import DateParserService
            date_metadata = DateParserService.extract_date_metadata(origin_filename)
            logger.info(f"Extracted temporal metadata: document_date={date_metadata.get('document_date')}, fiscal_year={date_metadata.get('fiscal_year')}")
            
            # Enrich chunks with metadata
            for chunk in chunks:
                chunk["logical_id"] = logical_id
                chunk["version"] = version
                chunk["title"] = origin_filename
                chunk["origin_filename"] = origin_filename
                chunk["source_uri"] = blob_url
                chunk["observed_date"] = datetime.utcnow().isoformat() + 'Z'  # Add Z for UTC timezone
                chunk["kpi_tags"] = []  # Future enhancement
                # Add temporal metadata
                chunk["document_date"] = date_metadata.get("document_date")
                chunk["year"] = date_metadata.get("year")
                chunk["month"] = date_metadata.get("month")
                chunk["quarter"] = date_metadata.get("quarter")
                chunk["fiscal_year"] = date_metadata.get("fiscal_year")
            
            logger.info(f"Generated {len(chunks)} chunks for {doc_id}")
            
            # Embed chunks
            chunks_with_embeddings = embedding_service.embed_chunks(chunks)
            logger.info(f"Generated embeddings for {len(chunks_with_embeddings)} chunks")
            
            # Upload to search index
            upload_result = search_index_service.upload_chunks(chunks_with_embeddings)
            logger.info(f"Uploaded {upload_result['uploaded']} chunks to search index")
            
            # Update document status to indexed
            doc_metadata['status'] = 'indexed'
            doc_metadata['chunk_count'] = len(chunks)
            doc_metadata['indexed_chunk_count'] = upload_result['uploaded']
            doc_metadata['indexed_at'] = datetime.utcnow().isoformat()
            cosmos_service.save_document(doc_metadata)
            
            # Log indexing event
            cosmos_service.log_event(
                event_type='indexed',
                doc_id=doc_id,
                details={
                    'chunks_created': len(chunks),
                    'chunks_uploaded': upload_result['uploaded'],
                    'chunks_failed': upload_result.get('failed', 0)
                }
            )
            
        except Exception as index_error:
            logger.error(f"Indexing failed for {doc_id}: {index_error}", exc_info=True)
            # Update status to indicate indexing failure
            doc_metadata['status'] = 'extraction_complete_indexing_failed'
            doc_metadata['indexing_error'] = str(index_error)
            cosmos_service.save_document(doc_metadata)
            
            # Still return success for upload, but note indexing issue
            logger.warning(f"Document {doc_id} uploaded but indexing failed")
        
        logger.info(f"Successfully processed upload for {doc_id} (version {version})")
        
        response_data = {
            'message': 'Document uploaded and processed successfully',
            'doc_id': doc_id,
            'logical_id': logical_id,
            'origin_filename': origin_filename,
            'page_count': processing_result['manifest']['page_count'],
            'table_count': processing_result['manifest']['table_count'],
            'thumbnail_count': processing_result['manifest']['thumbnail_count'],
            'status': doc_metadata.get('status', 'extracted'),
            'version': version,
            'duplicate': False,
            'near_duplicates': near_duplicates,
            'near_duplicate_count': len(near_duplicates),
            'indexed': doc_metadata.get('status') == 'indexed',
            'chunk_count': doc_metadata.get('chunk_count', 0),
            'indexed_chunk_count': doc_metadata.get('indexed_chunk_count', 0)
        }
        
        if superseded_doc_id:
            response_data['supersedes'] = superseded_doc_id
        
        return jsonify(response_data), 201
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return jsonify({
            'error': 'Upload failed',
            'message': str(e)
        }), 500


@documents_bp.route('/', methods=['GET'])
def list_documents():
    """
    List all documents.
    
    Query params:
        - limit: Maximum number of documents to return (default 100)
    
    Returns:
        JSON array of document records or HTML partial for HTMX
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        documents = cosmos_service.list_documents(limit=limit)
        
        # Check if request is from HTMX
        if request.headers.get('HX-Request'):
            # Return HTML partial for HTMX
            return render_template('document_table_rows.html', documents=documents)
        
        # Return JSON for API calls
        return jsonify({
            'documents': documents,
            'count': len(documents)
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        if request.headers.get('HX-Request'):
            return render_template('document_table_rows.html', documents=[], error=str(e))
        return jsonify({
            'error': 'Failed to list documents',
            'message': str(e)
        }), 500


@documents_bp.route('/<doc_id>', methods=['GET'])
def get_document(doc_id):
    """
    Get document metadata by ID.
    
    Args:
        doc_id: Document identifier
    
    Returns:
        JSON document record
    """
    try:
        document = cosmos_service.get_document(doc_id)
        
        if not document:
            return jsonify({
                'error': 'Document not found',
                'doc_id': doc_id
            }), 404
        
        return jsonify(document), 200
        
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        return jsonify({
            'error': 'Failed to get document',
            'message': str(e)
        }), 500


@documents_bp.route('/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """
    Delete a document (EPIC E.14).
    
    Process:
    1. Delete chunks from AI Search index
    2. Mark Cosmos document as deleted
    3. Move blobs to archive container
    
    Args:
        doc_id: Document identifier
    
    Returns:
        JSON response with deletion summary
    """
    try:
        # Check if document exists
        document = cosmos_service.get_document(doc_id)
        if not document:
            return jsonify({
                'error': 'Document not found',
                'doc_id': doc_id
            }), 404
        
        # Check if already deleted
        if document.get('is_deleted', False):
            return jsonify({
                'message': 'Document already deleted',
                'doc_id': doc_id
            }), 200
        
        logger.info(f"Starting deletion process for document {doc_id}")
        
        # Step 1: Delete chunks from AI Search index
        deleted_chunks = 0
        try:
            deleted_chunks = search_index_service.delete_chunks_by_doc_id(doc_id)
            logger.info(f"Deleted {deleted_chunks} chunks from search index for {doc_id}")
        except Exception as e:
            logger.warning(f"Failed to delete chunks from search index: {e}")
            # Continue with deletion even if search fails
        
        # Step 2: Mark Cosmos document as deleted (soft delete)
        cosmos_service.mark_as_deleted(doc_id)
        logger.info(f"Marked document {doc_id} as deleted in Cosmos DB")
        
        # Step 3: Move blobs to archive
        archived = storage_service.archive_document_blobs(doc_id)
        logger.info(f"Archived blobs for document {doc_id}: {archived}")
        
        # Log deletion event
        cosmos_service.log_event(
            event_type='delete',
            doc_id=doc_id,
            details={
                'origin_filename': document.get('origin_filename', ''),
                'deleted_chunks': deleted_chunks,
                'archived': archived
            }
        )
        
        logger.info(f"Successfully deleted document {doc_id}")
        
        # Return success with redirect instruction for HTMX
        response = jsonify({
            'message': 'Document deleted successfully',
            'doc_id': doc_id,
            'deleted_chunks': deleted_chunks,
            'archived': archived
        })
        response.headers['HX-Redirect'] = '/documents'
        return response, 200
        
    except Exception as e:
        logger.error(f"Failed to delete document {doc_id}: {e}")
        return jsonify({
            'error': 'Failed to delete document',
            'message': str(e),
            'doc_id': doc_id
        }), 500


# ============================================================================
# UI Routes (EPIC E.11, E.12, E.13)
# ============================================================================

@documents_bp.route('/ui', methods=['GET'])
@documents_bp.route('/ui/', methods=['GET'])
def ui_list_documents():
    """
    Render document list UI (EPIC E.11).
    """
    return render_template('document_list.html')


@documents_bp.route('/ui/upload', methods=['GET'])
def ui_upload_form():
    """
    Render upload form UI (EPIC E.12).
    """
    return render_template('upload.html')


@documents_bp.route('/ui/<doc_id>', methods=['GET'])
def ui_document_detail(doc_id):
    """
    Render document detail UI (EPIC E.13).
    """
    try:
        document = cosmos_service.get_document(doc_id)
        
        if not document:
            return render_template('error.html', 
                error='Document not found',
                doc_id=doc_id
            ), 404
        
        return render_template('document_detail.html', document=document)
        
    except Exception as e:
        logger.error(f"Failed to render document detail: {e}")
        return render_template('error.html',
            error='Failed to load document',
            message=str(e)
        ), 500


@documents_bp.route('/<doc_id>/thumbnail/<int:page_no>', methods=['GET'])
def get_thumbnail(doc_id, page_no):
    """
    Get thumbnail for a specific page.
    Returns SAS URL to the thumbnail blob.
    """
    try:
        from flask import redirect
        
        # Generate thumbnail blob name
        thumb_blob = f"{doc_id}/p{page_no}.png"
        
        # Check if thumbnail exists
        if not storage_service.blob_exists(storage_service.blob_service_client.get_container_client('thumbs').container_name, thumb_blob):
            return jsonify({
                'error': 'Thumbnail not found',
                'doc_id': doc_id,
                'page_no': page_no
            }), 404
        
        # Generate SAS URL
        sas_url = storage_service.generate_sas_url('thumbs', thumb_blob, expiry_hours=1)
        
        # Redirect to SAS URL
        return redirect(sas_url)
        
    except Exception as e:
        logger.error(f"Failed to get thumbnail: {e}")
        return jsonify({
            'error': 'Failed to get thumbnail',
            'message': str(e)
        }), 500


@documents_bp.route('/<doc_id>/reindex', methods=['POST'])
def reindex_document(doc_id):
    """
    Reindex a document (EPIC E.13).
    Triggers re-chunking and re-indexing of the document.
    """
    try:
        # Get document
        document = cosmos_service.get_document(doc_id)
        if not document:
            return jsonify({
                'error': 'Document not found',
                'doc_id': doc_id
            }), 404
        
        logger.info(f"Starting reindex for document {doc_id}")
        
        # Step 1: Delete existing chunks from search index
        deleted_chunks = search_index_service.delete_chunks_by_doc_id(doc_id)
        logger.info(f"Deleted {deleted_chunks} existing chunks for {doc_id}")
        
        # Step 2: Import chunking service
        from services.chunking_service import ChunkingService
        
        chunking_service = ChunkingService()
        
        # Step 3: Download extracted JSON
        extracted_blob = f"{doc_id}.json"
        extraction_data = storage_service.download_json('extracted', extracted_blob)
        
        # Step 4: Re-chunk the document
        chunks = chunking_service.chunk_document(
            doc_id=doc_id,
            extraction_data=extraction_data
        )
        
        # Extract temporal metadata from filename
        from services.date_parser_service import DateParserService
        origin_filename = document.get('origin_filename', '')
        date_metadata = DateParserService.extract_date_metadata(origin_filename)
        logger.info(f"Extracted temporal metadata for reindex: document_date={date_metadata.get('document_date')}, fiscal_year={date_metadata.get('fiscal_year')}")
        
        # Enrich chunks with metadata including temporal fields
        for chunk in chunks:
            chunk["logical_id"] = document.get('logical_id', doc_id)
            chunk["version"] = document.get('version', 1)
            chunk["source_uri"] = document.get('source_uri', '')
            chunk["title"] = document.get('origin_filename', '')
            chunk["origin_filename"] = document.get('origin_filename', '')
            chunk["observed_date"] = document.get('observed_date', datetime.utcnow().isoformat() + 'Z')
            chunk["kpi_tags"] = document.get('kpi_tags', [])
            # Add temporal metadata
            chunk["document_date"] = date_metadata.get("document_date")
            chunk["year"] = date_metadata.get("year")
            chunk["month"] = date_metadata.get("month")
            chunk["quarter"] = date_metadata.get("quarter")
            chunk["fiscal_year"] = date_metadata.get("fiscal_year")
        
        logger.info(f"Generated {len(chunks)} chunks for {doc_id}")
        
        # Step 5: Embed and index chunks
        chunks_with_embeddings = embedding_service.embed_chunks(chunks)
        result = search_index_service.upload_chunks(chunks_with_embeddings)
        
        # Log reindex event
        cosmos_service.log_event(
            event_type='reindex',
            doc_id=doc_id,
            details={
                'deleted_chunks': deleted_chunks,
                'new_chunks': result.get('uploaded', 0),
                'failed_chunks': result.get('failed', 0)
            }
        )
        
        logger.info(f"Successfully reindexed document {doc_id}")
        
        return jsonify({
            'message': 'Document reindexed successfully',
            'doc_id': doc_id,
            'deleted_chunks': deleted_chunks,
            'new_chunks': result.get('uploaded', 0),
            'failed_chunks': result.get('failed', 0)
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to reindex document {doc_id}: {e}")
        return jsonify({
            'error': 'Failed to reindex document',
            'message': str(e),
            'doc_id': doc_id
        }), 500


@documents_bp.route('/search', methods=['GET', 'POST'])
def search_documents():
    """
    Search endpoint implementing hybrid BM25 + vector retrieval with citations.
    
    EPIC F.15 - Search API
    
    Query params (GET) or JSON body (POST):
        - q or query: Search query text (required)
        - top: Number of results (default 10, max 100)
        - filter: OData filter expression (optional)
        - include_thumbnails: Whether to include thumbnail URLs (default true)
    
    Returns:
        JSON response with search results and citations
    """
    try:
        # Get parameters from query string, form data, or JSON body
        if request.method == 'POST':
            # Check if it's JSON or form data
            if request.is_json:
                data = request.get_json() or {}
                query = data.get('query') or data.get('q')
                top = data.get('top', 10)
                filter_expr = data.get('filter')
                include_thumbnails = data.get('include_thumbnails', True)
            else:
                # Form data (from HTMX or regular form submission)
                query = request.form.get('query') or request.form.get('q')
                top = int(request.form.get('top', 10))
                filter_expr = request.form.get('filter')
                include_thumbnails = request.form.get('include_thumbnails', 'true').lower() == 'true'
        else:
            query = request.args.get('q') or request.args.get('query')
            top = int(request.args.get('top', 10))
            filter_expr = request.args.get('filter')
            include_thumbnails = request.args.get('include_thumbnails', 'true').lower() == 'true'
        
        # Validate query
        if not query:
            return jsonify({
                'error': 'Missing query parameter',
                'message': 'Please provide a search query using "q" or "query" parameter'
            }), 400
        
        # Limit top to reasonable max
        top = min(max(1, top), 100)
        
        logger.info(f"Search request: query='{query}', top={top}, filter={filter_expr}")
        
        # Execute search
        result = search_service.search(
            query=query,
            top=top,
            filter_expr=filter_expr,
            include_thumbnails=include_thumbnails
        )
        
        # Log search event
        cosmos_service.log_event(
            event_type='search',
            doc_id=None,
            details={
                'query': query,
                'result_count': result['count'],
                'top': top,
                'filter': filter_expr
            }
        )
        
        logger.info(f"Search completed: {result['count']} results for query '{query}'")
        
        # Return HTML for HTMX requests, JSON for API calls
        if request.headers.get('HX-Request'):
            # HTMX request - return HTML fragment
            return render_template('search_results.html', 
                                   query=result['query'],
                                   count=result['count'],
                                   results=result['results'],
                                   error=None,
                                   message=None)
        else:
            # Regular API request - return JSON
            return jsonify(result), 200
        
    except ValueError as e:
        logger.error(f"Invalid search parameters: {e}")
        
        if request.headers.get('HX-Request'):
            return render_template('search_results.html',
                                   error='Invalid parameters',
                                   message=str(e),
                                   query='',
                                   count=0,
                                   results=[])
        else:
            return jsonify({
                'error': 'Invalid parameters',
                'message': str(e)
            }), 400
            
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        
        if request.headers.get('HX-Request'):
            return render_template('search_results.html',
                                   error='Search failed',
                                   message=str(e),
                                   query='',
                                   count=0,
                                   results=[])
        else:
            return jsonify({
                'error': 'Search failed',
                'message': str(e)
            }), 500


@documents_bp.route('/search/chunk/<chunk_id>', methods=['GET'])
def get_chunk_detail(chunk_id):
    """
    Get details for a specific chunk by ID.
    
    Args:
        chunk_id: Unique chunk identifier
    
    Returns:
        JSON response with chunk details
    """
    try:
        logger.info(f"Retrieving chunk: {chunk_id}")
        
        chunk = search_service.get_chunk_by_id(chunk_id)
        
        if not chunk:
            return jsonify({
                'error': 'Chunk not found',
                'message': f'No chunk found with ID: {chunk_id}'
            }), 404
        
        return jsonify(chunk), 200
        
    except Exception as e:
        logger.error(f"Failed to retrieve chunk {chunk_id}: {e}")
        return jsonify({
            'error': 'Failed to retrieve chunk',
            'message': str(e)
        }), 500


@documents_bp.route('/search/document/<doc_id>', methods=['GET'])
def search_within_document(doc_id):
    """
    Search within a specific document.
    
    Args:
        doc_id: Document identifier
    
    Query params:
        - q or query: Search query (optional - if not provided, returns all chunks)
        - top: Number of results (default 100)
    
    Returns:
        JSON response with chunks from the specified document
    """
    try:
        query = request.args.get('q') or request.args.get('query')
        top = int(request.args.get('top', 100))
        
        logger.info(f"Search within document {doc_id}: query='{query}', top={top}")
        
        chunks = search_service.search_by_document(
            doc_id=doc_id,
            query=query,
            top=top
        )
        
        return jsonify({
            'doc_id': doc_id,
            'query': query,
            'count': len(chunks),
            'chunks': chunks
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to search within document {doc_id}: {e}")
        return jsonify({
            'error': 'Search failed',
            'message': str(e)
        }), 500


@documents_bp.route('/ui/search', methods=['GET'])
def search_ui():
    """
    Render the search UI page.
    
    EPIC F.16 - Search UI with citations
    """
    return render_template('search.html')


# =============================================================================
# EPIC G - RAG Chat Endpoints
# =============================================================================

@documents_bp.route('/chat', methods=['POST'])
def chat():
    """
    RAG-powered chat endpoint using GPT-4o-mini.
    
    Implements Microsoft RAG best practices:
    - Grounding with hybrid search results
    - Inline citations
    - Prompt engineering with few-shot examples
    
    Expected JSON body:
    {
        "query": "What are the key performance indicators?",
        "conversation_history": [  // Optional
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ],
        "top_k": 5,  // Optional, default 5
        "temperature": 0.3  // Optional, default 0.3
    }
    
    Returns:
        JSON response with generated answer, sources, and metadata
    """
    try:
        # Parse request (support both JSON and form data)
        if request.is_json:
            data = request.get_json()
        else:
            # Form data from HTMX
            data = {
                'query': request.form.get('query'),
                'conversation_history': json.loads(request.form.get('conversation_history', '[]')),
                'top_k': int(request.form.get('top_k', 5)),
                'temperature': float(request.form.get('temperature', 0.3)),
                'max_tokens': int(request.form.get('max_tokens', 1000))
            }
        
        query = data.get('query')
        
        if not query:
            return jsonify({
                'error': 'Missing required field',
                'message': 'Please provide a query'
            }), 400
        
        # Optional parameters
        conversation_history = data.get('conversation_history', [])
        top_k = data.get('top_k', 5)
        temperature = data.get('temperature', 0.3)
        max_tokens = data.get('max_tokens', 1000)
        
        logger.info(f"Chat request: '{query[:100]}...' (top_k={top_k})")
        
        # Call chat service
        result = chat_service.chat(
            query=query,
            conversation_history=conversation_history,
            top_k=top_k,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Log event to Cosmos
        try:
            cosmos_service.log_event(
                doc_id='chat_system',  # System-level event
                event_type='chat_query',
                details={
                    'query': query[:200],  # Truncate for storage
                    'sources_count': len(result['sources']),
                    'tokens_used': result['usage']['total_tokens']
                }
            )
        except Exception as log_error:
            logger.warning(f"Failed to log chat event: {log_error}")
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Chat failed: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Chat processing failed',
            'message': str(e)
        }), 500


@documents_bp.route('/ui/chat', methods=['GET'])
def chat_ui():
    """
    Render the RAG chat UI page.
    
    EPIC G - Interactive chat interface with inline citations
    """
    return render_template('chat.html')

