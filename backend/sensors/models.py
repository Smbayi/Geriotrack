from django.db import models
from patients.models import Patient
from django.core.validators import MinValueValidator, MaxValueValidator

class ECGReading(models.Model):
    """ECG (Electrocardiogram) readings from the device"""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='ecg_readings')
    heart_rate = models.IntegerField(validators=[MinValueValidator(20), MaxValueValidator(200)])
    timestamp = models.DateTimeField(auto_now_add=True)
    raw_data = models.JSONField(default=list)  # Store raw ECG waveform data
    is_normal = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['patient', '-timestamp']),
        ]

    def __str__(self):
        return f"ECG for {self.patient} at {self.timestamp}"


class AccelerometerGyroscope(models.Model):
    """Motion data from accelerometer and gyroscope"""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='motion_data')

    # Accelerometer values (m/s²)
    accel_x = models.FloatField()
    accel_y = models.FloatField()
    accel_z = models.FloatField()

    # Gyroscope values (rad/s)
    gyro_x = models.FloatField()
    gyro_y = models.FloatField()
    gyro_z = models.FloatField()

    # Derived values
    total_acceleration = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['patient', '-timestamp']),
        ]

    def __str__(self):
        return f"Motion data for {self.patient} at {self.timestamp}"


class TemperatureHumidity(models.Model):
    """Temperature and humidity sensor readings"""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='env_data')
    temperature = models.FloatField(validators=[MinValueValidator(20), MaxValueValidator(50)])
    humidity = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = "Temperature and Humidity"
        indexes = [
            models.Index(fields=['patient', '-timestamp']),
        ]

    def __str__(self):
        return f"Env: {self.temperature}°C, {self.humidity}% at {self.timestamp}"


class GPSLocation(models.Model):
    """GPS location data for fall detection and tracking"""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='gps_locations')
    latitude = models.FloatField()
    longitude = models.FloatField()
    altitude = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)
    speed = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['patient', '-timestamp']),
        ]

    def __str__(self):
        return f"Location: ({self.latitude:.4f}, {self.longitude:.4f})"


class LiveSensorReading(models.Model):
    """Dernières valeurs reçues d'un appareil (ESP32) — sans compte Patient obligatoire."""
    device_id = models.CharField(max_length=100, unique=True)
    patient_code = models.CharField(max_length=20, blank=True, default='')  # ex: P001

    accel_x = models.FloatField(default=0)
    accel_y = models.FloatField(default=0)
    accel_z = models.FloatField(default=9.81)
    gyro_x = models.FloatField(default=0)
    gyro_y = models.FloatField(default=0)
    gyro_z = models.FloatField(default=0)
    total_acceleration = models.FloatField(default=1.0)

    temperature = models.FloatField(null=True, blank=True)
    humidity = models.FloatField(null=True, blank=True)

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    altitude = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)
    speed = models.FloatField(null=True, blank=True)

    raw_payload = models.JSONField(default=dict, blank=True)
    fall_detected = models.BooleanField(default=False)

    ecg_raw = models.IntegerField(null=True, blank=True)
    ecg_bpm = models.IntegerField(null=True, blank=True)
    ecg_mv = models.FloatField(null=True, blank=True)
    ecg_waveform = models.JSONField(default=list, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.device_id} → {self.patient_code or '?'} @ {self.updated_at}"


class DeviceReadingLog(models.Model):
    """Historique complet : chaque POST reçu de l'ESP32 est enregistré."""
    device_id = models.CharField(max_length=100, default='ESP32-001')
    patient_code = models.CharField(max_length=20, default='P001')
    temperature = models.FloatField(null=True, blank=True)
    humidity = models.FloatField(null=True, blank=True)
    fall_detected = models.BooleanField(default=False)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['patient_code', '-received_at']),
            models.Index(fields=['device_id', '-received_at']),
        ]

    def __str__(self):
        return f"{self.patient_code} @ {self.received_at:%Y-%m-%d %H:%M:%S}"


class FallEvent(models.Model):
    """Chute détectée (ESP32 ou simulation enregistrée)."""
    SOURCE_CHOICES = [
        ('esp32', 'ESP32'),
        ('simulated', 'Simulation'),
    ]
    patient_code = models.CharField(max_length=20)
    device_id = models.CharField(max_length=100, blank=True, default='')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='esp32')
    acknowledged = models.BooleanField(default=False)
    detected_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['patient_code', '-detected_at']),
        ]

    def __str__(self):
        return f"Chute {self.patient_code} @ {self.detected_at:%Y-%m-%d %H:%M}"


class MonitoringContext(models.Model):
    """Patient actuellement sélectionné pour la détection de chute (un seul ESP32)."""
    key = models.CharField(max_length=50, unique=True, default='default')
    active_patient_code = models.CharField(max_length=20, default='P001')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Surveillance → {self.active_patient_code}"


