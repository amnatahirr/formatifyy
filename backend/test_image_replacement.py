#!/usr/bin/env python3
"""
Test script to verify image replacement endpoint is working
Run this to debug the 404 issue
"""

import requests
import os
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000/api"  # Change if needed
DOCUMENT_ID = 289
IMAGE_INDEX = 0

# Create a simple test image
test_image_path = Path("test_image.png")
if not test_image_path.exists():
    from PIL import Image
    img = Image.new('RGB', (100, 100), color='red')
    img.save(test_image_path)
    print(f"Created test image: {test_image_path}")

# Test the endpoint
endpoint = f"{BASE_URL}/documents/{DOCUMENT_ID}/replace-image"
print(f"\nTesting endpoint: {endpoint}")

try:
    with open(test_image_path, 'rb') as f:
        files = {
            'file': ('test_image.png', f, 'image/png')
        }
        data = {
            'image_index': IMAGE_INDEX
        }
        
        print(f"Sending POST request with:")
        print(f"  - document_id: {DOCUMENT_ID}")
        print(f"  - image_index: {IMAGE_INDEX}")
        print(f"  - file: test_image.png")
        
        response = requests.post(endpoint, files=files, data=data)
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body: {response.json()}")
        
        if response.status_code == 200:
            print("\n✓ SUCCESS: Endpoint is working!")
        else:
            print(f"\n✗ FAILED: Got status {response.status_code}")
            
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    print("\nTroubleshooting:")
    print("1. Make sure your backend is running: python main.py")
    print("2. Check BASE_URL is correct (should be http://localhost:8000/api)")
    print("3. Verify the router is registered in main.py")
finally:
    # Cleanup
    if test_image_path.exists():
        test_image_path.unlink()
        print(f"\nCleaned up test image: {test_image_path}")
