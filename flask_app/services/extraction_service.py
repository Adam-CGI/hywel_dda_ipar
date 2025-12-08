"""
Document extraction service using Azure Document Intelligence SDK v4.0.
Supports PDF, images (PNG, JPG, TIFF, BMP), and Office formats (DOCX, XLSX, PPTX).
"""
import logging
import os
from io import BytesIO
from PIL import Image
import pypdfium2 as pdfium
from config import get_document_intelligence_client, CONTAINER_EXTRACTED, CONTAINER_THUMBS, CONTAINER_MANIFESTS
from services.storage_service import StorageService

logger = logging.getLogger(__name__)

# Formats that support PDF-style thumbnail generation
PDF_FORMATS = {'.pdf'}
# Formats that are images and can be thumbnailed directly
IMAGE_FORMATS = {'.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.heif'}
# Office formats - not yet supported (requires SDK v4.0 upgrade)
# OFFICE_FORMATS = {'.docx', '.xlsx', '.pptx'}


class ExtractionService:
    """Service for extracting text and metadata from documents."""
    
    def __init__(self):
        self.doc_intel_client = get_document_intelligence_client()
        self.storage_service = StorageService()
    
    def extract_document(self, doc_id, document_bytes):
        """
        Extract text and layout from document using Document Intelligence.
        
        Args:
            doc_id: Document identifier (SHA256)
            document_bytes: Document file content as bytes
            
        Returns:
            dict: Extraction results with pages, text, tables
        """
        try:
            logger.info(f"Starting extraction for document {doc_id}")
            
            # Analyze document using Document Intelligence
            # (Azure Doc Intel handles PDF, images, and Office formats natively)
            poller = self.doc_intel_client.begin_analyze_document(
                model_id="prebuilt-layout",
                body=BytesIO(document_bytes)
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
            
            # For Office formats (DOCX, XLSX, PPTX), page.lines may be None
            # but result.content contains the full document text.
            # We use result.content as the primary text source when available.
            document_content = result.content if hasattr(result, 'content') and result.content else ""
            
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
                
                # Extract lines (available for PDFs and images, may be None for Office formats)
                if page.lines:
                    for line in page.lines:
                        line_data = {
                            "text": line.content,
                            "bounding_box": [point for point in line.polygon] if line.polygon else []
                        }
                        page_data["lines"].append(line_data)
                        page_data["text"] += line.content + "\n"
                
                # Extract words (may have span info instead of polygon for Office formats)
                if page.words:
                    for word in page.words:
                        # Handle both old and new SDK word structures
                        word_content = word.get('content') if isinstance(word, dict) else getattr(word, 'content', '')
                        word_confidence = word.get('confidence') if isinstance(word, dict) else getattr(word, 'confidence', None)
                        word_polygon = word.get('polygon') if isinstance(word, dict) else getattr(word, 'polygon', None)
                        
                        word_data = {
                            "text": word_content,
                            "confidence": word_confidence,
                            "bounding_box": [point for point in word_polygon] if word_polygon else []
                        }
                        page_data["words"].append(word_data)
                
                # For Office formats where lines are None, build text from page spans
                if not page_data["text"] and page.spans and document_content:
                    # Extract text for this page from document_content using spans
                    for span in page.spans:
                        offset = span.get('offset') if isinstance(span, dict) else getattr(span, 'offset', 0)
                        length = span.get('length') if isinstance(span, dict) else getattr(span, 'length', 0)
                        page_data["text"] = document_content[offset:offset + length]
                
                extraction_data["pages"].append(page_data)
                extraction_data["full_text"] += page_data["text"] + "\n\n"
            
            # If full_text is still empty but we have document_content, use it directly
            if not extraction_data["full_text"].strip() and document_content:
                extraction_data["full_text"] = document_content
                # Also update the first page text if we only have one page
                if len(extraction_data["pages"]) == 1:
                    extraction_data["pages"][0]["text"] = document_content
            
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
    
    def _get_file_extension(self, origin_filename):
        """Extract lowercase file extension from filename."""
        return os.path.splitext(origin_filename.lower())[1] if origin_filename else '.pdf'
    
    def generate_thumbnails(self, doc_id, document_bytes, origin_filename, scale=2.0):
        """
        Generate page thumbnails from document.
        
        Supports:
        - PDF: Full page rendering via pypdfium2
        - Images: Direct resize via PIL
        - Office formats: Skipped (returns empty list)
        
        Args:
            doc_id: Document identifier
            document_bytes: Document file content as bytes
            origin_filename: Original filename (used to detect format)
            scale: Scale factor for PDF rendering (default 2.0)
            
        Returns:
            list: List of thumbnail blob URLs (may be empty for unsupported formats)
        """
        ext = self._get_file_extension(origin_filename)
        
        if ext in PDF_FORMATS:
            return self._generate_pdf_thumbnails(doc_id, document_bytes, scale)
        elif ext in IMAGE_FORMATS:
            return self._generate_image_thumbnail(doc_id, document_bytes, ext)
        else:
            logger.warning(f"Unknown format {ext} for thumbnail generation (doc_id={doc_id})")
            return []
    
    def _generate_pdf_thumbnails(self, doc_id, pdf_bytes, scale=2.0):
        """Generate thumbnails from PDF using pypdfium2."""
        try:
            logger.info(f"Generating PDF thumbnails for document {doc_id}")
            
            pdf = pdfium.PdfDocument(pdf_bytes)
            thumbnail_urls = []
            
            for page_num in range(len(pdf)):
                page = pdf[page_num]
                
                pil_image = page.render(
                    scale=scale,
                    rotation=0,
                ).to_pil()
                
                pil_image.thumbnail((800, 800), Image.Resampling.LANCZOS)
                
                img_byte_arr = BytesIO()
                pil_image.save(img_byte_arr, format='PNG')
                img_bytes = img_byte_arr.getvalue()
                
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
            logger.info(f"Generated {len(thumbnail_urls)} PDF thumbnails for document {doc_id}")
            return thumbnail_urls
            
        except Exception as e:
            logger.error(f"Failed to generate PDF thumbnails for {doc_id}: {e}")
            raise
    
    def _generate_image_thumbnail(self, doc_id, image_bytes, ext):
        """Generate thumbnail from image file using PIL."""
        try:
            logger.info(f"Generating image thumbnail for document {doc_id}")
            
            pil_image = Image.open(BytesIO(image_bytes))
            
            # Convert to RGB if necessary (e.g., for RGBA PNGs)
            if pil_image.mode in ('RGBA', 'P'):
                pil_image = pil_image.convert('RGB')
            
            pil_image.thumbnail((800, 800), Image.Resampling.LANCZOS)
            
            img_byte_arr = BytesIO()
            pil_image.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()
            
            thumb_blob_name = f"{doc_id}/p1.png"
            thumb_url = self.storage_service.upload_image(
                CONTAINER_THUMBS,
                thumb_blob_name,
                img_bytes
            )
            
            logger.info(f"Generated image thumbnail for document {doc_id}")
            return [{
                "page_no": 1,
                "url": thumb_url,
                "blob_name": thumb_blob_name
            }]
            
        except Exception as e:
            # Non-blocking for image thumbnails - log and return empty
            logger.warning(f"Failed to generate image thumbnail for {doc_id}: {e}")
            return []
    
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
            
            ext = self._get_file_extension(origin_filename)
            
            manifest = {
                "doc_id": doc_id,
                "origin_filename": origin_filename,
                "file_extension": ext,
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
    
    def process_document(self, doc_id, document_bytes, origin_filename):
        """
        Full document processing pipeline: extract, generate thumbnails, create manifest.
        
        Args:
            doc_id: Document identifier
            document_bytes: Document file content as bytes
            origin_filename: Original filename
            
        Returns:
            dict: Processing results with extraction_data, thumbnails, manifest
        """
        try:
            logger.info(f"Processing document {doc_id}")
            
            # Step 1: Extract text and layout
            extraction_data = self.extract_document(doc_id, document_bytes)
            
            # Step 2: Generate thumbnails (non-blocking for non-PDF formats)
            try:
                thumbnail_urls = self.generate_thumbnails(doc_id, document_bytes, origin_filename)
            except Exception as e:
                logger.warning(f"Thumbnail generation failed for {doc_id}, continuing without thumbnails: {e}")
                thumbnail_urls = []
            
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