class PatientLiveState(models.Model):
    """État live par patient — capteurs partagés + GPS propre au patient surveillé."""
    patient_code = models.CharField(max_length=20, unique=True)
    temperature = models.FloatField(null=True, blank=True)
    humidity = models.FloatField(null=True, blank=True)
    angle_x = models.FloatField(null=True, blank=True)
    angle_y = models.FloatField(null=True, blank=True)
    accel_x = models.FloatField(null=True, blank=True)
    accel_y = models.FloatField(null=True, blank=True)
    accel_z = models.FloatField(null=True, blank=True)
    gyro_x = models.FloatField(null=True, blank=True)
    gyro_y = models.FloatField(null=True, blank=True)
    gyro_z = models.FloatField(null=True, blank=True)
    fall_risk = models.FloatField(null=True, blank=True)  # 0..1 selon angle / seuil 50°
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    sensor_online = models.BooleanField(default=False)
    ecg_raw = models.IntegerField(null=True, blank=True)
    ecg_bpm = models.IntegerField(null=True, blank=True)
    ecg_mv = models.FloatField(null=True, blank=True)
    ecg_status = models.CharField(max_length=20, blank=True, default='')
    ecg_waveform = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['patient_code']

    def __str__(self):
        return f"{self.patient_code} live"


class PatientMovementLog(models.Model):
    """Historique mouvement (axes X/Y) par patient — alimenté par l'ESP32 unique."""
    patient_code = models.CharField(max_length=20)
    angle_x = models.FloatField()
    angle_y = models.FloatField()
    accel_x = models.FloatField(null=True, blank=True)
    accel_y = models.FloatField(null=True, blank=True)
    device_id = models.CharField(max_length=100, default='ESP32-001')
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['patient_code', '-recorded_at']),
        ]


class GsmCommand(models.Model):
    """File d'attente : commandes SMS / appel pour le module SIM800L (ESP32)."""
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('sent', 'Envoyé'),
        ('failed', 'Échec'),
    ]
    CHANNEL_CHOICES = [
        ('sms', 'SMS'),
        ('call', 'Appel'),
    ]
    device_id = models.CharField(max_length=100, default='ESP32-001')
    patient_code = models.CharField(max_length=20, blank=True, default='')
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    phone = models.CharField(max_length=40)
    message = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    fall_event = models.ForeignKey(
        FallEvent, null=True, blank=True, on_delete=models.SET_NULL, related_name='gsm_commands'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['device_id', 'status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.channel} → {self.phone} ({self.status})"


class OutboundMessage(models.Model):
    """Messages SMS / appels — journal + déclenchement SIM800L."""
    CHANNEL_CHOICES = [
        ('sms', 'SMS'),
        ('call', 'Appel'),
    ]
    RECIPIENT_CHOICES = [
        ('medecin', 'Médecin'),
        ('famille', 'Famille'),
    ]
    patient_code = models.CharField(max_length=20)
    fall_event = models.ForeignKey(
        FallEvent, null=True, blank=True, on_delete=models.SET_NULL, related_name='messages'
    )
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default='sms')
    recipient_type = models.CharField(max_length=20, choices=RECIPIENT_CHOICES)
    recipient_name = models.CharField(max_length=120)
    recipient_phone = models.CharField(max_length=40)
    message_body = models.TextField()
    status = models.CharField(max_length=20, default='sent')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class AppNotification(models.Model):
    """Notifications cloche (dashboard / patients / géoloc)."""
    TYPE_CHOICES = [
        ('fall', 'Chute'),
        ('message', 'Message envoyé'),
        ('call', 'Appel'),
        ('email', 'E-mail'),
        ('gps', 'GPS'),
    ]
    patient_code = models.CharField(max_length=20, blank=True, default='')
    notif_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='fall')
    title = models.CharField(max_length=200)
    body = models.TextField()
    read = models.BooleanField(default=False)
    fall_event = models.ForeignKey(
        FallEvent, null=True, blank=True, on_delete=models.SET_NULL, related_name='notifications'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class OutboundEmail(models.Model):
    """E-mails envoyés par le logiciel (en parallèle SMS/appel GSM)."""
    patient_code = models.CharField(max_length=20)
    fall_event = models.ForeignKey(
        FallEvent, null=True, blank=True, on_delete=models.SET_NULL, related_name='emails'
    )
    recipient_type = models.CharField(max_length=20, default='famille')  # famille | medecin
    recipient_name = models.CharField(max_length=120)
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body_text = models.TextField()
    geo_url = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=20, default='sent')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Mail → {self.recipient_email} ({self.patient_code})"

