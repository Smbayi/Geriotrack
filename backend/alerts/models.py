from django.db import models
from patients.models import Patient, Guardian

class Alert(models.Model):
    """Alert model for fall detection, health anomalies, etc."""
    ALERT_TYPE_CHOICES = [
        ('FALL', 'Fall Detection'),
        ('HEART_RATE', 'Abnormal Heart Rate'),
        ('ECG', 'ECG Anomaly'),
        ('INACTIVITY', 'Prolonged Inactivity'),
        ('FRAGILITY', 'Fragility Risk'),
        ('BATTERY', 'Low Battery'),
        ('GPS', 'GPS Signal Lost'),
    ]

    SEVERITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('RESOLVED', 'Resolved'),
        ('FALSE_ALARM', 'False Alarm'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    description = models.TextField()
    location = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    sensor_data = models.JSONField(default=dict)  # Store relevant sensor data
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.patient} ({self.severity})"


class NotificationLog(models.Model):
    """Log of notifications sent to guardians"""
    NOTIFICATION_METHOD_CHOICES = [
        ('SMS', 'SMS'),
        ('CALL', 'Phone Call'),
        ('EMAIL', 'Email'),
        ('PUSH', 'Push Notification'),
        ('BUZZER', 'Device Buzzer'),
    ]

    DELIVERY_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Failed'),
        ('READ', 'Read'),
    ]

    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name='notifications')
    guardian = models.ForeignKey(Guardian, on_delete=models.CASCADE, related_name='notifications')
    method = models.CharField(max_length=20, choices=NOTIFICATION_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=DELIVERY_STATUS_CHOICES, default='PENDING')
    message = models.TextField()
    recipient = models.CharField(max_length=100)  # Phone number, email, etc.
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    external_id = models.CharField(max_length=100, blank=True, null=True)  # For tracking with SMS API

    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['alert', '-sent_at']),
            models.Index(fields=['status', '-sent_at']),
        ]

    def __str__(self):
        return f"{self.get_method_display()} to {self.recipient} - {self.get_status_display()}"


class AlertThreshold(models.Model):
    """Custom alert thresholds per patient"""
    THRESHOLD_TYPE_CHOICES = [
        ('HEART_RATE', 'Heart Rate'),
        ('TEMP', 'Temperature'),
        ('INACTIVITY', 'Inactivity Duration'),
        ('FALL_SENSITIVITY', 'Fall Sensitivity'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='alert_thresholds')
    threshold_type = models.CharField(max_length=30, choices=THRESHOLD_TYPE_CHOICES)
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('patient', 'threshold_type')

    def __str__(self):
        return f"{self.patient} - {self.get_threshold_type_display()}"
