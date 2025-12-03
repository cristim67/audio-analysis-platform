#!/usr/bin/env python3
"""
Client Python care capturează audio de la microfonul laptopului
și trimite datele prin WebSocket către server.

Serverul retransmite datele către Arduino prin WebSocket.

Folosește: python microphone_client.py --url ws://localhost:8000/ws-microphone
"""

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
    print(f"❌ Eroare: Lipsește dependența: {e}")
    print("📦 Instalează cu: pip install pyaudio numpy websockets")
    sys.exit(1)


class MicrophoneClient:
    def __init__(self, websocket_url: str):
        self.websocket_url = websocket_url
        self.websocket = None
        
        # Configurare audio
        self.CHUNK = 1024  # Număr de samples per chunk
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1  # Mono
        self.RATE = 44100  # Sample rate
        self.SEND_INTERVAL_MS = 200  # Similar cu Arduino
        
        self.audio = pyaudio.PyAudio()
        self.stream = None
        
    def calculate_volume(self, audio_data: np.ndarray) -> tuple:
        """Calculează volumul din datele audio"""
        # Convertim la numpy array dacă nu este deja
        if not isinstance(audio_data, np.ndarray):
            audio_data = np.frombuffer(audio_data, dtype=np.int16)
        
        # Calculăm amplitudinea peak-to-peak
        signal_max = int(np.max(audio_data))
        signal_min = int(np.min(audio_data))
        peak_to_peak = signal_max - signal_min
        
        # Calculăm RMS pentru o măsură mai precisă
        rms = np.sqrt(np.mean(audio_data**2))
        
        # Normalizăm RMS la 0-100 (16-bit audio: max RMS ~32768)
        volume = int((rms / 32768.0) * 100)
        volume = min(100, max(0, volume))
        
        # Threshold minim pentru a elimina zgomotul de fundal
        if peak_to_peak < 100:  # Ajustat pentru 16-bit audio
            volume = 0
        
        return volume, peak_to_peak
    
    def start_audio_stream(self) -> bool:
        """Pornește stream-ul audio"""
        try:
            self.stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            print("✅ Microfon pornit")
            print(f"   Sample rate: {self.RATE} Hz")
            print(f"   Chunk size: {self.CHUNK} samples")
            return True
        except Exception as e:
            print(f"❌ Eroare la pornirea microfonului: {e}")
            return False
    
    async def connect_websocket(self) -> bool:
        """Conectează la server prin WebSocket"""
        try:
            print(f"🔌 Conectare la {self.websocket_url}...")
            self.websocket = await websockets.connect(self.websocket_url)
            print("✅ Conectat la server!")
            return True
        except Exception as e:
            print(f"❌ Eroare la conectarea WebSocket: {e}")
            return False
    
    async def send_audio_data(self, volume: int, peak_to_peak: int, timestamp: int):
        """Trimite datele audio către server prin WebSocket"""
        if not self.websocket:
            return False
        
        # Format JSON similar cu Arduino
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
            print(f"⚠️ Eroare la trimiterea datelor: {e}")
            return False
    
    async def run(self):
        """Rulează bucla principală"""
        if not await self.connect_websocket():
            return
        
        if not self.start_audio_stream():
            return
        
        print("\n🎤 Capturarea audio a început...")
        print("💡 Apasă Ctrl+C pentru a opri\n")
        
        last_send_time = 0
        
        try:
            while True:
                current_time_ms = int(time.time() * 1000)
                
                # Citește audio data
                try:
                    audio_data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                except Exception as e:
                    print(f"⚠️ Eroare la citirea audio: {e}")
                    await asyncio.sleep(0.1)
                    continue
                
                # Trimite la fiecare interval
                if current_time_ms - last_send_time >= self.SEND_INTERVAL_MS:
                    volume, peak_to_peak = self.calculate_volume(audio_data)
                    
                    # Trimite către server
                    await self.send_audio_data(volume, peak_to_peak, current_time_ms)
                    
                    # Debug output
                    print(f"📊 Volume: {volume} | PeakToPeak: {peak_to_peak}")
                    
                    last_send_time = current_time_ms
                
                # Mic delay pentru a nu suprasolicita CPU
                await asyncio.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\n\n⏹️  Oprire...")
        except websockets.exceptions.ConnectionClosed:
            print("\n❌ Conexiunea WebSocket a fost închisă")
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
        description="Client pentru microfonul laptopului - trimite audio prin WebSocket"
    )
    parser.add_argument(
        "--url", "-u",
        type=str,
        default="ws://localhost:8000/ws-microphone",
        help="URL WebSocket server (default: ws://localhost:8000/ws-microphone)"
    )
    
    args = parser.parse_args()
    
    client = MicrophoneClient(args.url)
    
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\n✅ Oprire completă")


if __name__ == "__main__":
    main()

