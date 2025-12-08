"""
Storage service for handling blob operations.
"""
import hashlib
import logging
from datetime import datetime, timedelta
from azure.storage.blob import BlobSasPermissions, generate_blob_sas, ContentSettings
from config import (
    get_blob_service_client,
    CONTAINER_RAW,
    CONTAINER_EXTRACTED,
    CONTAINER_THUMBS,
    CONTAINER_MANIFESTS,
    CONTAINER_ARCHIVE,
    AZURE_STORAGE_ACCOUNT
)

logger = logging.getLogger(__name__)


class StorageService:
    """Service for managing Azure Blob Storage operations."""
    
    def __init__(self):
        self.blob_service_client = get_blob_service_client()
    
    @staticmethod
    def compute_sha256(file_bytes):
        """Compute SHA256 hash of file bytes."""
        return hashlib.sha256(file_bytes).hexdigest()
    
    @staticmethod
    def compute_logical_id(text):
        """
        Compute logical_id from normalized text.
        Used for logical duplicate detection (same content, different file).
        
        Args:
            text: Extracted text content
            
        Returns:
            str: SHA256 hash of normalized text
        """
        import re
        
        # Normalize text for logical comparison
        # Remove extra whitespace, convert to lowercase
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        
        # Compute hash of normalized text
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    
    def upload_to_raw(self, file_bytes, filename):
        """
        Upload document to raw container.
        
        Args:
            file_bytes: Document file content as bytes
            filename: Original filename
            
        Returns:
            tuple: (doc_id, blob_url)
        """
        import os
        
        doc_id = self.compute_sha256(file_bytes)
        # Preserve original file extension
        ext = os.path.splitext(filename.lower())[1] or '.pdf'
        blob_name = f"{doc_id}{ext}"
        
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=CONTAINER_RAW,
                blob=blob_name
            )
            
            # Check if blob already exists
            if blob_client.exists():
                logger.info(f"Document {doc_id} already exists in raw container")
                return doc_id, blob_client.url
            
            # Upload with metadata
            metadata = {
                "origin_filename": filename,
                "file_extension": ext,
                "upload_timestamp": datetime.utcnow().isoformat(),
                "doc_id": doc_id
            }
            
            blob_client.upload_blob(
                data=file_bytes,
                metadata=metadata,
                overwrite=False
            )
            
            logger.info(f"Uploaded document {doc_id} to raw container")
            return doc_id, blob_client.url
            
        except Exception as e:
            logger.error(f"Failed to upload to raw container: {e}")
            raise
    
    def upload_json(self, container_name, blob_name, json_data):
        """
        Upload JSON data to specified container.
        
        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            json_data: JSON string or dict
        """
        try:
            import json
            if isinstance(json_data, dict):
                json_data = json.dumps(json_data, indent=2)
            
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            
            blob_client.upload_blob(
                data=json_data,
                overwrite=True,
                content_settings=ContentSettings(content_type='application/json')
            )
            
            logger.info(f"Uploaded JSON to {container_name}/{blob_name}")
            return blob_client.url
            
        except Exception as e:
            logger.error(f"Failed to upload JSON: {e}")
            raise
    
    def upload_image(self, container_name, blob_name, image_bytes):
        """
        Upload image to specified container.
        
        Args:
            container_name: Name of the container
            blob_name: Name of the blob (e.g., "doc_id/p1.png")
            image_bytes: Image content as bytes
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            
            blob_client.upload_blob(
                data=image_bytes,
                overwrite=True,
                content_settings=ContentSettings(content_type='image/png')
            )
            
            logger.info(f"Uploaded image to {container_name}/{blob_name}")
            return blob_client.url
            
        except Exception as e:
            logger.error(f"Failed to upload image: {e}")
            raise
    
    def get_blob(self, container_name, blob_name):
        """Download blob content as bytes."""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            return blob_client.download_blob().readall()
        except Exception as e:
            logger.error(f"Failed to download blob: {e}")
            raise
    
    def download_json(self, container_name, blob_name):
        """
        Download and parse JSON blob.
        
        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            
        Returns:
            dict: Parsed JSON data
        """
        try:
            import json
            blob_bytes = self.get_blob(container_name, blob_name)
            json_data = json.loads(blob_bytes.decode('utf-8'))
            logger.info(f"Downloaded JSON from {container_name}/{blob_name}")
            return json_data
        except Exception as e:
            logger.error(f"Failed to download JSON: {e}")
            raise
    
    def generate_sas_url(self, container_name, blob_name, expiry_hours=1):
        """
        Generate SAS URL for blob access.
        
        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            expiry_hours: Hours until SAS expires (default 1)
            
        Returns:
            str: SAS URL
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            
            # Get account key from connection string
            account_key = self.blob_service_client.credential.account_key
            
            sas_token = generate_blob_sas(
                account_name=AZURE_STORAGE_ACCOUNT,
                container_name=container_name,
                blob_name=blob_name,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
            )
            
            return f"{blob_client.url}?{sas_token}"
            
        except Exception as e:
            logger.error(f"Failed to generate SAS URL: {e}")
            raise
    
    def blob_exists(self, container_name, blob_name):
        """Check if blob exists in container."""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            return blob_client.exists()
        except Exception as e:
            logger.error(f"Failed to check blob existence: {e}")
            return False
    
    def copy_blob(self, source_container, source_blob, dest_container, dest_blob):
        """
        Copy blob from source to destination.
        
        Args:
            source_container: Source container name
            source_blob: Source blob name
            dest_container: Destination container name
            dest_blob: Destination blob name
            
        Returns:
            str: Destination blob URL
        """
        try:
            source_blob_client = self.blob_service_client.get_blob_client(
                container=source_container,
                blob=source_blob
            )
            dest_blob_client = self.blob_service_client.get_blob_client(
                container=dest_container,
                blob=dest_blob
            )
            
            # Copy blob
            dest_blob_client.start_copy_from_url(source_blob_client.url)
            
            logger.info(f"Copied {source_container}/{source_blob} to {dest_container}/{dest_blob}")
            return dest_blob_client.url
            
        except Exception as e:
            logger.error(f"Failed to copy blob: {e}")
            raise
    
    def delete_blob(self, container_name, blob_name):
        """
        Delete blob from container.
        
        Args:
            container_name: Container name
            blob_name: Blob name
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            blob_client.delete_blob()
            logger.info(f"Deleted blob {container_name}/{blob_name}")
            
        except Exception as e:
            logger.error(f"Failed to delete blob: {e}")
            raise
    
    def archive_document_blobs(self, doc_id):
        """
        Move all document-related blobs to archive container.
        Copies from raw, extracted, manifests, and thumbs to archive.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            dict: Summary of archived files
        """
        archived = {
            "raw": False,
            "extracted": False,
            "manifest": False,
            "thumbnails": 0
        }
        
        try:
            # Archive raw document (support legacy .pdf and new multi-format naming)
            # Try to get extension from Cosmos metadata, fallback to .pdf for legacy docs
            ext = ".pdf"  # Default for legacy documents
            try:
                from services.cosmos_service import CosmosService
                cosmos = CosmosService()
                doc_meta = cosmos.get_document(doc_id)
                if doc_meta and doc_meta.get("file_extension"):
                    ext = doc_meta["file_extension"]
            except Exception as e:
                logger.warning(f"Could not retrieve file extension for {doc_id}, using .pdf: {e}")
            
            raw_blob = f"{doc_id}{ext}"
            if self.blob_exists(CONTAINER_RAW, raw_blob):
                self.copy_blob(CONTAINER_RAW, raw_blob, CONTAINER_ARCHIVE, f"raw/{raw_blob}")
                self.delete_blob(CONTAINER_RAW, raw_blob)
                archived["raw"] = True
                logger.info(f"Archived raw document for {doc_id}")
            
            # Archive extracted JSON
            extracted_blob = f"{doc_id}.json"
            if self.blob_exists(CONTAINER_EXTRACTED, extracted_blob):
                self.copy_blob(CONTAINER_EXTRACTED, extracted_blob, CONTAINER_ARCHIVE, f"extracted/{extracted_blob}")
                self.delete_blob(CONTAINER_EXTRACTED, extracted_blob)
                archived["extracted"] = True
                logger.info(f"Archived extracted JSON for {doc_id}")
            
            # Archive manifest
            manifest_blob = f"{doc_id}.json"
            if self.blob_exists(CONTAINER_MANIFESTS, manifest_blob):
                self.copy_blob(CONTAINER_MANIFESTS, manifest_blob, CONTAINER_ARCHIVE, f"manifests/{manifest_blob}")
                self.delete_blob(CONTAINER_MANIFESTS, manifest_blob)
                archived["manifest"] = True
                logger.info(f"Archived manifest for {doc_id}")
            
            # Archive thumbnails (iterate through potential pages)
            # We'll check up to 1000 pages (reasonable max)
            container_client = self.blob_service_client.get_container_client(CONTAINER_THUMBS)
            thumbnail_prefix = f"{doc_id}/"
            
            thumb_blobs = container_client.list_blobs(name_starts_with=thumbnail_prefix)
            thumb_count = 0
            
            for blob in thumb_blobs:
                source_blob_name = blob.name
                dest_blob_name = f"thumbs/{source_blob_name}"
                self.copy_blob(CONTAINER_THUMBS, source_blob_name, CONTAINER_ARCHIVE, dest_blob_name)
                self.delete_blob(CONTAINER_THUMBS, source_blob_name)
                thumb_count += 1
            
            archived["thumbnails"] = thumb_count
            if thumb_count > 0:
                logger.info(f"Archived {thumb_count} thumbnails for {doc_id}")
            
            logger.info(f"Successfully archived all blobs for document {doc_id}")
            return archived
            
        except Exception as e:
            logger.error(f"Failed to archive document blobs for {doc_id}: {e}")
            raise
