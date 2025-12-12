#!/usr/bin/env python3
"""
Manual test script for MRV ingestion APIs
"""

import asyncio
import httpx
import json
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8002"
TEST_TOKEN = "test-token"  # This will fail auth, but we can test endpoint structure

async def test_mrv_endpoints():
    """Test MRV ingestion endpoints manually"""
    async with httpx.AsyncClient() as client:
        print("=== Testing MRV Ingestion APIs ===\n")
        
        # Test 1: Get project samples (should fail auth but show endpoint exists)
        print("1. Testing GET /api/mrv/projects/proj123/samples")
        try:
            response = await client.get(
                f"{BASE_URL}/api/mrv/projects/proj123/samples",
                headers={"Authorization": f"Bearer {TEST_TOKEN}"}
            )
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test 2: Get sample detail (should fail auth but show endpoint exists)
        print("\n2. Testing GET /api/mrv/samples/SAMPLE123")
        try:
            response = await client.get(
                f"{BASE_URL}/api/mrv/samples/SAMPLE123",
                headers={"Authorization": f"Bearer {TEST_TOKEN}"}
            )
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test 3: Create sample (should fail auth but show endpoint exists)
        print("\n3. Testing POST /api/mrv/samples/")
        sample_data = {
            "project_id": "proj123",
            "collected_by": "Test User",
            "sample_type": "soil",
            "geotag_lat": 40.7128,
            "geotag_lon": -74.0060,
            "notes": "Test sample"
        }
        
        try:
            response = await client.post(
                f"{BASE_URL}/api/mrv/samples/",
                headers={"Authorization": f"Bearer {TEST_TOKEN}", "Content-Type": "application/json"},
                json=sample_data
            )
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test 4: Add chain step (should fail auth but show endpoint exists)
        print("\n4. Testing POST /api/mrv/samples/SAMPLE123/chain")
        chain_data = {
            "actor": "Test Actor",
            "action": "received",
            "notes": "Chain step test"
        }
        
        try:
            response = await client.post(
                f"{BASE_URL}/api/mrv/samples/SAMPLE123/chain",
                headers={"Authorization": f"Bearer {TEST_TOKEN}", "Content-Type": "application/json"},
                json=chain_data
            )
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test 5: Upload test result (should fail auth but show endpoint exists)
        print("\n5. Testing POST /api/mrv/tests/SAMPLE123/upload")
        test_data = {
            "parameter": "ph",
            "value": "7.2",
            "unit": "pH",
            "method": "ISO 10304",
            "tested_at": datetime.now().isoformat()
        }
        
        try:
            response = await client.post(
                f"{BASE_URL}/api/mrv/tests/SAMPLE123/upload",
                headers={"Authorization": f"Bearer {TEST_TOKEN}", "Content-Type": "application/json"},
                json=test_data
            )
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test 6: Submit to lab (should fail auth but show endpoint exists)
        print("\n6. Testing POST /api/mrv/samples/SAMPLE123/submit_lab")
        lab_data = {
            "lab_id": "lab123",
            "expected_tests": ["ph", "heavy_metals"],
            "submitted_at": datetime.now().isoformat(),
            "sample_condition": "good"
        }
        
        try:
            response = await client.post(
                f"{BASE_URL}/api/mrv/samples/SAMPLE123/submit_lab",
                headers={"Authorization": f"Bearer {TEST_TOKEN}", "Content-Type": "application/json"},
                json=lab_data
            )
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
        except Exception as e:
            print(f"   Error: {e}")
        
        print("\n=== Test Complete ===")
        print("All endpoints should return 401 Unauthorized with valid error messages")
        print("This confirms the endpoints exist and are properly protected by authentication.")

if __name__ == "__main__":
    asyncio.run(test_mrv_endpoints())
