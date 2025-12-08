"""
Cosmos DB service for document metadata and event persistence.
"""
import logging
import re
import uuid
from datetime import datetime
from azure.cosmos.exceptions import CosmosResourceExistsError, CosmosResourceNotFoundError
from werkzeug.security import generate_password_hash, check_password_hash
from config import (
    get_cosmos_container,
    COSMOS_COLL_DOCUMENTS,
    COSMOS_COLL_EVENTS,
    COSMOS_COLL_LINEAGE,
    COSMOS_COLL_USERS,
    COSMOS_COLL_QUERIES
)

logger = logging.getLogger(__name__)


def validate_password(password):
    """
    Validate password meets requirements.
    
    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    
    Args:
        password: Password string to validate
        
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    return True, None


class CosmosService:
    """Service for managing Cosmos DB operations."""
    
    def __init__(self):
        self.documents_container = get_cosmos_container(COSMOS_COLL_DOCUMENTS)
        self.events_container = get_cosmos_container(COSMOS_COLL_EVENTS)
        self.lineage_container = get_cosmos_container(COSMOS_COLL_LINEAGE)
        self.users_container = get_cosmos_container(COSMOS_COLL_USERS)
        self.queries_container = get_cosmos_container(COSMOS_COLL_QUERIES)
    
    # ==================== USER MANAGEMENT ====================
    
    def create_user(self, username, password, is_admin=False, created_by=None):
        """
        Create a new user in Cosmos DB.
        
        Args:
            username: Unique username
            password: Plain text password (will be hashed)
            is_admin: Whether user has admin privileges
            created_by: Username of creator (optional)
            
        Returns:
            dict: Created user record (without password_hash)
            
        Raises:
            ValueError: If username exists or password invalid
        """
        # Check if username already exists
        existing = self.get_user_by_username(username)
        if existing:
            raise ValueError(f"Username '{username}' already exists")
        
        # Validate password
        is_valid, error = validate_password(password)
        if not is_valid:
            raise ValueError(error)
        
        user_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        user_data = {
            'id': user_id,
            'username': username.lower().strip(),
            'password_hash': generate_password_hash(password),
            'is_admin': is_admin,
            'is_active': True,
            'created_at': now,
            'created_by': created_by,
            'updated_at': now
        }
        
        try:
            self.users_container.create_item(user_data)
            logger.info(f"Created user '{username}' (admin={is_admin})")
            
            # Return user without password hash
            return {k: v for k, v in user_data.items() if k != 'password_hash'}
            
        except Exception as e:
            logger.error(f"Failed to create user '{username}': {e}")
            raise
    
    def get_user_by_username(self, username):
        """
        Get user by username.
        
        Args:
            username: Username to lookup
            
        Returns:
            dict: User record or None
        """
        try:
            query = "SELECT * FROM c WHERE c.username = @username"
            parameters = [{"name": "@username", "value": username.lower().strip()}]
            items = list(self.users_container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            return items[0] if items else None
        except Exception as e:
            logger.error(f"Failed to get user '{username}': {e}")
            return None
    
    def get_user_by_id(self, user_id):
        """
        Get user by ID.
        
        Args:
            user_id: User identifier
            
        Returns:
            dict: User record or None
        """
        try:
            return self.users_container.read_item(item=user_id, partition_key=user_id)
        except CosmosResourceNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Failed to get user by id '{user_id}': {e}")
            return None
    
    def verify_user(self, username, password):
        """
        Verify username and password.
        
        Args:
            username: Username
            password: Plain text password
            
        Returns:
            dict: User record (without password_hash) if valid, None otherwise
        """
        user = self.get_user_by_username(username)
        if not user:
            return None
        
        if not user.get('is_active', True):
            logger.warning(f"Login attempt for inactive user '{username}'")
            return None
        
        if check_password_hash(user['password_hash'], password):
            logger.info(f"Successful login for user '{username}'")
            return {k: v for k, v in user.items() if k != 'password_hash'}
        
        logger.warning(f"Failed login attempt for user '{username}'")
        return None
    
    def list_users(self):
        """
        List all users (excluding password hashes).
        
        Returns:
            list: User records
        """
        try:
            query = """
                SELECT c.id, c.username, c.is_admin, c.is_active, 
                       c.created_at, c.created_by, c.updated_at
                FROM c
                ORDER BY c.created_at DESC
            """
            items = list(self.users_container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            return items
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return []
    
    def update_user(self, user_id, updates, updated_by=None):
        """
        Update user fields (not password).
        
        Args:
            user_id: User identifier
            updates: Dict of fields to update (is_admin, is_active)
            updated_by: Username making the update
            
        Returns:
            dict: Updated user record
        """
        try:
            user = self.users_container.read_item(item=user_id, partition_key=user_id)
            
            # Only allow updating certain fields
            allowed_fields = ['is_admin', 'is_active']
            for field in allowed_fields:
                if field in updates:
                    user[field] = updates[field]
            
            user['updated_at'] = datetime.utcnow().isoformat()
            if updated_by:
                user['updated_by'] = updated_by
            
            self.users_container.upsert_item(user)
            logger.info(f"Updated user '{user['username']}': {updates}")
            
            return {k: v for k, v in user.items() if k != 'password_hash'}
            
        except CosmosResourceNotFoundError:
            logger.warning(f"User {user_id} not found for update")
            return None
        except Exception as e:
            logger.error(f"Failed to update user {user_id}: {e}")
            raise
    
    def reset_password(self, user_id, new_password, reset_by=None):
        """
        Reset user password.
        
        Args:
            user_id: User identifier
            new_password: New plain text password
            reset_by: Username performing reset
            
        Returns:
            bool: True if successful
            
        Raises:
            ValueError: If password invalid
        """
        # Validate new password
        is_valid, error = validate_password(new_password)
        if not is_valid:
            raise ValueError(error)
        
        try:
            user = self.users_container.read_item(item=user_id, partition_key=user_id)
            user['password_hash'] = generate_password_hash(new_password)
            user['updated_at'] = datetime.utcnow().isoformat()
            if reset_by:
                user['password_reset_by'] = reset_by
                user['password_reset_at'] = datetime.utcnow().isoformat()
            
            self.users_container.upsert_item(user)
            logger.info(f"Password reset for user '{user['username']}' by {reset_by}")
            return True
            
        except CosmosResourceNotFoundError:
            logger.warning(f"User {user_id} not found for password reset")
            return False
        except Exception as e:
            logger.error(f"Failed to reset password for user {user_id}: {e}")
            raise
    
    def deactivate_user(self, user_id, deactivated_by=None):
        """
        Deactivate a user (soft delete).
        
        Args:
            user_id: User identifier
            deactivated_by: Username performing deactivation
            
        Returns:
            dict: Updated user record or None
        """
        return self.update_user(user_id, {'is_active': False}, updated_by=deactivated_by)
    
    def activate_user(self, user_id, activated_by=None):
        """
        Reactivate a user.
        
        Args:
            user_id: User identifier
            activated_by: Username performing activation
            
        Returns:
            dict: Updated user record or None
        """
        return self.update_user(user_id, {'is_active': True}, updated_by=activated_by)
    
    def user_exists(self, username):
        """Check if username exists."""
        return self.get_user_by_username(username) is not None
    
    # ==================== QUERY HISTORY MANAGEMENT ====================
    
    def save_query(self, user_id, username, query, response, sources=None, 
                   tokens_used=None, conversation_id=None):
        """
        Save a chat query to Cosmos DB for user history.
        
        Args:
            user_id: User identifier from session
            username: Username from session
            query: The user's question
            response: The AI-generated response
            sources: List of source documents used (optional)
            tokens_used: Token usage statistics (optional)
            conversation_id: Conversation session identifier (optional)
            
        Returns:
            dict: Saved query record
        """
        try:
            query_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            
            # Simplify sources to avoid storing large embeddings
            simplified_sources = []
            if sources:
                for src in sources[:10]:  # Limit to first 10 sources
                    simplified_sources.append({
                        'doc_id': src.get('doc_id'),
                        'chunk_id': src.get('chunk_id'),
                        'title': src.get('title'),
                        'page_no': src.get('page_no'),
                        'score': src.get('score')
                    })
            
            query_data = {
                'id': query_id,
                'user_id': user_id,
                'username': username,
                'query': query,
                'response': response,
                'sources': simplified_sources,
                'sources_count': len(simplified_sources),
                'tokens_used': tokens_used,
                'conversation_id': conversation_id,
                'created_at': now
            }
            
            result = self.queries_container.create_item(query_data)
            logger.info(f"Saved query {query_id} for user {username}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to save query for user {username}: {e}")
            raise
    
    def get_user_queries(self, user_id, limit=50):
        """
        Get query history for a specific user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of queries to return (default 50)
            
        Returns:
            list: Query records ordered by most recent first
        """
        try:
            query = f"""
                SELECT TOP {limit} c.id, c.query, c.response, c.sources_count, 
                       c.tokens_used, c.created_at, c.conversation_id
                FROM c 
                WHERE c.user_id = @user_id
                ORDER BY c.created_at DESC
            """
            parameters = [{"name": "@user_id", "value": user_id}]
            
            items = list(self.queries_container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            return items
        except Exception as e:
            logger.error(f"Failed to get queries for user {user_id}: {e}")
            return []
    
    def get_query_by_id(self, query_id):
        """
        Get a specific query by ID.
        
        Args:
            query_id: Query identifier
            
        Returns:
            dict: Query record or None
        """
        try:
            return self.queries_container.read_item(item=query_id, partition_key=query_id)
        except CosmosResourceNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Failed to get query {query_id}: {e}")
            return None
    
    # ==================== DOCUMENT MANAGEMENT ====================
    
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
