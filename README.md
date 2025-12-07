# Audio Analysis Platform - Real-Time Signal Processing

Platformă pentru analiza audio în timp real folosind ESP32, FastAPI și React. Sistemul capturează date audio de la un microfon conectat la ESP32, procesează semnalul în timp real și afișează analize detaliate într-un dashboard web modern.

## 🏗️ Arhitectură

```
┌─────────────────────────────────────────────────────────────────┐
│                         ESP32 Device                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  MAX4466 Microphone → ADC → FFT Analysis → WebSocket     │  │
│  │  - Sample Rate: 16kHz                                     │  │
│  │  - FFT Samples: 128                                       │  │
│  │  - Frequency Bands: 9 (0-8kHz)                             │  │
│  │  - Real-time filtering & SNR calculation                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │ WebSocket (WSS)
                             │ Port 443
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend Server                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  WebSocket Manager                                        │  │
│  │  - /ws (ESP32 endpoint)                                  │  │
│  │  - /ws-dashboard (Frontend endpoint)                     │  │
│  │  - Real-time data broadcasting                           │  │
│  │  - Connection management                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  REST API                                                │  │
│  │  - /api/info (System information)                        │  │
│  │  - CORS enabled                                           │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │ WebSocket (WSS)
                             │ HTTP/HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    React Frontend (Vite)                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Real-Time Dashboard                                     │  │
│  │  - Waveform Charts (RAW & FILTERED)                      │  │
│  │  - Spectrogram Visualization                            │  │
│  │  - Frequency Bands Display                                │  │
│  │  - Signal Quality Metrics (SNR)                          │  │
│  │  - Filter Controls (Low/High/Band-Pass)                  │  │
│  │  - Measurement Log                                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 📦 Componente

### ESP32 Firmware (`arduino/microphone_websocket.ino`)
- **Hardware**: ESP32 + MAX4466 Microphone
- **Funcționalități**:
  - Captură audio la 16kHz
  - Analiză FFT cu 9 benzi de frecvență
  - Filtrare în timp real (Low-Pass, High-Pass, Band-Pass)
  - Calcul SNR pentru RAW și FILTERED
  - Noise gate și calibrare automată
  - Comunicare WebSocket cu backend-ul

### Backend Server (`server/`)
- **Framework**: FastAPI (Python)
- **Funcționalități**:
  - WebSocket server pentru ESP32 și Dashboard
  - Broadcast în timp real către toate dashboard-urile
  - Management conexiuni
  - REST API pentru informații sistem
  - Logging structurat

### Frontend Dashboard (`client/`)
- **Framework**: React + TypeScript + Vite
- **UI**: Tailwind CSS
- **Funcționalități**:
  - Visualizări în timp real (waveform, spectrogram)
  - Control filtre audio (cutoff frequencies, voice boost)
  - Metrici calitate semnal (SNR)
  - Log măsurători
  - Status conexiuni (Dashboard & ESP32)

## 🚀 Rulare cu Docker

### Prerequisituri
- Docker
- Docker Compose

### Rulare completă

```bash
# Clonează repository-ul
git clone <repository-url>
cd psad-project

# Rulează toate serviciile
docker-compose up -d

# Verifică statusul
docker-compose ps

# Vezi logurile
docker-compose logs -f
```

### Accesare
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/api
- **Backend Health**: http://localhost:8000/api/health
- **Backend WebSocket**: ws://localhost:8000/ws (ESP32)
- **Dashboard WebSocket**: ws://localhost:8000/ws-dashboard

### Oprire
```bash
docker-compose down
```

## 🔧 Configurare Manuală

### Backend (FastAPI)

```bash
cd server
python -m venv venv
source venv/bin/activate  # Linux/Mac
# sau
venv\Scripts\activate  # Windows

pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend (React)

```bash
cd client
npm install
npm run dev
```

### ESP32

1. Deschide `arduino/microphone_websocket.ino` în Arduino IDE
2. Instalează bibliotecile necesare:
   - `WiFi` (built-in)
   - `WebSocketsClient` (de la Links2004)
3. Configurează WiFi credentials în cod
4. Configurează WebSocket host/port
5. Upload la ESP32

## 📊 Date și Metrici

### Date trimise de ESP32
- `volume`: Amplitudine RAW (0-100%)
- `volumeFiltered`: Amplitudine filtrată (0-100%)
- `peakToPeak`: Vârf la vârf (ADC units)
- `bands`: Array cu 9 benzi FFT (RAW)
- `bandsFiltered`: Array cu 9 benzi FFT (FILTERED)
- `snrRaw`: Signal-to-Noise Ratio RAW (dB)
- `snrFiltered`: Signal-to-Noise Ratio FILTERED (dB)
- `min`, `max`, `avg`: Valori ADC

### Filtre disponibile
- **Low-Pass**: Elimină frecvențe peste cutoff
- **High-Pass**: Elimină frecvențe sub cutoff
- **Band-Pass**: Păstrează frecvențe între 2 cutoff-uri
- **Voice Boost**: Amplificare pentru benzile vocale (500Hz-2500Hz)

## 🛠️ Tehnologii

- **ESP32**: Microcontroller cu WiFi
- **FastAPI**: Backend Python modern
- **React + TypeScript**: Frontend reactiv
- **WebSocket**: Comunicare bidirecțională în timp real
- **Tailwind CSS**: Styling modern
- **Vite**: Build tool rapid pentru frontend
- **Docker**: Containerizare și deployment

## 📝 Structură Proiect

```
psad-project/
├── arduino/              # Firmware ESP32
│   └── microphone_websocket.ino
├── server/               # Backend FastAPI
│   ├── app.py
│   ├── routes/          # API & WebSocket routes
│   ├── services/        # Business logic
│   ├── config/          # Configuration
│   └── requirements.txt
├── client/              # Frontend React
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── hooks/      # Custom hooks
│   │   └── services/   # API utilities
│   └── package.json
├── docker-compose.yml   # Docker orchestration
├── Dockerfile.backend   # Backend container
├── Dockerfile.frontend  # Frontend container
└── README.md
```

## 🔐 Variabile de Mediu

### Backend
Nu necesită variabile de mediu (configurare în cod)

### Frontend
Creează `.env` în `client/`:
```env
VITE_API_URL_FASTAPI=wss://your-backend-url.com
```

## 📈 Performanță

- **Sample Rate**: 16kHz
- **FFT Resolution**: 128 samples (~125Hz per bin)
- **Update Rate**: 350ms (configurabil)
- **Frequency Range**: 0-8kHz
- **Bands**: 9 benzi optimizate pentru voce umană

## 🐛 Troubleshooting

### ESP32 nu se conectează
- Verifică credentials WiFi
- Verifică WebSocket host/port
- Verifică că backend-ul rulează

### Frontend nu primește date
- Verifică conexiunea WebSocket în browser console
- Verifică că ESP32 trimite date
- Verifică CORS settings în backend

### Docker issues
- Verifică că porturile 3000 și 8000 sunt libere
- Verifică logurile: `docker-compose logs`

## 📄 Licență

Vezi `LICENSE` pentru detalii.

## 👤 Autor

Cristi Miloiu
