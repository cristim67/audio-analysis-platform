#!/usr/bin/env python3
"""
Microphone client - streams audio to server via WebSocket (binary protocol)
Sends at 250ms intervals for smooth, consistent streaming.
"""
import argparse
import asyncio
import queue
import struct
import sys
import threading
import time

try:
    import pyaudio
    import websockets
except ImportError as e:
    print(f"❌ Error: Missing dependency: {e}")
    print("📦 Install with: pip install pyaudio websockets")
    sys.exit(1)


class MicrophoneClient:
    def __init__(self, websocket_url: str):
        self.websocket_url = websocket_url
        self.websocket = None
        
        # Audio configuration
        self.CHUNK = 1024  # ~23ms of audio at 44100Hz (44100 * 0.023 ≈ 1024)
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 44100
        self.SEND_INTERVAL_MS = 100  # 100ms = 10 packets per second (smooth real-time)
        
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.send_count = 0
        self.running = True
        
        # Thread-safe queue for audio data
        self.audio_queue = queue.Queue(maxsize=10)
    
    def audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for audio stream - runs in separate thread"""
        if self.running:
            try:
                # Don't block if queue is full - drop old data
                if self.audio_queue.full():
                    try:
                        self.audio_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.audio_queue.put_nowait(in_data)
            except queue.Full:
                pass
        return (None, pyaudio.paContinue)
    
    def start_audio_stream(self) -> bool:
        """Start audio stream with callback (non-blocking)"""
        try:
            self.stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK,
                stream_callback=self.audio_callback
            )
            self.stream.start_stream()
            print("✅ Microphone started (non-blocking callback mode)")
            print(f"   Sample rate: {self.RATE} Hz")
            print(f"   Chunk size: {self.CHUNK} samples")
            print(f"   Send interval: {self.SEND_INTERVAL_MS}ms")
            return True
        except Exception as e:
            print(f"❌ Error starting microphone: {e}")
            return False
    
    async def connect_websocket(self) -> bool:
        """Connect to server via WebSocket"""
        try:
            print(f"🔌 Connecting to {self.websocket_url}...")
            
            additional_headers = {}
            if "ngrok" in self.websocket_url or "tunnel" in self.websocket_url:
                additional_headers["ngrok-skip-browser-warning"] = "true"
            
            self.websocket = await asyncio.wait_for(
                websockets.connect(
                    self.websocket_url,
                    additional_headers=additional_headers,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5
                ),
                timeout=10.0
            )
            print("✅ Connected to server!")
            return True
        except asyncio.TimeoutError:
            print(f"❌ Connection timeout after 10s")
            return False
        except Exception as e:
            print(f"❌ Connection error: {type(e).__name__}: {e}")
            return False
    
    async def send_audio_data(self, audio_data: bytes, timestamp: int) -> bool:
        """Send audio data via binary WebSocket protocol"""
        if not self.websocket:
            return False
        
        try:
            # Binary header: 8 bytes
            header = struct.pack('<BIHB',
                0x01,                          # Message type
                timestamp & 0xFFFFFFFF,        # Timestamp
                self.RATE // 100,              # Rate / 100
                self.CHUNK // 64               # Chunk / 64
            )
            
            await self.websocket.send(header + audio_data)
            return True
        except Exception as e:
            print(f"⚠️ Send error: {e}")
            try:
                await self.websocket.close()
            except:
                pass
            self.websocket = None
            return False
    
    async def run(self):
        """Main loop - smooth streaming at 250ms intervals"""
        if not self.start_audio_stream():
            return
        
        print("\n🎤 Audio streaming started...")
        print(f"📡 Sending every {self.SEND_INTERVAL_MS}ms")
        print("💡 Press Ctrl+C to stop\n")
        
        try:
            while self.running:
                # Connect if not connected
                if not self.websocket:
                    if not await self.connect_websocket():
                        print("⏳ Retry in 2s...")
                        await asyncio.sleep(2)
                        continue
                
                # Wait for interval
                await asyncio.sleep(self.SEND_INTERVAL_MS / 1000.0)
                
                # Get latest audio data from queue
                audio_data = None
                try:
                    # Get all available data, use the latest
                    while not self.audio_queue.empty():
                        audio_data = self.audio_queue.get_nowait()
                except queue.Empty:
                    pass
                
                if audio_data:
                    timestamp = int(time.time() * 1000)
                    success = await self.send_audio_data(audio_data, timestamp)
                    
                    if success:
                        self.send_count += 1
                        if self.send_count % 4 == 0:  # Log every second (4 * 250ms)
                            print(f"📤 Sent #{self.send_count}: {len(audio_data)} bytes")
                
        except KeyboardInterrupt:
            print("\n\n⏹️ Stopping...")
        finally:
            self.running = False
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup resources"""
        self.running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.audio:
            self.audio.terminate()
        if self.websocket:
            try:
                await self.websocket.close()
            except:
                pass
        print("✅ Resources released")


def main():
    parser = argparse.ArgumentParser(
        description="Microphone client - streams audio via WebSocket"
    )
    parser.add_argument(
        "--url", "-u",
        type=str,
        default="wss://tunnel.cristimiloiu.com/ws-microphone",
        help="WebSocket URL"
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=250,
        help="Send interval in ms (default: 250)"
    )
    
    args = parser.parse_args()
    
    if not args.url.startswith(('ws://', 'wss://')):
        print("⚠️ URL must start with ws:// or wss://")
        sys.exit(1)
    
    client = MicrophoneClient(args.url)
    client.SEND_INTERVAL_MS = args.interval
    
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\n✅ Shutdown complete")


if __name__ == "__main__":
    main()
