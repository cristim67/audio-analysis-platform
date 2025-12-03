#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>

const char *ssid = "NAVA-MAMA 5829";
const char *password = "D76?b492";

WebSocketsClient webSocket;

// Variables for repetitive sending
unsigned long lastSendTime = 0;
const unsigned long sendInterval = 100;      // Minimum 100ms between sends
const unsigned long forceSendInterval = 500; // Force send every 500ms even if no change
bool isConnected = false;
unsigned long connectionTime = 0; // Track when connection was established

// Delta tracking - only send when volume changes significantly
int lastSentVolume = -1;
int lastSentPeakToPeak = -1;
const int volumeDeltaThreshold = 3; // Only send if volume changed by 3% or more

// Variables for receiving and processing audio data
unsigned long receivedTimestamp = 0;
unsigned long lastDataReceivedTime = 0;
bool hasAudioData = false;

// Audio processing variables
int processedVolume = 0;
int processedPeakToPeak = 0;
int audioRate = 44100;
int audioChannels = 1;
int audioChunkSize = 1024; // Match Python client (100ms intervals)

// Static buffer for audio processing (no malloc/free - prevents memory fragmentation)
// 1024 samples * 2 bytes = 2048 bytes
#define MAX_AUDIO_BUFFER 2048
uint8_t audioBuffer[MAX_AUDIO_BUFFER];

// Forward declaration
void processAudioDataBytes(uint8_t *audioData, int dataLength);

// Process audio data from bytes (optimized - no String overhead)
void processAudioDataBytes(uint8_t *audioData, int dataLength)
{
    if (dataLength < 2)
    {
        processedVolume = 0;
        processedPeakToPeak = 0;
        return;
    }

    // Convert bytes to int16 samples
    int16_t signalMax = -32768;
    int16_t signalMin = 32767;
    long sum = 0;
    int sampleCount = 0;

    // Process audio data as int16 samples (2 bytes per sample)
    for (int i = 0; i < dataLength - 1; i += 2)
    {
        // Combine two bytes into int16 (little-endian)
        int16_t sample = (int16_t)(audioData[i] | (audioData[i + 1] << 8));

        sum += abs(sample);
        if (sample > signalMax)
            signalMax = sample;
        if (sample < signalMin)
            signalMin = sample;
        sampleCount++;
    }

    if (sampleCount == 0)
    {
        processedVolume = 0;
        processedPeakToPeak = 0;
        return;
    }

    // Calculate peak-to-peak amplitude (int16 range: 0 to 65535 max)
    processedPeakToPeak = signalMax - signalMin;

    // Convert to volume (0-100 scale)
    // int16 audio: peak-to-peak can be 0-65535
    // Normal speech/music: typically 1000-20000 peak-to-peak
    // Map 0-20000 to 0-100 for good sensitivity
    if (processedPeakToPeak > 100) // Noise floor threshold
    {
        // Map from 100-20000 to 0-100 (realistic audio range)
        processedVolume = map(processedPeakToPeak, 100, 20000, 0, 100);
        processedVolume = constrain(processedVolume, 0, 100);
    }
    else
    {
        processedVolume = 0; // Below noise floor
    }
}

void webSocketEvent(WStype_t type, uint8_t *payload, size_t length)
{
    switch (type)
    {
    case WStype_CONNECTED:
        Serial.println("✅ WebSocket connected!");
        Serial.print("📡 Connected to: ");
        if (length > 0)
        {
            Serial.println((char *)payload);
        }
        else
        {
            Serial.println("ngrok server");
        }
        isConnected = true;
        lastSendTime = millis();
        connectionTime = millis();
        Serial.println("✅ Ready to receive BINARY audio data from server");

        // Identify as Arduino to server
        webSocket.sendTXT("{\"source\":\"arduino\",\"status\":\"connected\",\"type\":\"audio_processor\"}");
        Serial.println("📤 Sent identification message to server");
        break;

    // BINARY message handler - FAST path (no JSON parsing!)
    case WStype_BIN:
    {
        // Binary protocol header (8 bytes):
        // - Byte 0: Message type (0x01 = audio from laptop)
        // - Bytes 1-4: Timestamp (uint32 little-endian)
        // - Bytes 5-6: Sample rate / 100 (uint16)
        // - Byte 7: Chunk size / 64
        // - Bytes 8+: Raw audio data

        if (length < 8)
        {
            break; // Invalid message
        }

        uint8_t msgType = payload[0];

        if (msgType == 0x01) // Laptop microphone audio
        {
            // Extract header (direct memory access - FAST)
            receivedTimestamp = payload[1] | (payload[2] << 8) | (payload[3] << 16) | (payload[4] << 24);
            audioRate = (payload[5] | (payload[6] << 8)) * 100;
            audioChunkSize = payload[7] * 64;

            // Audio data starts at byte 8
            int audioLength = length - 8;
            uint8_t *audioData = payload + 8;

            // Reduced logging for performance (only log every 40th packet)
            static int receiveCount = 0;
            if (++receiveCount % 40 == 0)
            {
                Serial.print("📥 BIN audio: ");
                Serial.print(audioLength);
                Serial.println(" bytes");
            }

            // Process directly from payload (zero-copy!)
            if (audioLength > 0 && audioLength <= MAX_AUDIO_BUFFER)
            {
                processAudioDataBytes(audioData, audioLength);
            }

            // Mark data as available (sending happens in loop() at fixed interval)
            hasAudioData = true;
            lastDataReceivedTime = millis();
        }
        break;
    }

    // TEXT message handler - for JSON control messages only
    case WStype_TEXT:
    {
        // Only handle control messages (heartbeat, status, etc.)
        // Audio data now comes via BINARY (much faster)
        // Silently ignore - no JSON parsing needed for audio
        break;
    }

    case WStype_DISCONNECTED:
        Serial.println("❌ WebSocket disconnected!");
        Serial.print("Reason: ");
        if (length > 0)
        {
            Serial.println((char *)payload);
        }
        else
        {
            Serial.println("Connection closed by server or network issue");
        }
        isConnected = false;
        break;

    case WStype_ERROR:
        Serial.print("❌ WebSocket error: ");
        if (length > 0)
        {
            Serial.print((char *)payload);
            Serial.print(" (length: ");
            Serial.print(length);
            Serial.println(")");
        }
        else
        {
            Serial.println("Unknown error - check SSL certificate or server availability");
        }
        isConnected = false;
        Serial.println("Will retry connection in 15 seconds...");
        break;

    case WStype_PING:
        Serial.println("📡 Ping received");
        break;

    case WStype_PONG:
        Serial.println("📡 Pong received");
        break;

    default:
        Serial.print("ℹ️ WebSocket event: ");
        Serial.print(type);
        if (length > 0)
        {
            Serial.print(" - ");
            Serial.println((char *)payload);
        }
        else
        {
            Serial.println();
        }
        break;
    }
}

