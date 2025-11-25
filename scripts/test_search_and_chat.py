"""Test search and chat functionality."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from flask_app.services.search_service import SearchService
from flask_app.services.chat_service import ChatService

print("\n" + "="*80)
print("TESTING SEARCH AND CHAT")
print("="*80)

# Test search
print("\n1. Testing search...")
search = SearchService()
results = search.search("IPAR performance indicators", top=3)
print(f"   Found {results['count']} results")
if results['count'] > 0:
    print(f"   ✅ Search is working!")
    for i, r in enumerate(results['results'][:2], 1):
        print(f"      {i}. {r.get('title', 'Unknown')[:60]} (score: {r.get('score', 0):.2f})")
else:
    print(f"   ❌ No search results!")
    sys.exit(1)

# Test chat
print("\n2. Testing chat...")
chat = ChatService()
try:
    response = chat.chat("What are the key performance indicators mentioned in the IPAR report?", top_k=3)
    print(f"   ✅ Chat response received")
    print(f"   Sources used: {len(response['sources'])}")
    print(f"   Response preview: {response['response'][:200]}...")
    
    if "I don't have information" in response['response']:
        print(f"\n   ⚠️  Chat says no information found, but search found results!")
    else:
        print(f"\n   ✅✅✅ CHAT IS WORKING WITH GROUNDED RESPONSES!")
except Exception as e:
    print(f"   ❌ Chat failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
