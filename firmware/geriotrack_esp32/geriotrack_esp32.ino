/*
 * GérioTrack — ESP32 + MPU6050 + DHT11 + GPS + ECG + SIM800L GSM
 * Seuil chute 50° · envoi 1 Hz · SMS/appels via file Django
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <TinyGPS++.h>
#include "DHT.h"
#include <cmath>

const char* ssid     = "MOI";
const char* password = "Elsa@202";
// Labo local (même Wi-Fi que le PC Django) :
// String djangoURL = "http://192.168.150.205:8000/api/recevoir/";
// Production Render (Internet requis) :
String djangoURL = "https://geriotrack.onrender.com/api/recevoir/";

#define DHTPIN 4
#define DHTTYPE DHT11
#define RXD_GPS 26
#define TXD_GPS 27
#define RXD_GSM 16
#define TXD_GSM 17
#define PIN_ECG 34
#define PIN_LO_PLUS 32
#define PIN_LO_MOINS 25
const int BUZZER_X = 12;
const int BUZZER_Y = 13;

DHT dht(DHTPIN, DHTTYPE);
Adafruit_MPU6050 mpu;
TinyGPSPlus gps;
HardwareSerial SerialGSM(2);

const float SEUIL_CHUTE_ANGLE = 50.0;
unsigned long dernierEnvoi = 0;
const unsigned long INTERVALLE_ENVOI = 1000;

bool alerteChuteActuelle = false;
float lastAngleX = 0, lastAngleY = 0;
sensors_event_t lastA, lastG, tempEvt;

// ECG AD8232 — ADC 12 bits, ligne de base ~2048
const int ECG_MID = 2048;
const int ECG_BUF_LEN = 80;
int ecgBuf[ECG_BUF_LEN];
int ecgBufIdx = 0;
int ecgBufCount = 0;
int ecgRaw = 0;
int ecgBpm = 0;
bool electrodesOk = false;
unsigned long dernierBattement = 0;
int seuilDetectionPic = 2200;
bool picDetecte = false;
unsigned long lastEcgSerial = 0;

String gsmReadAll(unsigned long timeoutMs = 3000) {
  String r = "";
  unsigned long t0 = millis();
  while (millis() - t0 < timeoutMs) {
    while (SerialGSM.available()) {
      char c = SerialGSM.read();
      r += c;
      t0 = millis();
    }
    delay(5);
  }
  return r;
}

bool gsmSendAT(String cmd, String expect = "OK", unsigned long timeout = 4000) {
  SerialGSM.println(cmd);
  String resp = gsmReadAll(timeout);
  Serial.print("GSM> "); Serial.println(cmd);
  if (resp.length()) Serial.println(resp);
  return resp.indexOf(expect) >= 0;
}

void gsmInit() {
  SerialGSM.begin(9600, SERIAL_8N1, RXD_GSM, TXD_GSM);
  delay(1500);
  gsmSendAT("AT");
  gsmSendAT("ATE0");
  gsmSendAT("AT+CMGF=1");  // SMS texte
  gsmSendAT("AT+CLIP=1");
  Serial.println("SIM800L pret.");
}

void gsmSendSMS(String phone, String msg) {
  phone.replace(" ", "");
  if (!gsmSendAT("AT+CMGF=1")) return;
  SerialGSM.print("AT+CMGS=\"");
  SerialGSM.print(phone);
  SerialGSM.println("\"");
  delay(400);
  SerialGSM.print(msg);
  SerialGSM.write(26);  // Ctrl+Z
  gsmReadAll(8000);
  Serial.println("SMS envoye -> " + phone);
}

void gsmCall(String phone) {
  phone.replace(" ", "");
  SerialGSM.print("ATD");
  SerialGSM.print(phone);
  SerialGSM.println(";");
  gsmReadAll(5000);
  Serial.println("Appel -> " + phone);
}

void processGsmCommands(String jsonBody) {
  int pos = jsonBody.indexOf("\"gsm_commands\"");
  if (pos < 0) return;
  int arrStart = jsonBody.indexOf('[', pos);
  if (arrStart < 0) return;

  int i = arrStart;
  while ((i = jsonBody.indexOf("\"channel\"", i)) > 0) {
    String channel = "";
    int cpos = jsonBody.indexOf(':', i);
    int q1 = jsonBody.indexOf('"', cpos + 1);
    int q2 = jsonBody.indexOf('"', q1 + 1);
    if (q1 > 0 && q2 > q1) channel = jsonBody.substring(q1 + 1, q2);

    String phone = "";
    int ppos = jsonBody.indexOf("\"phone\"", i);
    if (ppos > 0 && ppos < i + 200) {
      int pq1 = jsonBody.indexOf('"', jsonBody.indexOf(':', ppos) + 1);
      int pq2 = jsonBody.indexOf('"', pq1 + 1);
      if (pq1 > 0 && pq2 > pq1) phone = jsonBody.substring(pq1 + 1, pq2);
    }

    String message = "";
    int mpos = jsonBody.indexOf("\"message\"", i);
    if (mpos > 0 && mpos < i + 300) {
      int mq1 = jsonBody.indexOf('"', jsonBody.indexOf(':', mpos) + 1);
      int mq2 = jsonBody.indexOf('"', mq1 + 1);
      if (mq1 > 0 && mq2 > mq1) message = jsonBody.substring(mq1 + 1, mq2);
    }

    if (channel == "sms" && phone.length() > 5) {
      gsmSendSMS(phone, message.length() ? message : "Alerte GérioTrack");
    } else if (channel == "call" && phone.length() > 5) {
      gsmCall(phone);
    }
    i = q2 + 1;
  }
}

void updateEcg(unsigned long tempsActuel) {
  electrodesOk = (digitalRead(PIN_LO_PLUS) == 0) && (digitalRead(PIN_LO_MOINS) == 0);
  int valeurEcg = 0;

  if (electrodesOk) {
    valeurEcg = analogRead(PIN_ECG);
    if (valeurEcg > seuilDetectionPic && !picDetecte) {
      unsigned long intervalle = tempsActuel - dernierBattement;
      if (dernierBattement > 0 && intervalle > 400) {
        ecgBpm = constrain((int)(60000UL / intervalle), 45, 150);
        dernierBattement = tempsActuel;
        picDetecte = true;
      } else if (dernierBattement == 0) {
        dernierBattement = tempsActuel;
        picDetecte = true;
      }
    } else if (valeurEcg < (seuilDetectionPic - 200)) {
      picDetecte = false;
    }
  } else {
    valeurEcg = 0;
    ecgBpm = 0;
    picDetecte = false;
  }

  ecgRaw = valeurEcg;
  ecgBuf[ecgBufIdx] = valeurEcg;
  ecgBufIdx = (ecgBufIdx + 1) % ECG_BUF_LEN;
  if (ecgBufCount < ECG_BUF_LEN) ecgBufCount++;

  if (tempsActuel - lastEcgSerial >= 200) {
    lastEcgSerial = tempsActuel;
    Serial.printf("ECG adc=%d bpm=%d elec=%s\n", valeurEcg, ecgBpm, electrodesOk ? "OK" : "OFF");
  }
}

void appendEcgSamples(String& json) {
  json += "\"ecg_samples\":[";
  for (int i = 0; i < ecgBufCount; i++) {
    int idx = (ecgBufIdx - ecgBufCount + i + ECG_BUF_LEN) % ECG_BUF_LEN;
    if (i) json += ",";
    json += String(ecgBuf[idx]);
  }
  json += "],";
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  pinMode(BUZZER_X, OUTPUT);
  pinMode(BUZZER_Y, OUTPUT);
  pinMode(PIN_ECG, INPUT);
  pinMode(PIN_LO_PLUS, INPUT);
  pinMode(PIN_LO_MOINS, INPUT);
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
  noTone(BUZZER_X);
  noTone(BUZZER_Y);

  Serial.println("\n--- GérioTrack ESP32 + SIM800L + ECG ---");

  dht.begin();
  if (!mpu.begin()) Serial.println("MPU6050 non detecte !");
  else {
    mpu.setAccelerometerRange(MPU6050_RANGE_2_G);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    Serial.println("MPU6050 pret.");
  }

  Serial1.begin(9600, SERIAL_8N1, RXD_GPS, TXD_GPS);
  gsmInit();

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nWi-Fi OK");
  Serial.println(WiFi.localIP());
}

void loop() {
  unsigned long now = millis();

  mpu.getEvent(&lastA, &lastG, &tempEvt);
  lastAngleX = atan2(lastA.acceleration.x, sqrt(lastA.acceleration.y * lastA.acceleration.y + lastA.acceleration.z * lastA.acceleration.z)) * 180.0 / M_PI;
  lastAngleY = atan2(lastA.acceleration.y, sqrt(lastA.acceleration.x * lastA.acceleration.x + lastA.acceleration.z * lastA.acceleration.z)) * 180.0 / M_PI;

  bool chuteX = (abs(lastAngleX) > SEUIL_CHUTE_ANGLE);
  bool chuteY = (abs(lastAngleY) > SEUIL_CHUTE_ANGLE);
  if (chuteX) tone(BUZZER_X, 1200); else noTone(BUZZER_X);
  if (chuteY) tone(BUZZER_Y, 1500); else noTone(BUZZER_Y);
  alerteChuteActuelle = (chuteX || chuteY);

  while (Serial1.available() > 0) gps.encode(Serial1.read());
  updateEcg(now);

  if (now - dernierEnvoi >= INTERVALLE_ENVOI) {
    dernierEnvoi = now;

    float hum = dht.readHumidity();
    float tempAmb = dht.readTemperature();
    double lat = 0.0, lng = 0.0;
    if (gps.location.isValid()) {
      lat = gps.location.lat();
      lng = gps.location.lng();
    }

    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(djangoURL);
      http.addHeader("Content-Type", "application/json");

      String json = "{";
      json += "\"device_id\":\"ESP32-001\",";
      json += "\"temperature\":" + String(isnan(tempAmb) ? 0 : tempAmb, 1) + ",";
      json += "\"humidite\":" + String(isnan(hum) ? 0 : hum, 1) + ",";
      json += "\"chute\":" + String(alerteChuteActuelle ? "true" : "false") + ",";
      json += "\"angle_x\":" + String(lastAngleX, 2) + ",";
      json += "\"angle_y\":" + String(lastAngleY, 2) + ",";
      json += "\"accel_x\":" + String(lastA.acceleration.x, 3) + ",";
      json += "\"accel_y\":" + String(lastA.acceleration.y, 3) + ",";
      json += "\"accel_z\":" + String(lastA.acceleration.z, 3) + ",";
      json += "\"gyro_x\":" + String(lastG.gyro.x, 3) + ",";
      json += "\"gyro_y\":" + String(lastG.gyro.y, 3) + ",";
      json += "\"gyro_z\":" + String(lastG.gyro.z, 3) + ",";
      appendEcgSamples(json);
      json += "\"ecg_brut\":" + String(ecgRaw) + ",";
      json += "\"ecg_raw\":" + String(ecgRaw) + ",";
      json += "\"bpm\":" + String(ecgBpm) + ",";
      json += "\"electrodes_connectees\":" + String(electrodesOk ? "true" : "false") + ",";
      json += "\"latitude\":" + String(lat, 6) + ",";
      json += "\"longitude\":" + String(lng, 6);
      json += "}";

      int code = http.POST(json);
      if (code > 0) {
        String resp = http.getString();
        Serial.printf("OK %d | BPM=%d ECG=%d elec=%s chute=%d\n",
          code, ecgBpm, ecgRaw, electrodesOk ? "OK" : "OFF", alerteChuteActuelle);
        processGsmCommands(resp);
      } else {
        Serial.println(http.errorToString(code).c_str());
      }
      http.end();
    }
  }
  delay(10);
}