void setup()
{
    Serial.begin(115200);
    delay(1000);

    Serial.println("🎤 Arduino Audio Processor");
    Serial.println("   Receives raw audio data via WebSocket");
    Serial.println("   Processes audio locally (volume, peak-to-peak)");
    Serial.println();

    Serial.println("Connecting to WiFi...");
    WiFi.begin(ssid, password);

    int timeout = 0;
    while (WiFi.status() != WL_CONNECTED && timeout < 20)
    {
        delay(500);
        Serial.print(".");
        timeout++;
    }

    Serial.println();

    if (WiFi.status() == WL_CONNECTED)
    {
        Serial.println("✅ Connected to WiFi!");
        Serial.print("IP: ");
        Serial.println(WiFi.localIP());

        // Connect to WebSocket server with SSL
        // beginSSL handles SSL automatically
        Serial.println("🔌 Configuring WebSocket connection...");
        Serial.print("   Host: tunnel.cristimiloiu.com");
        Serial.println(":443/ws");

        webSocket.beginSSL("tunnel.cristimiloiu.com", 443, "/ws");

        // Add header for ngrok (bypass warning page)
        webSocket.setExtraHeaders("ngrok-skip-browser-warning: true");

        webSocket.onEvent(webSocketEvent);
        // Longer reconnect interval to give SSL handshake time
        webSocket.setReconnectInterval(15000); // 15 seconds - ngrok can be slow

        // Enable debug output (if available in library)
        // webSocket.enableHeartbeat(15000, 3000, 2); // ping every 15s, timeout 3s, retry 2x

        Serial.println("🔌 Attempting WebSocket connection to server...");
        Serial.println("⏳ SSL handshake may take 10-15 seconds, please wait...");
        Serial.println("💡 Make sure:");
        Serial.println("   1. Server is running and sending raw audio data");
        Serial.println("   2. Server is sending audio data via WebSocket");
        Serial.println("   3. URL matches your server domain");
        Serial.println("🎤 Ready to receive and process raw audio data!");
    }
    else
    {
        Serial.println("❌ Could not connect to WiFi!");
    }
}

void loop()
{
    webSocket.loop(); // Must be called constantly

    // Smart send: only when volume changes significantly OR forced interval
    if (isConnected && hasAudioData && (millis() - lastSendTime >= sendInterval))
    {
        unsigned long timeSinceLastSend = millis() - lastSendTime;
        int volumeDelta = abs(processedVolume - lastSentVolume);

        // Send if:
        // 1. Volume changed significantly (delta >= threshold)
        // 2. OR forced update interval passed (keep-alive)
        // 3. OR first message (lastSentVolume == -1)
        bool shouldSend = (volumeDelta >= volumeDeltaThreshold) ||
                          (timeSinceLastSend >= forceSendInterval) ||
                          (lastSentVolume == -1);

        if (shouldSend)
        {
            char message[200];
            snprintf(
                message,
                sizeof(message),
                "{\"source\":\"arduino\",\"volume\":%d,\"peakToPeak\":%d,\"rate\":%d,\"chunk_size\":%d,\"timestamp\":%lu}",
                processedVolume,
                processedPeakToPeak,
                audioRate,
                audioChunkSize,
                millis());
            webSocket.sendTXT(message);

            lastSendTime = millis();
            lastSentVolume = processedVolume;
            lastSentPeakToPeak = processedPeakToPeak;
        }
    }

    // Watchdog: Check for free heap memory (prevent crashes)
    static unsigned long lastHeapCheck = 0;
    if (millis() - lastHeapCheck > 30000) // Every 30 seconds
    {
        uint32_t freeHeap = ESP.getFreeHeap();
        Serial.print("📡 Status: V=");
        Serial.print(processedVolume);
        Serial.print("% | Heap: ");
        Serial.print(freeHeap);
        Serial.println(" bytes");
        lastHeapCheck = millis();
    }
}
