"""
Date parser service for extracting temporal information from IPAR filenames.
Handles various date formats in filenames like "_26-06-25.pdf" or "_31-03-25.pdf"
"""
import logging
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class DateParserService:
    """Service for parsing dates from IPAR document filenames."""
    
    # Pattern: _DD-MM-YY.pdf or _DD-MM-YY at end of filename
    DATE_PATTERN = re.compile(r'_(\d{2})-(\d{2})-(\d{2})(?:\.pdf)?$', re.IGNORECASE)
    
    @staticmethod
    def parse_date_from_filename(filename: str) -> Optional[datetime]:
        """
        Extract date from filename pattern like "Report_26-06-25.pdf"
        
        Args:
            filename: Original filename
            
        Returns:
            datetime object if date found, None otherwise
        """
        try:
            match = DateParserService.DATE_PATTERN.search(filename)
            if not match:
                logger.debug(f"No date pattern found in filename: {filename}")
                return None
            
            day = int(match.group(1))
            month = int(match.group(2))
            year_short = int(match.group(3))
            
            # Convert 2-digit year to 4-digit (assume 20YY for years < 50, 19YY for >= 50)
            year = 2000 + year_short if year_short < 50 else 1900 + year_short
            
            # Create datetime object
            document_date = datetime(year, month, day)
            
            logger.info(f"Parsed date from '{filename}': {document_date.strftime('%Y-%m-%d')}")
            return document_date
            
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse date from filename '{filename}': {e}")
            return None
    
    @staticmethod
    def format_for_search_index(date: Optional[datetime]) -> Optional[str]:
        """
        Format datetime for Azure Search DateTimeOffset field.
        
        Args:
            date: datetime object
            
        Returns:
            ISO 8601 formatted string with 'Z' suffix for UTC
        """
        if date is None:
            return None
        
        # Azure Search expects ISO 8601 format: YYYY-MM-DDTHH:MM:SS.sssZ
        return date.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
    
    @staticmethod
    def extract_date_metadata(filename: str) -> dict:
        """
        Extract comprehensive date metadata from filename.
        
        Args:
            filename: Original filename
            
        Returns:
            Dictionary with parsed date information
        """
        parsed_date = DateParserService.parse_date_from_filename(filename)
        
        if parsed_date:
            return {
                'document_date': DateParserService.format_for_search_index(parsed_date),
                'document_date_raw': parsed_date,
                'year': parsed_date.year,
                'month': parsed_date.month,
                'quarter': (parsed_date.month - 1) // 3 + 1,
                'fiscal_year': DateParserService.get_fiscal_year(parsed_date)
            }
        else:
            return {
                'document_date': None,
                'document_date_raw': None,
                'year': None,
                'month': None,
                'quarter': None,
                'fiscal_year': None
            }
    
    @staticmethod
    def get_fiscal_year(date: datetime) -> str:
        """
        Get NHS fiscal year (April to March).
        
        Args:
            date: datetime object
            
        Returns:
            Fiscal year string like "2024-25"
        """
        # NHS fiscal year runs April to March
        if date.month >= 4:
            start_year = date.year
            end_year = date.year + 1
        else:
            start_year = date.year - 1
            end_year = date.year
        
        return f"{start_year}-{str(end_year)[-2:]}"
