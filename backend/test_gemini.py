import asyncio
import os
import sys
from dotenv import load_dotenv

# Add current dir to path
sys.path.append(os.path.dirname(__file__))

load_dotenv()

# We can also check if a system key is set or try fallback
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

async def main():
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY is not set in backend/.env. Please configure it for verification.")
        sys.exit(1)
        
    print("Testing GeminiClientAdapter...")
    from gemini_adapter import GeminiClientAdapter
    
    adapter = GeminiClientAdapter(api_key=GEMINI_API_KEY)
    
    prompt = """
    Analyze the following paragraphs for grammar errors:
    [{"paragraph_id": "p0", "page": 1, "text": "This are a test with grammar problems."}]
    For each error, return JSON with "paragraph_id", "page", "original", "suggestion", "reason", "severity".
    Return structure: {"issues": [...]}
    """
    
    messages = [{"role": "user", "content": prompt}]
    
    try:
        response = await adapter.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=messages
        )
        print("Success! Gemini response:")
        print(response.content[0].text)
        
        # Test parsing
        import json
        data = json.loads(response.content[0].text)
        print("Parsed JSON successfully:", data)
    except Exception as e:
        print("API test failed:", e)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
