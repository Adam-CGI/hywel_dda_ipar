"""
Cosmos DB service for document metadata and event persistence.
"""
import logging
from datetime import datetime
from azure.cosmos.exceptions import CosmosResourceExistsError, CosmosResourceNotFoundError
from app.config import (
    get_cosmos_container,
    COSMOS_COLL_DOCUMENTS,
    COSMOS_COLL_EVENTS,
    COSMOS_COLL_LINEAGE
)

logger = logging.getLogger(__name__)


class CosmosService:
    """Service for managing Cosmos DB operations."""
    
    def __init__(self):
        self.documents_container = get_cosmos_container(COSMOS_COLL_DOCUMENTS)
        self.events_container = get_cosmos_container(COSMOS_COLL_EVENTS)
        self.lineage_container = get_cosmos_container(COSMOS_COLL_LINEAGE)
    
    def save_document(self, doc_data):
        """
        Save document metadata to Cosmos DB.
        
        Args:
            doc_data: Dictionary containing document metadata
            
        Returns:
            dict: Saved document record
        """
        try:
            # Ensure required fields
            if 'id' not in doc_data:
                raise ValueError("Document must have 'id' field")
            
            # Add timestamp if not present
            if 'created_at' not in doc_data:
                doc_data['created_at'] = datetime.utcnow().isoformat()
            
            doc_data['updated_at'] = datetime.utcnow().isoformat()
            
            result = self.documents_container.upsert_item(doc_data)
            logger.info(f"Saved document {doc_data['id']} to Cosmos DB")
            return result
            
        except CosmosResourceExistsError:
            logger.warning(f"Document {doc_data['id']} already exists")
            raise
        except Exception as e:
            logger.error(f"Failed to save document: {e}")
            raise
    
    def create_document(self, doc_data):
        """Alias for save_document to match expected interface."""
        return self.save_document(doc_data)
    
    def update_document(self, doc_data):
        """Update existing document (upsert)."""
        return self.save_document(doc_data)
    
    def get_document(self, doc_id):
        """
        Retrieve document by ID.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            dict: Document record or None
        """
        try:
            return self.documents_container.read_item(
                item=doc_id,
                partition_key=doc_id
            )
        except CosmosResourceNotFoundError:
            logger.warning(f"Document {doc_id} not found")
            return None
        except Exception as e:
            logger.error(f"Failed to get document: {e}")
            raise
    
    def document_exists(self, doc_id):
        """Check if document exists in Cosmos DB."""
        return self.get_document(doc_id) is not None
    
    def log_event(self, event_type, doc_id, details=None, user_id=None):
        """
        Log an event to Cosmos DB.
        
        Args:
            event_type: Type of event (e.g., 'upload', 'extract', 'delete')
            doc_id: Document identifier
            details: Optional dictionary with event details
            user_id: Optional user identifier
            
        Returns:
            dict: Event record
        """
        try:
            import uuid
            event_id = str(uuid.uuid4())
            
            event_data = {
                'id': event_id,
                'event_type': event_type,
                'doc_id': doc_id,
                'timestamp': datetime.utcnow().isoformat(),
                'user_id': user_id,
                'details': details or {}
            }
            
            result = self.events_container.create_item(event_data)
            logger.info(f"Logged event {event_type} for document {doc_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to log event: {e}")
            raise
    
    def create_event(self, event_data):
        """
        Create event from event data dictionary.
        
        Args:
            event_data: Event dictionary with event_type, doc_id, timestamp, etc.
            
        Returns:
            dict: Event record
        """
        try:
            import uuid
            if 'id' not in event_data:
                event_data['id'] = str(uuid.uuid4())
            
            if 'timestamp' not in event_data:
                event_data['timestamp'] = datetime.utcnow().isoformat()
            
            result = self.events_container.create_item(event_data)
            logger.info(f"Created event {event_data.get('event_type', 'unknown')}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            raise
    
    def save_lineage(self, lineage_data):
        """
        Save lineage relationship to Cosmos DB.
        
        Args:
            lineage_data: Dictionary containing lineage relationship
            
        Returns:
            dict: Lineage record
        """
        try:
            import uuid
            if 'id' not in lineage_data:
                lineage_data['id'] = str(uuid.uuid4())
            
            lineage_data['created_at'] = datetime.utcnow().isoformat()
            
            result = self.lineage_container.create_item(lineage_data)
            logger.info(f"Saved lineage record {lineage_data['id']}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to save lineage: {e}")
            raise
    
    def query_documents(self, query, parameters=None):
        """
        Execute a query against documents container.
        
        Args:
            query: SQL query string
            parameters: Optional query parameters
            
        Returns:
            list: Query results
        """
        try:
            items = list(self.documents_container.query_items(
                query=query,
                parameters=parameters or [],
                enable_cross_partition_query=True
            ))
            return items
        except Exception as e:
            logger.error(f"Failed to query documents: {e}")
            raise
    
    def list_documents(self, limit=100, include_deleted=False):
        """
        List all documents with optimized query.
        
        Args:
            limit: Maximum number of documents to return
            include_deleted: Whether to include deleted documents (default False)
            
        Returns:
            list: Document records
        """
        try:
            # Optimized query: only select needed fields, exclude deleted by default
            if include_deleted:
                query = f"""
                    SELECT TOP {limit} c.id, c.doc_id, c.logical_id, c.origin_filename, 
                           c.version, c.page_count, c.created_at, c.updated_at, 
                           c.is_deleted, c.superseded, c.source_uri
                    FROM c 
                    ORDER BY c.created_at DESC
                """
            else:
                query = f"""
                    SELECT TOP {limit} c.id, c.doc_id, c.logical_id, c.origin_filename, 
                           c.version, c.page_count, c.created_at, c.updated_at, 
                           c.is_deleted, c.superseded, c.source_uri
                    FROM c 
                    WHERE (NOT IS_DEFINED(c.is_deleted) OR c.is_deleted = false)
                    ORDER BY c.created_at DESC
                """
            
            logger.info(f"Listing documents with limit={limit}, include_deleted={include_deleted}")
            results = self.query_documents(query)
            logger.info(f"Retrieved {len(results)} documents from Cosmos DB")
            return results
        except Exception as e:
            logger.error(f"Failed to list documents: {e}", exc_info=True)
            # Return empty list instead of raising to prevent total failure
            return []
    
    def find_by_logical_id(self, logical_id):
        """
        Find documents by logical_id (normalized content hash).
        
        Args:
            logical_id: Logical identifier (hash of normalized text)
            
        Returns:
            list: Documents with matching logical_id
        """
        try:
            query = "SELECT * FROM c WHERE c.logical_id = @logical_id AND c.is_deleted = false"
            parameters = [{"name": "@logical_id", "value": logical_id}]
            return self.query_documents(query, parameters)
        except Exception as e:
            logger.error(f"Failed to find documents by logical_id: {e}")
            raise
    
    def get_latest_version(self, logical_id):
        """
        Get the latest version of a document by logical_id.
        
        Args:
            logical_id: Logical identifier
            
        Returns:
            dict: Latest version document or None
        """
        try:
            query = """
                SELECT * FROM c 
                WHERE c.logical_id = @logical_id 
                AND c.is_deleted = false 
                AND (NOT IS_DEFINED(c.superseded) OR c.superseded = false)
                ORDER BY c.version DESC
            """
            parameters = [{"name": "@logical_id", "value": logical_id}]
            results = self.query_documents(query, parameters)
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Failed to get latest version: {e}")
            raise
    
    def mark_as_superseded(self, doc_id):
        """
        Mark a document as superseded by a newer version.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            dict: Updated document
        """
        try:
            doc = self.get_document(doc_id)
            if doc:
                doc['superseded'] = True
                doc['updated_at'] = datetime.utcnow().isoformat()
                return self.save_document(doc)
            else:
                logger.warning(f"Document {doc_id} not found for superseding")
                return None
        except Exception as e:
            logger.error(f"Failed to mark document as superseded: {e}")
            raise
    
    def mark_as_deleted(self, doc_id):
        """
        Mark a document as deleted (soft delete).
        
        Args:
            doc_id: Document identifier
            
        Returns:
            dict: Updated document
        """
        try:
            doc = self.get_document(doc_id)
            if doc:
                doc['is_deleted'] = True
                doc['deleted_at'] = datetime.utcnow().isoformat()
                doc['updated_at'] = datetime.utcnow().isoformat()
                return self.save_document(doc)
            else:
                logger.warning(f"Document {doc_id} not found for deletion")
                return None
        except Exception as e:
            logger.error(f"Failed to mark document as deleted: {e}")
            raise
