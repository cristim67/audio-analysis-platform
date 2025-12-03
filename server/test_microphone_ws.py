#!/usr/bin/env python3
"""
Test script for microphone WebSocket endpoint
"""
import asyncio
import sys

try:
    import websockets
except ImportError:
    print("❌ Package 'websockets' is not installed!")
    print("   Install with: pip3 install websockets")
    sys.exit(1)


async def test_microphone_websocket(url):
    """Test microphone WebSocket connection"""
    print(f"🔌 Testing microphone WebSocket: {url}...")
    
    # Headers for ngrok (bypass warning page)
    additional_headers = {}
    if "ngrok" in url:
        additional_headers["ngrok-skip-browser-warning"] = "true"
        print("   Using ngrok headers...")
    
    try:
        async with websockets.connect(
            url,
            additional_headers=additional_headers,
            ping_interval=15,
            ping_timeout=8
        ) as websocket:
            print("✅ Connected successfully!\n")
            
            # Wait for welcome message
            try:
                welcome = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📥 Welcome message: {welcome}\n")
            except asyncio.TimeoutError:
                print("⏱️  No welcome message received\n")
            
            # Send a test audio message
            test_message = '{"source":"laptop_microphone","volume":50,"peakToPeak":1000,"timestamp":1234567890}'
            print(f"📤 Sending test message: {test_message}")
            await websocket.send(test_message)
            
            # Wait a bit to see if we get any response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                print(f"📥 Response: {response}\n")
            except asyncio.TimeoutError:
                print("⏱️  No response (this is OK, server may not echo)\n")
            
            # Keep connection alive for a few seconds
            print("💤 Keeping connection alive for 10 seconds...")
            await asyncio.sleep(10)
            
            print("✅ Test successful!")
            
    except websockets.exceptions.InvalidURI:
        print(f"❌ Invalid URL: {url}")
    except websockets.exceptions.InvalidStatus as e:
        print(f"❌ Server rejected connection: {e}")
        print(f"   HTTP Status: {getattr(e, 'status_code', 'Unknown')}")
    except ConnectionRefusedError:
        print(f"❌ Connection refused - server may not be running")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def main():
    # Test local first
    print("=" * 60)
    print("TEST 1: Local connection")
    print("=" * 60)
    asyncio.run(test_microphone_websocket("ws://localhost:8000/ws-microphone"))
    
    print("\n" + "=" * 60)
    print("TEST 2: Ngrok connection")
    print("=" * 60)
    ngrok_url = "wss://tunnel.cristimiloiu.com/ws-microphone"
    asyncio.run(test_microphone_websocket(ngrok_url))


if __name__ == "__main__":
    main()

