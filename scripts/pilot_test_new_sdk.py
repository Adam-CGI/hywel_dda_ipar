#!/usr/bin/env python3
"""
Pilot Test Script for azure-ai-documentintelligence SDK v4.0

This script tests the new DocumentIntelligenceClient SDK to verify it supports
Office formats (DOCX, XLSX, PPTX) before upgrading the main codebase.

Prerequisites:
    pip install azure-ai-documentintelligence python-dotenv

Usage:
    python scripts/pilot_test_new_sdk.py --test-file /path/to/document.docx
    python scripts/pilot_test_new_sdk.py --test-all  # Test with sample files in data/
    python scripts/pilot_test_new_sdk.py --connection-only  # Just test SDK connection

Environment variables required (from .env):
    AZURE_DOCINTEL_ENDPOINT - Document Intelligence endpoint URL
    AZURE_DOCINTEL_KEY - Document Intelligence API key
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment from flask_app directory
env_path = Path(__file__).parent.parent / "flask_app" / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Try root .env
    load_dotenv(Path(__file__).parent.parent / ".env")


def check_sdk_installation():
    """Check if the new SDK is installed."""
    print("\n" + "=" * 60)
    print("STEP 1: Checking SDK Installation")
    print("=" * 60)
    
    try:
        import azure.ai.documentintelligence
        version = getattr(azure.ai.documentintelligence, '__version__', 'unknown')
        print(f"✅ azure-ai-documentintelligence is installed (version: {version})")
        return True
    except ImportError:
        print("❌ azure-ai-documentintelligence is NOT installed")
        print("\nTo install, run:")
        print("    pip install azure-ai-documentintelligence")
        return False


def check_environment():
    """Check required environment variables."""
    print("\n" + "=" * 60)
    print("STEP 2: Checking Environment Variables")
    print("=" * 60)
    
    endpoint = os.getenv("AZURE_DOCINTEL_ENDPOINT")
    key = os.getenv("AZURE_DOCINTEL_KEY")
    
    if endpoint:
        print(f"✅ AZURE_DOCINTEL_ENDPOINT: {endpoint[:50]}...")
    else:
        print("❌ AZURE_DOCINTEL_ENDPOINT is not set")
        
    if key:
        print(f"✅ AZURE_DOCINTEL_KEY: {key[:8]}...{key[-4:]}")
    else:
        print("❌ AZURE_DOCINTEL_KEY is not set")
    
    return bool(endpoint and key)


def test_connection():
    """Test connection to Azure Document Intelligence with new SDK."""
    print("\n" + "=" * 60)
    print("STEP 3: Testing SDK Connection")
    print("=" * 60)
    
    try:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential
        
        endpoint = os.getenv("AZURE_DOCINTEL_ENDPOINT")
        key = os.getenv("AZURE_DOCINTEL_KEY")
        
        # Create client
        client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key)
        )
        
        print(f"✅ DocumentIntelligenceClient created successfully")
        print(f"   Endpoint: {endpoint}")
        
        return client
        
    except Exception as e:
        print(f"❌ Failed to create client: {e}")
        return None


def test_document_extraction(client, file_path: str):
    """Test document extraction with the new SDK."""
    print("\n" + "=" * 60)
    print(f"STEP 4: Testing Document Extraction")
    print("=" * 60)
    
    file_path = Path(file_path)
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False
    
    ext = file_path.suffix.lower()
    file_size = file_path.stat().st_size
    
    print(f"📄 File: {file_path.name}")
    print(f"   Extension: {ext}")
    print(f"   Size: {file_size:,} bytes")
    
    # Map extensions to expected MIME types
    mime_types = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.tiff': 'image/tiff',
        '.bmp': 'image/bmp',
        '.html': 'text/html',
    }
    
    content_type = mime_types.get(ext)
    if content_type:
        print(f"   Content-Type: {content_type}")
    else:
        print(f"   ⚠️ Unknown extension, attempting extraction anyway")
    
    try:
        print(f"\n🔄 Starting document analysis...")
        start_time = datetime.now()
        
        # Use the new SDK's analyze_document method
        # The new SDK accepts a file handle directly via body parameter
        with open(file_path, "rb") as f:
            poller = client.begin_analyze_document(
                model_id="prebuilt-layout",
                body=f
            )
        
        result = poller.result()
        elapsed = (datetime.now() - start_time).total_seconds()
        
        print(f"✅ Document analysis completed in {elapsed:.2f}s")
        
        # Extract key information
        if result.content:
            content_preview = result.content[:500]
            if len(result.content) > 500:
                content_preview += "..."
            print(f"\n📝 Extracted Content Preview:")
            print("-" * 40)
            print(content_preview)
            print("-" * 40)
            print(f"\nTotal content length: {len(result.content):,} characters")
        
        # Page information
        if hasattr(result, 'pages') and result.pages:
            print(f"\n📄 Pages: {len(result.pages)}")
            for i, page in enumerate(result.pages[:3]):  # Show first 3 pages
                width = getattr(page, 'width', 'N/A')
                height = getattr(page, 'height', 'N/A')
                print(f"   Page {i+1}: {width}x{height}")
            if len(result.pages) > 3:
                print(f"   ... and {len(result.pages) - 3} more pages")
        
        # Tables
        if hasattr(result, 'tables') and result.tables:
            print(f"\n📊 Tables detected: {len(result.tables)}")
        
        return True
        
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds() if 'start_time' in dir() else 0
        print(f"\n❌ Extraction failed after {elapsed:.2f}s")
        print(f"   Error: {type(e).__name__}: {e}")
        
        # Check for specific error types
        error_str = str(e).lower()
        if "invalidcontent" in error_str:
            print("\n💡 This error indicates the file format is not supported.")
            print("   The new SDK should support: PDF, DOCX, XLSX, PPTX, PNG, JPG, TIFF, BMP, HTML")
        elif "unauthorized" in error_str or "401" in error_str:
            print("\n💡 Authentication failed. Check your API key.")
        elif "notfound" in error_str or "404" in error_str:
            print("\n💡 Endpoint not found. Check your endpoint URL.")
            
        return False


def find_test_files(data_dir: Path):
    """Find test files in the data directory."""
    supported_extensions = {'.pdf', '.docx', '.xlsx', '.pptx', '.png', '.jpg', '.jpeg', '.tiff', '.bmp'}
    test_files = []
    
    if data_dir.exists():
        for ext in supported_extensions:
            test_files.extend(data_dir.glob(f"*{ext}"))
            test_files.extend(data_dir.glob(f"*{ext.upper()}"))
    
    return sorted(test_files)


def run_pilot_test(args):
    """Run the complete pilot test."""
    print("\n" + "=" * 70)
    print("  PILOT TEST: azure-ai-documentintelligence SDK v4.0")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)
    
    results = {
        "sdk_installed": False,
        "env_configured": False,
        "connection_ok": False,
        "extractions": []
    }
    
    # Step 1: Check SDK installation
    results["sdk_installed"] = check_sdk_installation()
    if not results["sdk_installed"]:
        print("\n⛔ Cannot continue without SDK. Install it first.")
        return results
    
    # Step 2: Check environment
    results["env_configured"] = check_environment()
    if not results["env_configured"]:
        print("\n⛔ Cannot continue without environment configuration.")
        return results
    
    # Step 3: Test connection
    client = test_connection()
    results["connection_ok"] = client is not None
    
    if not results["connection_ok"]:
        print("\n⛔ Cannot continue without working connection.")
        return results
    
    if args.connection_only:
        print("\n✅ Connection test passed. Use --test-file to test extraction.")
        return results
    
    # Step 4: Test document extraction
    test_files = []
    
    if args.test_file:
        test_files = [Path(args.test_file)]
    elif args.test_all:
        data_dir = Path(__file__).parent.parent / "data"
        test_files = find_test_files(data_dir)
        if not test_files:
            print(f"\n⚠️ No test files found in {data_dir}")
            print("   Place some PDF, DOCX, XLSX, or PPTX files there and try again.")
    
    for file_path in test_files:
        success = test_document_extraction(client, str(file_path))
        results["extractions"].append({
            "file": str(file_path),
            "extension": file_path.suffix.lower(),
            "success": success
        })
    
    # Summary
    print("\n" + "=" * 70)
    print("  PILOT TEST SUMMARY")
    print("=" * 70)
    print(f"  SDK Installed:     {'✅ Yes' if results['sdk_installed'] else '❌ No'}")
    print(f"  Env Configured:    {'✅ Yes' if results['env_configured'] else '❌ No'}")
    print(f"  Connection OK:     {'✅ Yes' if results['connection_ok'] else '❌ No'}")
    
    if results["extractions"]:
        print(f"\n  Extraction Results:")
        for ext_result in results["extractions"]:
            status = "✅ PASS" if ext_result["success"] else "❌ FAIL"
            print(f"    {status} - {Path(ext_result['file']).name} ({ext_result['extension']})")
        
        passed = sum(1 for r in results["extractions"] if r["success"])
        total = len(results["extractions"])
        print(f"\n  Total: {passed}/{total} extractions successful")
    
    print("=" * 70)
    
    # Next steps
    if all([results["sdk_installed"], results["env_configured"], results["connection_ok"]]):
        if not results["extractions"]:
            print("\n📋 Next Steps:")
            print("   1. Run with --test-file /path/to/document.docx to test extraction")
            print("   2. Or place test files in data/ and run with --test-all")
        elif all(r["success"] for r in results["extractions"]):
            print("\n🎉 All tests passed! The new SDK is working correctly.")
            print("\n📋 Next Steps to upgrade the main codebase:")
            print("   1. Add 'azure-ai-documentintelligence' to flask_app/requirements.txt")
            print("   2. Update flask_app/config.py to use DocumentIntelligenceClient")
            print("   3. Update flask_app/services/extraction_service.py")
            print("   4. Re-enable Office formats in routes/documents.py")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Pilot test for azure-ai-documentintelligence SDK v4.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Test just the connection
    python scripts/pilot_test_new_sdk.py --connection-only

    # Test with a specific file
    python scripts/pilot_test_new_sdk.py --test-file /path/to/document.docx

    # Test all files in data/ directory
    python scripts/pilot_test_new_sdk.py --test-all
        """
    )
    
    parser.add_argument(
        "--test-file",
        type=str,
        help="Path to a document file to test extraction"
    )
    parser.add_argument(
        "--test-all",
        action="store_true",
        help="Test all supported files in the data/ directory"
    )
    parser.add_argument(
        "--connection-only",
        action="store_true",
        help="Only test SDK installation and connection"
    )
    
    args = parser.parse_args()
    
    # Default to connection-only if no file specified
    if not args.test_file and not args.test_all:
        args.connection_only = True
    
    results = run_pilot_test(args)
    
    # Exit with appropriate code
    if not all([results["sdk_installed"], results["env_configured"], results["connection_ok"]]):
        sys.exit(1)
    if results["extractions"] and not all(r["success"] for r in results["extractions"]):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
