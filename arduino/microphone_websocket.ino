#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <mbedtls/base64.h>

const char *ssid = "NAVA-MAMA 5829";
const char *password = "D76?b492";

WebSocketsClient webSocket;

// Variables for repetitive sending
unsigned long lastSendTime = 0;
const unsigned long sendInterval = 50; // 50ms for faster response
bool isConnected = false;
unsigned long connectionTime = 0; // Track when connection was established

// Variables for receiving and processing audio data
String receivedAudioBase64 = "";
unsigned long receivedTimestamp = 0;
unsigned long lastDataReceivedTime = 0;
const unsigned long DATA_TIMEOUT = 2000; // 2 seconds timeout
bool hasAudioData = false;

// Audio processing variables
int processedVolume = 0;
int processedPeakToPeak = 0;
int audioRate = 44100;
int audioChannels = 1;
int audioChunkSize = 1024;

// Forward declarations
String base64Decode(String input);
void processAudioData(String audioData);

// Base64 decoding function using mbedtls
String base64Decode(String input)
{
    size_t inputLen = input.length();
    if (inputLen == 0)
    {
        return String("");
    }

    // Calculate output buffer size (base64 is 4/3 of input)
    size_t outputLen = (inputLen * 3) / 4;
    uint8_t *outputBuffer = (uint8_t *)malloc(outputLen);
    if (!outputBuffer)
    {
        Serial.println("❌ Failed to allocate memory for base64 decode");
        return String("");
    }

    size_t actualOutputLen = 0;
    int result = mbedtls_base64_decode(
        outputBuffer,
        outputLen,
        &actualOutputLen,
        (const unsigned char *)input.c_str(),
        inputLen);

    String output = "";
    if (result == 0)
    {
        // Convert byte array to String
        for (size_t i = 0; i < actualOutputLen; i++)
        {
            output += (char)outputBuffer[i];
        }
    }
    else
    {
        Serial.print("❌ Base64 decode failed with error: ");
        Serial.println(result);
    }

    free(outputBuffer);
    return output;
}

