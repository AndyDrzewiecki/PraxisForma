# test_connection.py
print("🔍 Testing PraxisForma setup...")

# Test 1: Basic imports
try:
    from google.cloud import storage
    from google.cloud import videointelligence
    print("✅ Google Cloud packages imported successfully")
except ImportError as e:
    print(f"❌ Import error: {e}")
    exit(1)

# Test 2: Authentication 
try:
    client = storage.Client(project='throwpro')
    print("✅ Authentication working")
except Exception as e:
    print(f"❌ Authentication error: {e}")
    print("💡 Try running: gcloud auth application-default login")
    exit(1)

# Test 3: Access your bucket
try:
    bucket = client.bucket('praxisforma-videos')
    blobs = list(bucket.list_blobs(max_results=3))
    print(f"✅ Found {len(blobs)} files in praxisforma-videos bucket")
    for blob in blobs:
        print(f"   📹 {blob.name}")
except Exception as e:
    print(f"❌ Bucket access error: {e}")

print("\n🚀 Setup test complete!")
print("Ready for PraxisForma development! 🥏")