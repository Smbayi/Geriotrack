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
