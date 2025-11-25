"""
Unit tests for DateParserService - temporal metadata extraction from filenames.
"""
from datetime import datetime
from flask_app.services.date_parser_service import DateParserService


class TestDateParserService:
    """Test date parsing from IPAR filenames."""
    
    def test_parse_date_from_filename_standard_format(self):
        """Test parsing date from standard IPAR filename format."""
        filename = "4.1 Integrated Performance Assurance Report_26-06-25.pdf"
        result = DateParserService.parse_date_from_filename(filename)
        
        assert result is not None
        assert result.year == 2025
        assert result.month == 6
        assert result.day == 26
    
    def test_parse_date_multiple_formats(self):
        """Test parsing dates from various filename formats."""
        test_cases = [
            ("Report_31-03-25.pdf", datetime(2025, 3, 31)),
            ("IPAR_21-10-25.pdf", datetime(2025, 10, 21)),
            ("Document_26-08-25.pdf", datetime(2025, 8, 26)),
            ("5.1 Integrated Performance Assurance Report_26-08-25.pdf", datetime(2025, 8, 26)),
        ]
        
        for filename, expected_date in test_cases:
            result = DateParserService.parse_date_from_filename(filename)
            assert result == expected_date, f"Failed for {filename}"
    
    def test_parse_date_no_extension(self):
        """Test parsing date without .pdf extension."""
        filename = "Report_26-06-25"
        result = DateParserService.parse_date_from_filename(filename)
        
        assert result is not None
        assert result.year == 2025
        assert result.month == 6
        assert result.day == 26
    
    def test_parse_date_year_conversion(self):
        """Test 2-digit to 4-digit year conversion."""
        # Years < 50 should be 20YY
        filename1 = "Report_01-01-25.pdf"
        result1 = DateParserService.parse_date_from_filename(filename1)
        assert result1.year == 2025
        
        filename2 = "Report_01-01-49.pdf"
        result2 = DateParserService.parse_date_from_filename(filename2)
        assert result2.year == 2049
        
        # Years >= 50 should be 19YY
        filename3 = "Report_01-01-50.pdf"
        result3 = DateParserService.parse_date_from_filename(filename3)
        assert result3.year == 1950
        
        filename4 = "Report_01-01-99.pdf"
        result4 = DateParserService.parse_date_from_filename(filename4)
        assert result4.year == 1999
    
    def test_parse_date_no_match(self):
        """Test filename without date pattern returns None."""
        filename = "Report Without Date.pdf"
        result = DateParserService.parse_date_from_filename(filename)
        
        assert result is None
    
    def test_parse_date_invalid_date(self):
        """Test invalid date values return None."""
        # Invalid month
        filename1 = "Report_31-13-25.pdf"
        result1 = DateParserService.parse_date_from_filename(filename1)
        assert result1 is None
        
        # Invalid day
        filename2 = "Report_32-01-25.pdf"
        result2 = DateParserService.parse_date_from_filename(filename2)
        assert result2 is None
    
    def test_format_for_search_index(self):
        """Test formatting datetime for Azure Search DateTimeOffset field."""
        date = datetime(2025, 6, 26, 0, 0, 0)
        result = DateParserService.format_for_search_index(date)
        
        assert result == "2025-06-26T00:00:00Z"
    
    def test_format_for_search_index_none(self):
        """Test formatting None returns None."""
        result = DateParserService.format_for_search_index(None)
        assert result is None
    
    def test_get_fiscal_year(self):
        """Test NHS fiscal year calculation (April to March)."""
        # Date in April - start of fiscal year
        date1 = datetime(2025, 4, 1)
        assert DateParserService.get_fiscal_year(date1) == "2025-26"
        
        # Date in June - middle of fiscal year
        date2 = datetime(2025, 6, 26)
        assert DateParserService.get_fiscal_year(date2) == "2025-26"
        
        # Date in March - end of fiscal year
        date3 = datetime(2025, 3, 31)
        assert DateParserService.get_fiscal_year(date3) == "2024-25"
        
        # Date in January - middle of fiscal year
        date4 = datetime(2025, 1, 15)
        assert DateParserService.get_fiscal_year(date4) == "2024-25"
    
    def test_extract_date_metadata_complete(self):
        """Test extracting complete date metadata dictionary."""
        filename = "4.1 Integrated Performance Assurance Report_26-06-25.pdf"
        result = DateParserService.extract_date_metadata(filename)
        
        assert result['document_date'] == "2025-06-26T00:00:00Z"
        assert result['year'] == 2025
        assert result['month'] == 6
        assert result['quarter'] == 2  # Q2: April, May, June
        assert result['fiscal_year'] == "2025-26"
        assert result['document_date_raw'] == datetime(2025, 6, 26)
    
    def test_extract_date_metadata_quarters(self):
        """Test quarter calculation for all quarters."""
        test_cases = [
            ("Report_15-01-25.pdf", 1),  # Q1: Jan, Feb, Mar
            ("Report_15-02-25.pdf", 1),
            ("Report_15-03-25.pdf", 1),
            ("Report_15-04-25.pdf", 2),  # Q2: Apr, May, Jun
            ("Report_15-05-25.pdf", 2),
            ("Report_15-06-25.pdf", 2),
            ("Report_15-07-25.pdf", 3),  # Q3: Jul, Aug, Sep
            ("Report_15-08-25.pdf", 3),
            ("Report_15-09-25.pdf", 3),
            ("Report_15-10-25.pdf", 4),  # Q4: Oct, Nov, Dec
            ("Report_15-11-25.pdf", 4),
            ("Report_15-12-25.pdf", 4),
        ]
        
        for filename, expected_quarter in test_cases:
            result = DateParserService.extract_date_metadata(filename)
            assert result['quarter'] == expected_quarter, f"Failed for {filename}"
    
    def test_extract_date_metadata_no_date(self):
        """Test extracting metadata when no date is present."""
        filename = "Report Without Date.pdf"
        result = DateParserService.extract_date_metadata(filename)
        
        assert result['document_date'] is None
        assert result['document_date_raw'] is None
        assert result['year'] is None
        assert result['month'] is None
        assert result['quarter'] is None
        assert result['fiscal_year'] is None
    
    def test_real_ipar_filenames(self):
        """Test with actual IPAR filenames from the data folder."""
        filenames = [
            "4.1 Integrated Performance Assurance Report_26-06-25.pdf",
            "4.1 M12 2024-25 IPAR Overview_31-03-25.pdf",
            "5.1 Integrated Performance Assurance Report_26-08-25.pdf",
            "6.1 Integrated Performance Assurance Report_21-10-25.pdf"
        ]
        
        expected_dates = [
            datetime(2025, 6, 26),
            datetime(2025, 3, 31),
            datetime(2025, 8, 26),
            datetime(2025, 10, 21)
        ]
        
        for filename, expected_date in zip(filenames, expected_dates):
            result = DateParserService.parse_date_from_filename(filename)
            assert result == expected_date, f"Failed for {filename}"
            
            # Also test full metadata extraction
            metadata = DateParserService.extract_date_metadata(filename)
            assert metadata['year'] == expected_date.year
            assert metadata['month'] == expected_date.month
