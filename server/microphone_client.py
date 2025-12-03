#!/usr/bin/env python3
import argparse
import asyncio
import json
import sys
import time

try:
    import numpy as np
    import pyaudio
    import websockets
except ImportError as e:
    print(f"❌ Error: Missing dependency: {e}")
    print("📦 Install with: pip install pyaudio numpy websockets")
    sys.exit(1)


class MicrophoneClient:
    def __init__(self, websocket_url: str):
        self.websocket_url = websocket_url
        self.websocket = None
        
        # Audio configuration
        self.CHUNK = 1024  # Number of samples per chunk
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1  # Mono
        self.RATE = 44100  # Sample rate
        self.SEND_INTERVAL_MS = 200  # Similar to Arduino
        
        self.audio = pyaudio.PyAudio()
        self.stream = None
        
    def calculate_volume(self, audio_data: np.ndarray) -> tuple:
        """Calculate volume from audio data using peak-to-peak (similar to Arduino)"""
        # Convert to numpy array if not already
        if not isinstance(audio_data, np.ndarray):
            audio_data = np.frombuffer(audio_data, dtype=np.int16)
        
        # Handle empty or invalid audio data
        if len(audio_data) == 0:
            return 0, 0
        
        # Calculate peak-to-peak amplitude
        signal_max = int(np.max(audio_data))
        signal_min = int(np.min(audio_data))
        peak_to_peak = signal_max - signal_min
        
        # Use peak-to-peak for volume calculation (similar to Arduino)
        # Arduino maps 0-200 to 0-100 for 10-bit ADC (0-1024 range)
        # For 16-bit audio (0-65536 range), we'll use a higher threshold for better distribution
        volume = 0
        if peak_to_peak > 0:
            # Map peak-to-peak from 0-6000 to 0-100
            # This prevents saturation and gives better volume distribution
            # Adjust based on your microphone sensitivity
            volume = int((peak_to_peak / 6000.0) * 100)
            volume = min(100, max(0, volume))
            
            # Minimum threshold to eliminate background noise
            # Similar to Arduino: if amplitude < 3, set volume to 0
            # For 16-bit audio, threshold of ~100 corresponds to Arduino's threshold of 3
            if peak_to_peak < 100:
                volume = 0
        
        return volume, peak_to_peak
    
    def start_audio_stream(self) -> bool:
        """Start audio stream"""
        try:
            self.stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            print("✅ Microphone started")
            print(f"   Sample rate: {self.RATE} Hz")
            print(f"   Chunk size: {self.CHUNK} samples")
            return True
        except Exception as e:
            print(f"❌ Error starting microphone: {e}")
            return False
    
    async def connect_websocket(self) -> bool:
        """Connect to server via WebSocket"""
        try:
            print(f"🔌 Connecting to {self.websocket_url}...")
            
            # Headers for ngrok (bypass warning page)
            additional_headers = {}
            if "ngrok" in self.websocket_url:
                additional_headers["ngrok-skip-browser-warning"] = "true"
            
            self.websocket = await websockets.connect(
                self.websocket_url,
                additional_headers=additional_headers
            )
            print("✅ Connected to server!")
            return True
        except websockets.exceptions.InvalidURI:
            print(f"❌ Invalid URL: {self.websocket_url}")
            print("   Use: ws://localhost:8000/ws-microphone or wss://your-ngrok-url/ws-microphone")
            return False
        except websockets.exceptions.InvalidStatus as e:
            print(f"❌ Server rejected WebSocket connection: {e}")
            print(f"   HTTP Status: {e.status_code if hasattr(e, 'status_code') else 'Unknown'}")
            print("   Check:")
            print("   - If server is running")
            print("   - If path is correct (/ws-microphone)")
            print("   - If ngrok is exposing the server correctly")
            return False
        except ConnectionRefusedError:
            print(f"❌ Connection refused")
            print("   Check if server is running on the correct port")
            return False
        except Exception as e:
            print(f"❌ WebSocket connection error: {type(e).__name__}: {e}")
            return False
    
    async def send_audio_data(self, volume: int, peak_to_peak: int, timestamp: int):
        """Send audio data to server via WebSocket"""
        if not self.websocket:
            return False
        
        # JSON format similar to Arduino
        message = {
            "source": "laptop_microphone",
            "volume": volume,
            "peakToPeak": peak_to_peak,
            "timestamp": timestamp
        }
        
        try:
            await self.websocket.send(json.dumps(message))
            return True
        except Exception as e:
            print(f"⚠️ Error sending data: {e}")
            return False
    
    async def run(self):
        """Run main loop"""
        if not await self.connect_websocket():
            return
        
        if not self.start_audio_stream():
            return
        
        print("\n🎤 Audio capture started...")
        print("💡 Press Ctrl+C to stop\n")
        
        last_send_time = 0
        
        try:
            while True:
                current_time_ms = int(time.time() * 1000)
                
                # Read audio data
                try:
                    audio_data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                except Exception as e:
                    print(f"⚠️ Error reading audio: {e}")
                    await asyncio.sleep(0.1)
                    continue
                
                # Send at each interval
                if current_time_ms - last_send_time >= self.SEND_INTERVAL_MS:
                    volume, peak_to_peak = self.calculate_volume(audio_data)
                    
                    # Send to server
                    await self.send_audio_data(volume, peak_to_peak, current_time_ms)
                    
                    # Debug output
                    print(f"📊 Volume: {volume} | PeakToPeak: {peak_to_peak}")
                    
                    last_send_time = current_time_ms
                
                # Small delay to avoid overloading CPU
                await asyncio.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopping...")
        except websockets.exceptions.ConnectionClosed:
            print("\n❌ WebSocket connection closed")
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Curăță resursele"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.audio:
            self.audio.terminate()
        if self.websocket:
            await self.websocket.close()
        print("✅ Resurse eliberate")


def main():
    parser = argparse.ArgumentParser(
        description="Client for laptop microphone - sends audio via WebSocket"
    )
    parser.add_argument(
        "--url", "-u",
        type=str,
        default="wss://tunnel.cristimiloiu.com/ws-microphone",
        help="WebSocket server URL (default: wss://tunnel.cristimiloiu.com/ws-microphone)"
    )
    
    args = parser.parse_args()
    
    # Check URL format
    if not args.url.startswith(('ws://', 'wss://')):
        print("⚠️  URL must start with ws:// or wss://")
        print(f"   You provided: {args.url}")
        print(f"\n   Examples:")
        print(f"   python microphone_client.py --url ws://localhost:8000/ws-microphone")
        print(f"   python microphone_client.py --url wss://tunnel.cristimiloiu.com/ws-microphone")
        sys.exit(1)
    
    client = MicrophoneClient(args.url)
    
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\n✅ Shutdown complete")


if __name__ == "__main__":
    main()

