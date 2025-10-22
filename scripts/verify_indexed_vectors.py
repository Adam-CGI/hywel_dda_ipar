"""
Simple verification script to check if indexed documents have vector embeddings.
This script directly queries Azure AI Search to verify vectors exist.
"""
import os
import sys
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_ADMIN_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX", "ipar-chunks")


def verify_indexed_vectors():
    """Check if indexed documents have vector embeddings."""
    print("\n" + "="*60)
    print("VERIFYING INDEXED DOCUMENT VECTORS")
    print("="*60)
    
    try:
        # Initialize search client
        search_client = SearchClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            index_name=AZURE_SEARCH_INDEX,
            credential=AzureKeyCredential(AZURE_SEARCH_ADMIN_KEY)
        )
        print(f"✅ Connected to index: {AZURE_SEARCH_INDEX}")
        
        # Get a sample of documents
        results = search_client.search(
            search_text="*",
            select=["id", "doc_id", "title", "vector"],
            top=5
        )
        
        doc_count = 0
        vectors_found = 0
        vector_dimensions = set()
        
        print("\nSampling first 5 documents...\n")
        
        for doc in results:
            doc_count += 1
            chunk_id = doc.get("id", "unknown")
            doc_id = doc.get("doc_id", "unknown")
            title = doc.get("title", "unknown")
            vector = doc.get("vector")
            
            print(f"Document {doc_count}:")
            print(f"  Chunk ID: {chunk_id}")
            print(f"  Document ID: {doc_id}")
            print(f"  Title: {title}")
            
            if vector:
                vectors_found += 1
                vector_dim = len(vector)
                vector_dimensions.add(vector_dim)
                print(f"  ✅ Vector: {vector_dim} dimensions")
                print(f"     Sample values: [{vector[0]:.4f}, {vector[1]:.4f}, {vector[2]:.4f}, ...]")
            else:
                print(f"  ❌ Vector: MISSING")
            print()
        
        # Summary
        print("="*60)
        print("SUMMARY")
        print("="*60)
        print(f"Documents checked: {doc_count}")
        print(f"Vectors found: {vectors_found}/{doc_count}")
        
        if vector_dimensions:
            print(f"Vector dimensions: {vector_dimensions}")
            if 3072 in vector_dimensions:
                print("✅ Correct dimension for text-embedding-3-large (3072)")
            else:
                print(f"⚠️  Expected 3072 dimensions, found: {vector_dimensions}")
        
        if vectors_found == doc_count and 3072 in vector_dimensions:
            print("\n✅✅✅ ALL DOCUMENTS HAVE CORRECT EMBEDDINGS! ✅✅✅")
            return True
        elif vectors_found > 0:
            print(f"\n⚠️  Only {vectors_found}/{doc_count} documents have embeddings")
            return False
        else:
            print("\n❌ NO VECTORS FOUND IN INDEX")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = verify_indexed_vectors()
    sys.exit(0 if success else 1)
