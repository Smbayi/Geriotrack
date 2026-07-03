from django.db import models
from patients.models import Patient

class FallPredictionModel(models.Model):
    """Fall detection and prediction model"""
    MODEL_STATUS_CHOICES = [
        ('TRAINING', 'Training'),
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
    ]

    version = models.CharField(max_length=50, unique=True)
    algorithm = models.CharField(max_length=100)  # e.g., "Random Forest", "Neural Network"
    status = models.CharField(max_length=20, choices=MODEL_STATUS_CHOICES, default='INACTIVE')
    accuracy = models.FloatField(null=True, blank=True)
    precision = models.FloatField(null=True, blank=True)
    recall = models.FloatField(null=True, blank=True)
    f1_score = models.FloatField(null=True, blank=True)
    model_file = models.FileField(upload_to='ml_models/')
    features_used = models.JSONField(default=list)  # List of features used
    training_date = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    training_samples = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-training_date']

    def __str__(self):
        return f"Fall Detection Model v{self.version}"


class FragilityPredictionModel(models.Model):
    """Motor fragility prediction model"""
    MODEL_STATUS_CHOICES = [
        ('TRAINING', 'Training'),
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
    ]

    version = models.CharField(max_length=50, unique=True)
    algorithm = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=MODEL_STATUS_CHOICES, default='INACTIVE')
    accuracy = models.FloatField(null=True, blank=True)
    precision = models.FloatField(null=True, blank=True)
    recall = models.FloatField(null=True, blank=True)
    f1_score = models.FloatField(null=True, blank=True)
    model_file = models.FileField(upload_to='ml_models/')
    features_used = models.JSONField(default=list)
    training_date = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    training_samples = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-training_date']
        verbose_name_plural = "Fragility Prediction Models"

    def __str__(self):
        return f"Fragility Model v{self.version}"


class PatientPrediction(models.Model):
    """Store predictions for individual patients"""
    FRAGILITY_LEVEL_CHOICES = [
        ('LOW', 'Low Risk'),
        ('MEDIUM', 'Medium Risk'),
        ('HIGH', 'High Risk'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='predictions')
    fall_risk_score = models.FloatField(validators=[])  # 0.0 to 1.0
    fragility_level = models.CharField(max_length=10, choices=FRAGILITY_LEVEL_CHOICES)
    confidence = models.FloatField()  # Confidence of the prediction
    fall_model_version = models.CharField(max_length=50)
    fragility_model_version = models.CharField(max_length=50)
    predicted_at = models.DateTimeField(auto_now_add=True)
    recommendation = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-predicted_at']
        indexes = [
            models.Index(fields=['patient', '-predicted_at']),
        ]

    def __str__(self):
        return f"Prediction for {self.patient}: Fall Risk {self.fall_risk_score:.2f}, Fragility {self.fragility_level}"


class TrainingData(models.Model):
    """Dataset used for training ML models"""
    dataset_name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='training_data/')
    samples_count = models.IntegerField()
    data_source = models.CharField(max_length=50)  # e.g., "Sensor", "Simulated", "Public"
    created_at = models.DateTimeField(auto_now_add=True)
    is_validated = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Training Data"

    def __str__(self):
        return self.dataset_name