// Process audio data (int16 samples) and calculate volume and peak-to-peak
void processAudioData(String audioData)
{
    int dataLength = audioData.length();
    if (dataLength < 2)
    {
        processedVolume = 0;
        processedPeakToPeak = 0;
        return;
    }

    // Convert String to byte array (int16 samples)
    int16_t signalMax = -32768;
    int16_t signalMin = 32767;
    long sum = 0;
    int sampleCount = 0;

    // Process audio data as int16 samples (2 bytes per sample)
    for (int i = 0; i < dataLength - 1; i += 2)
    {
        // Combine two bytes into int16 (little-endian)
        int16_t sample = (int16_t)((uint8_t)audioData[i] | ((uint8_t)audioData[i + 1] << 8));

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

    // Calculate peak-to-peak amplitude
    processedPeakToPeak = signalMax - signalMin;

    // Calculate RMS-like value (average of absolute values)
    long avgAmplitude = sum / sampleCount;

    // Convert to volume (0-100 scale)
    // For 16-bit audio, map 0-6000 peak-to-peak to 0-100 volume
    if (processedPeakToPeak > 0)
    {
        processedVolume = map(processedPeakToPeak, 0, 6000, 0, 100);
        processedVolume = constrain(processedVolume, 0, 100);

        // Minimum threshold to eliminate background noise
        if (processedPeakToPeak < 100)
        {
            processedVolume = 0;
        }
    }
    else
    {
        processedVolume = 0;
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
        Serial.println("✅ Ready to receive and process raw audio data from server");

        // Identify as Arduino to server
        webSocket.sendTXT("{\"source\":\"arduino\",\"status\":\"connected\",\"type\":\"audio_processor\"}");
        Serial.println("📤 Sent identification message to server");

        // Request audio data from server
        delay(500); // Small delay to ensure connection is stable
        webSocket.sendTXT("{\"source\":\"arduino\",\"request\":\"audio_data\"}");
        Serial.println("📤 Sent request for audio data");
        break;

    case WStype_TEXT:
    {
        // Parse JSON with ArduinoJson
        StaticJsonDocument<4096> doc; // Adjust size based on your JSON payload
        DeserializationError error = deserializeJson(doc, (char *)payload, length);

        if (error)
        {
            Serial.print("❌ JSON parsing failed: ");
            Serial.println(error.c_str());
            break;
        }

        // Check if this message contains audio_data
        if (doc.containsKey("audio_data"))
        {
            const char *audioBase64 = doc["audio_data"];
            if (audioBase64)
            {
                Serial.print("📥 Received audio data (base64 length: ");
                Serial.print(strlen(audioBase64));
                Serial.println(")");

                // Extract metadata
                if (doc.containsKey("rate"))
                {
                    audioRate = doc["rate"];
                }
                if (doc.containsKey("chunk_size"))
                {
                    audioChunkSize = doc["chunk_size"];
                }
                if (doc.containsKey("channels"))
                {
                    audioChannels = doc["channels"];
                }
                if (doc.containsKey("timestamp"))
                {
                    receivedTimestamp = doc["timestamp"];
                }

                // Decode base64 and process audio
                String decodedAudio = base64Decode(String(audioBase64));
                processAudioData(decodedAudio);

                hasAudioData = true;
                lastDataReceivedTime = millis();

                Serial.print("🎤 Processed: Volume=");
                Serial.print(processedVolume);
                Serial.print(", PeakToPeak=");
                Serial.println(processedPeakToPeak);
            }
            else
            {
                Serial.println("⚠️ audio_data field is null");
            }
        }
        else
        {
            Serial.println("ℹ️ Message does not contain audio_data (might be status/heartbeat)");
        }
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

    // Connection status monitoring
    static unsigned long lastStatusCheck = 0;
    if (millis() - lastStatusCheck > 5000) // Every 5 seconds
    {
        if (!isConnected && WiFi.status() == WL_CONNECTED)
        {
            Serial.println("⏳ Waiting for WebSocket connection...");
        }
        lastStatusCheck = millis();
    }

    // Check if audio data has timed out and request new data
    static unsigned long lastRequestTime = 0;
    if (isConnected && (millis() - lastDataReceivedTime > DATA_TIMEOUT))
    {
        if (millis() - lastRequestTime > 5000) // Request every 5 seconds if no data
        {
            webSocket.sendTXT("{\"source\":\"arduino\",\"request\":\"audio_data\"}");
            Serial.println("📤 Requesting audio data from server...");
            lastRequestTime = millis();
        }
        if (hasAudioData)
        {
            hasAudioData = false;
            Serial.println("⚠️ Audio data timeout - no data received");
        }
    }

    // Process received audio data (if available)
    if (hasAudioData && (millis() - lastSendTime >= sendInterval))
    {
        // Display processed audio data
        Serial.print("📊 Processed Audio: Volume=");
        Serial.print(processedVolume);
        Serial.print(" | PeakToPeak=");
        Serial.print(processedPeakToPeak);
        Serial.print(" | Timestamp=");
        Serial.print(receivedTimestamp);
        Serial.print(" | Rate=");
        Serial.print(audioRate);
        Serial.print("Hz | Chunk=");
        Serial.print(audioChunkSize);
        Serial.println(" samples");

        // Here you can add your processing logic for the audio data
        // For example: control LEDs, motors, or other actuators based on volume

        // Example: Print volume level
        if (processedVolume > 50)
        {
            Serial.println("🔊 High volume detected!");
            // Add your high volume actions here (e.g., LED control, motor control)
        }
        else if (processedVolume > 20)
        {
            Serial.println("🔉 Medium volume");
            // Add your medium volume actions here
        }
        else if (processedVolume > 0)
        {
            Serial.println("🔈 Low volume");
            // Add your low volume actions here
        }
        else
        {
            Serial.println("🔇 Silent");
        }

        // Send processed data back to server via WebSocket
        if (isConnected)
        {
            char message[256];
            snprintf(
                message,
                sizeof(message),
                "{\"source\":\"arduino\",\"volume\":%d,\"peakToPeak\":%d,\"rate\":%d,\"chunk_size\":%d,\"channels\":%d,\"timestamp\":%lu}",
                processedVolume,
                processedPeakToPeak,
                audioRate,
                audioChunkSize,
                audioChannels,
                millis());

            webSocket.sendTXT(message);
            Serial.print("📤 Sent to server: ");
            Serial.println(message);
        }

        lastSendTime = millis();
    }
}
