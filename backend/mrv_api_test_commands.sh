#!/bin/bash
# MRV Ingestion API Test Commands
# Run these commands to test all MRV ingestion endpoints

# Base URL (adjust as needed)
BASE_URL="http://localhost:8000"
AUTH_TOKEN="your_jwt_token_here"

echo "=== MRV Ingestion API Tests ==="
echo "Base URL: $BASE_URL"
echo "Auth Token: $AUTH_TOKEN"
echo ""

# 1. Create a new sample with evidence file
echo "1. Creating new sample with evidence file..."
curl -X POST "$BASE_URL/api/mrv/samples/" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "project_id=proj123" \
  -F "collected_by=John Doe" \
  -F "collected_at=2024-01-15T10:00:00Z" \
  -F "geotag_lat=40.7128" \
  -F "geotag_lon=-74.0060" \
  -F "sample_type=soil" \
  -F "notes=Sample from construction site A" \
  -F "evidence_file=@sample_evidence.jpg"
echo ""

# 2. Create a sample without evidence file
echo "2. Creating sample without evidence file..."
curl -X POST "$BASE_URL/api/mrv/samples/" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "project_id=proj123" \
  -F "collected_by=Jane Smith" \
  -F "sample_type=water" \
  -F "geotag_lat=40.7589" \
  -F "geotag_lon=-73.9851" \
  -F "notes=Water sample from river"
echo ""

# 3. Add chain of custody step
echo "3. Adding chain of custody step..."
curl -X POST "$BASE_URL/api/mrv/samples/SAMPLE123/chain" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "actor=Lab Technician" \
  -F "action=received_at_lab" \
  -F "timestamp=2024-01-15T14:00:00Z" \
  -F "notes=Sample received in good condition, properly labeled" \
  -F "evidence_file=@chain_evidence.jpg"
echo ""

# 4. Submit sample to laboratory
echo "4. Submitting sample to laboratory..."
curl -X POST "$BASE_URL/api/mrv/samples/SAMPLE123/submit_lab" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "lab_id=lab123" \
  -F "expected_tests=[\"ph\", \"heavy_metals\", \"organic_content\", \"nitrogen\"]" \
  -F "submitted_at=2024-01-15T15:00:00Z" \
  -F "sample_condition=good - no contamination visible"
echo ""

# 5. Upload test result with certificate
echo "5. Uploading test result with certificate..."
curl -X POST "$BASE_URL/api/mrv/tests/SAMPLE123/upload" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "parameter=ph" \
  -F "value=7.2" \
  -F "unit=pH" \
  -F "method=ISO 10304:2007" \
  -F "tested_at=2024-01-16T10:30:00Z" \
  -F "certificate_file=@test_certificate.pdf"
echo ""

# 6. Upload another test result
echo "6. Uploading heavy metals test result..."
curl -X POST "$BASE_URL/api/mrv/tests/SAMPLE123/upload" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "parameter=lead" \
  -F "value=0.05" \
  -F "unit=mg/kg" \
  -F "method=USEPA 3050B" \
  -F "tested_at=2024-01-16T11:00:00Z" \
  -F "certificate_file=@heavy_metals_cert.pdf"
echo ""

# 7. Upload test with QA issues (missing value)
echo "7. Uploading test with QA issues..."
curl -X POST "$BASE_URL/api/mrv/tests/SAMPLE456/upload" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "parameter=organic_content" \
  -F "value=" \
  -F "unit=%" \
  -F "method=ASTM D2974" \
  -F "tested_at=2024-01-16T12:00:00Z" \
  -F "certificate_file=@organic_cert.pdf"
echo ""

# 8. Get sample details with all related data
echo "8. Getting sample details..."
curl -X GET "$BASE_URL/api/mrv/samples/SAMPLE123" \
  -H "Authorization: Bearer $AUTH_TOKEN"
echo ""

# 9. Get samples for a project (paginated)
echo "9. Getting project samples..."
curl -X GET "$BASE_URL/api/mrv/projects/proj123/samples?page=1&size=10" \
  -H "Authorization: Bearer $AUTH_TOKEN"
echo ""

# 10. Get filtered samples by status
echo "10. Getting samples filtered by status..."
curl -X GET "$BASE_URL/api/mrv/projects/proj123/samples?status=in_lab&page=1&size=5" \
  -H "Authorization: Bearer $AUTH_TOKEN"
echo ""

# 11. Test with invalid file type (should fail)
echo "11. Testing invalid file type (should fail)..."
curl -X POST "$BASE_URL/api/mrv/tests/SAMPLE123/upload" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "parameter=ph" \
  -F "value=7.2" \
  -F "unit=pH" \
  -F "method=ISO 10304" \
  -F "certificate_file=@invalid_file.txt"
echo ""

# 12. Test with oversized file (should fail)
echo "12. Testing oversized file (should fail)..."
curl -X POST "$BASE_URL/api/mrv/samples/" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "project_id=proj123" \
  -F "collected_by=Test User" \
  -F "sample_type=soil" \
  -F "evidence_file=@large_file.jpg"
echo ""

# 13. Test with invalid project ID (should fail)
echo "13. Testing invalid project ID (should fail)..."
curl -X POST "$BASE_URL/api/mrv/samples/" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "project_id=invalid_project" \
  -F "collected_by=Test User" \
  -F "sample_type=soil"
echo ""

# 14. Test with invalid sample ID (should fail)
echo "14. Testing invalid sample ID (should fail)..."
curl -X GET "$BASE_URL/api/mrv/samples/INVALID_SAMPLE" \
  -H "Authorization: Bearer $AUTH_TOKEN"
echo ""

# 15. Test unauthorized access (should fail)
echo "15. Testing unauthorized access (should fail)..."
curl -X POST "$BASE_URL/api/mrv/samples/" \
  -H "Authorization: Bearer invalid_token" \
  -H "Content-Type: multipart/form-data" \
  -F "project_id=proj123" \
  -F "collected_by=Test User" \
  -F "sample_type=soil"
echo ""

echo "=== Test Complete ==="
echo "Check the responses above for any errors or issues."
