from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

class Patient(models.Model):
    """Model for storing patient information"""
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    phone_number = models.CharField(max_length=20, unique=True)
    emergency_contact = models.CharField(max_length=100)
    emergency_phone = models.CharField(max_length=20)
    medical_conditions = models.TextField(blank=True, null=True)
    medications = models.TextField(blank=True, null=True)
    allergies = models.TextField(blank=True, null=True)
    device_id = models.CharField(max_length=100, unique=True)  # ESP32 device ID
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Patients"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Guardian(models.Model):
    """Model for storing guardian/caregiver information"""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='guardians')
    name = models.CharField(max_length=100)
    relationship = models.CharField(max_length=50)  # Son, Daughter, Nurse, etc.
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', '-created_at']

    def __str__(self):
        return f"{self.name} ({self.relationship})"


class PatientVitals(models.Model):
    """Baseline vitals for a patient"""
    patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name='baseline_vitals')
    resting_heart_rate = models.IntegerField(validators=[MinValueValidator(40), MaxValueValidator(150)])
    systolic_bp = models.IntegerField(validators=[MinValueValidator(80), MaxValueValidator(180)])
    diastolic_bp = models.IntegerField(validators=[MinValueValidator(40), MaxValueValidator(120)])
    body_temperature = models.FloatField(validators=[MinValueValidator(35), MaxValueValidator(40)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Patient Vitals"

    def __str__(self):
        return f"Vitals for {self.patient}"
