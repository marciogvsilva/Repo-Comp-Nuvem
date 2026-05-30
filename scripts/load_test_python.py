#!/usr/bin/env python3
"""Load testing script using Python (K6 alternative)"""

import asyncio
import time
import statistics
from typing import List
import httpx

BASE_URL = "http://localhost:8000"
CONCURRENT_USERS = 50
TEST_DURATION_SECONDS = 120
REQUESTS_PER_USER = 10

class LoadTestResults:
    def __init__(self):
        self.latencies: List[float] = []
        self.errors = 0
        self.success = 0
        self.start_time = time.time()

async def test_v1_offset(client: httpx.AsyncClient, results: LoadTestResults):
    """Test V1 offset pagination"""
    try:
        start = time.time()
        response = await client.get(f"{BASE_URL}/v1/produtos?limit=50&offset=0")
        latency = (time.time() - start) * 1000
        
        if response.status_code == 200:
            results.success += 1
            results.latencies.append(latency)
        else:
            results.errors += 1
    except Exception as e:
        results.errors += 1
        print(f"❌ Error in V1 offset: {e}")

async def test_v1_cursor(client: httpx.AsyncClient, results: LoadTestResults):
    """Test V1 cursor pagination"""
    try:
        start = time.time()
        response = await client.get(f"{BASE_URL}/v1/produtos/cursor?limit=50&cursor=0")
        latency = (time.time() - start) * 1000
        
        if response.status_code == 200:
            results.success += 1
            results.latencies.append(latency)
        else:
            results.errors += 1
    except Exception as e:
        results.errors += 1
        print(f"❌ Error in V1 cursor: {e}")

async def test_v2_offset(client: httpx.AsyncClient, results: LoadTestResults):
    """Test V2 offset pagination"""
    try:
        start = time.time()
        response = await client.get(f"{BASE_URL}/v2/produtos?limit=50&offset=0")
        latency = (time.time() - start) * 1000
        
        if response.status_code == 200:
            results.success += 1
            results.latencies.append(latency)
        else:
            results.errors += 1
    except Exception as e:
        results.errors += 1
        print(f"❌ Error in V2 offset: {e}")

async def test_headers_versioning(client: httpx.AsyncClient, results: LoadTestResults):
    """Test content negotiation via headers"""
    try:
        start = time.time()
        response = await client.get(
            f"{BASE_URL}/produtos?limit=50&offset=0",
            headers={"Accept": "application/vnd.api.v2+json"}
        )
        latency = (time.time() - start) * 1000
        
        if response.status_code == 200:
            results.success += 1
            results.latencies.append(latency)
        else:
            results.errors += 1
    except Exception as e:
        results.errors += 1
        print(f"❌ Error in headers versioning: {e}")

async def user_session(user_id: int, results: LoadTestResults):
    """Simulate a user making requests"""
    async with httpx.AsyncClient() as client:
        for _ in range(REQUESTS_PER_USER):
            # Randomly choose test
            test_choice = _ % 4
            if test_choice == 0:
                await test_v1_offset(client, results)
            elif test_choice == 1:
                await test_v1_cursor(client, results)
            elif test_choice == 2:
                await test_v2_offset(client, results)
            else:
                await test_headers_versioning(client, results)
            
            # Random delay
            await asyncio.sleep(0.1)

async def main():
    print("=" * 60)
    print("SSC0158 - REST API Load Test")
    print("=" * 60)
    print(f"\n🚀 Starting load test with {CONCURRENT_USERS} concurrent users")
    print(f"📊 Duration: {TEST_DURATION_SECONDS}s")
    print(f"📈 Requests per user: {REQUESTS_PER_USER}\n")
    
    results = LoadTestResults()
    
    # Create concurrent tasks
    tasks = [user_session(i, results) for i in range(CONCURRENT_USERS)]
    
    # Run all tasks
    await asyncio.gather(*tasks)
    
    # Calculate stats
    elapsed = time.time() - results.start_time
    total_requests = results.success + results.errors
    
    print("\n" + "=" * 60)
    print("📋 Test Results")
    print("=" * 60)
    print(f"✅ Successful requests: {results.success}")
    print(f"❌ Failed requests: {results.errors}")
    print(f"📊 Total requests: {total_requests}")
    print(f"⏱️  Elapsed time: {elapsed:.2f}s")
    print(f"🎯 RPS (requests/sec): {total_requests / elapsed:.2f}")
    
    if results.latencies:
        print(f"\n⏳ Latency Stats (ms):")
        print(f"  • Min: {min(results.latencies):.2f}ms")
        print(f"  • Max: {max(results.latencies):.2f}ms")
        print(f"  • Avg: {statistics.mean(results.latencies):.2f}ms")
        print(f"  • P95: {sorted(results.latencies)[int(len(results.latencies)*0.95)]:.2f}ms")
        print(f"  • P99: {sorted(results.latencies)[int(len(results.latencies)*0.99)]:.2f}ms")
    
    print(f"\n✅ Test completed!\n")

if __name__ == "__main__":
    asyncio.run(main())
