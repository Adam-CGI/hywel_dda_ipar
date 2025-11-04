"""
Document extraction service using Azure Document Intelligence.
"""
import logging
from io import BytesIO
from PIL import Image
import pypdfium2 as pdfium
from app.config import get_document_intelligence_client, CONTAINER_EXTRACTED, CONTAINER_THUMBS, CONTAINER_MANIFESTS
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class ExtractionService:
    """Service for extracting text and metadata from PDFs."""
    
    def __init__(self):
        self.doc_intel_client = get_document_intelligence_client()
        self.storage_service = StorageService()
    
    def extract_document(self, doc_id, pdf_bytes):
        """
        Extract text and layout from PDF using Document Intelligence.
        
        Args:
            doc_id: Document identifier (SHA256)
            pdf_bytes: PDF file content as bytes
            
        Returns:
            dict: Extraction results with pages, text, tables
        """
        try:
            logger.info(f"Starting extraction for document {doc_id}")
            
            # Analyze document using Document Intelligence
            poller = self.doc_intel_client.begin_analyze_document(
                "prebuilt-layout",
                document=BytesIO(pdf_bytes)
            )
            result = poller.result()
            
            # Extract structured data
            extraction_data = {
                "doc_id": doc_id,
                "pages": [],
                "tables": [],
                "key_value_pairs": [],
                "full_text": ""
            }
            
            # Process pages
            for page_num, page in enumerate(result.pages, start=1):
                page_data = {
                    "page_no": page_num,
                    "width": page.width,
                    "height": page.height,
                    "unit": page.unit,
                    "text": "",
                    "lines": [],
                    "words": []
                }
                
                # Extract lines
                if page.lines:
                    for line in page.lines:
                        line_data = {
                            "text": line.content,
                            "bounding_box": [point for point in line.polygon] if line.polygon else []
                        }
                        page_data["lines"].append(line_data)
                        page_data["text"] += line.content + "\n"
                
                # Extract words
                if page.words:
                    for word in page.words:
                        word_data = {
                            "text": word.content,
                            "confidence": word.confidence if hasattr(word, 'confidence') else None,
                            "bounding_box": [point for point in word.polygon] if word.polygon else []
                        }
                        page_data["words"].append(word_data)
                
                extraction_data["pages"].append(page_data)
                extraction_data["full_text"] += page_data["text"] + "\n\n"
            
            # Process tables
            if result.tables:
                for table_idx, table in enumerate(result.tables):
                    table_data = {
                        "table_id": table_idx,
                        "row_count": table.row_count,
                        "column_count": table.column_count,
                        "cells": []
                    }
                    
                    for cell in table.cells:
                        cell_data = {
                            "row_index": cell.row_index,
                            "column_index": cell.column_index,
                            "content": cell.content,
                            "row_span": cell.row_span if hasattr(cell, 'row_span') else 1,
                            "column_span": cell.column_span if hasattr(cell, 'column_span') else 1
                        }
                        table_data["cells"].append(cell_data)
                    
                    extraction_data["tables"].append(table_data)
            
            # Save extraction result to blob storage
            extraction_blob_name = f"{doc_id}.json"
            self.storage_service.upload_json(
                CONTAINER_EXTRACTED,
                extraction_blob_name,
                extraction_data
            )
            
            logger.info(f"Completed extraction for document {doc_id}")
            return extraction_data
            
        except Exception as e:
            logger.error(f"Failed to extract document {doc_id}: {e}")
            raise
    
    def generate_thumbnails(self, doc_id, pdf_bytes, scale=2.0):
        """
        Generate page thumbnails from PDF using pypdfium2.
        
        Args:
            doc_id: Document identifier
            pdf_bytes: PDF file content as bytes
            scale: Scale factor for rendering (default 2.0 for good quality)
            
        Returns:
            list: List of thumbnail blob URLs
        """
        try:
            logger.info(f"Generating thumbnails for document {doc_id}")
            
            # Load PDF from bytes
            pdf = pdfium.PdfDocument(pdf_bytes)
            thumbnail_urls = []
            
            for page_num in range(len(pdf)):
                page = pdf[page_num]
                
                # Render page to PIL Image
                # scale=2.0 gives approximately 144 DPI for standard pages
                pil_image = page.render(
                    scale=scale,
                    rotation=0,
                ).to_pil()
                
                # Resize to thumbnail (max 800x800)
                pil_image.thumbnail((800, 800), Image.Resampling.LANCZOS)
                
                # Save to bytes
                img_byte_arr = BytesIO()
                pil_image.save(img_byte_arr, format='PNG')
                img_bytes = img_byte_arr.getvalue()
                
                # Upload to blob storage
                thumb_blob_name = f"{doc_id}/p{page_num + 1}.png"
                thumb_url = self.storage_service.upload_image(
                    CONTAINER_THUMBS,
                    thumb_blob_name,
                    img_bytes
                )
                
                thumbnail_urls.append({
                    "page_no": page_num + 1,
                    "url": thumb_url,
                    "blob_name": thumb_blob_name
                })
            
            pdf.close()
            logger.info(f"Generated {len(thumbnail_urls)} thumbnails for document {doc_id}")
            return thumbnail_urls
            
        except Exception as e:
            logger.error(f"Failed to generate thumbnails for {doc_id}: {e}")
            raise
    
    def create_manifest(self, doc_id, origin_filename, extraction_data, thumbnail_urls):
        """
        Create and save document manifest.
        
        Args:
            doc_id: Document identifier
            origin_filename: Original filename
            extraction_data: Extraction results
            thumbnail_urls: List of thumbnail URLs
            
        Returns:
            dict: Manifest data
        """
        try:
            from datetime import datetime
            
            manifest = {
                "doc_id": doc_id,
                "origin_filename": origin_filename,
                "created_at": datetime.utcnow().isoformat(),
                "page_count": len(extraction_data.get("pages", [])),
                "table_count": len(extraction_data.get("tables", [])),
                "has_extraction": True,
                "has_thumbnails": len(thumbnail_urls) > 0,
                "thumbnail_count": len(thumbnail_urls),
                "thumbnails": thumbnail_urls,
                "extraction_blob": f"{doc_id}.json",
                "text_length": len(extraction_data.get("full_text", ""))
            }
            
            # Save manifest to blob storage
            manifest_blob_name = f"{doc_id}.json"
            self.storage_service.upload_json(
                CONTAINER_MANIFESTS,
                manifest_blob_name,
                manifest
            )
            
            logger.info(f"Created manifest for document {doc_id}")
            return manifest
            
        except Exception as e:
            logger.error(f"Failed to create manifest for {doc_id}: {e}")
            raise
    
    def process_document(self, doc_id, pdf_bytes, origin_filename):
        """
        Full document processing pipeline: extract, generate thumbnails, create manifest.
        
        Args:
            doc_id: Document identifier
            pdf_bytes: PDF file content as bytes
            origin_filename: Original filename
            
        Returns:
            dict: Processing results with extraction_data, thumbnails, manifest
        """
        try:
            logger.info(f"Processing document {doc_id}")
            
            # Step 1: Extract text and layout
            extraction_data = self.extract_document(doc_id, pdf_bytes)
            
            # Step 2: Generate thumbnails
            thumbnail_urls = self.generate_thumbnails(doc_id, pdf_bytes)
            
            # Step 3: Create manifest
            manifest = self.create_manifest(
                doc_id,
                origin_filename,
                extraction_data,
                thumbnail_urls
            )
            
            result = {
                "doc_id": doc_id,
                "extraction_data": extraction_data,
                "thumbnails": thumbnail_urls,
                "manifest": manifest,
                "success": True
            }
            
            logger.info(f"Successfully processed document {doc_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process document {doc_id}: {e}")
            raise
