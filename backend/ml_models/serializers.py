from rest_framework import serializers
from .models import FallPredictionModel, FragilityPredictionModel, PatientPrediction, TrainingData


class FallPredictionModelSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = FallPredictionModel
        fields = ['id', 'version', 'algorithm', 'status', 'status_display', 'accuracy',
                  'precision', 'recall', 'f1_score', 'features_used', 'training_date',
                  'last_updated', 'training_samples']
        read_only_fields = ['id', 'training_date', 'last_updated']


class FragilityPredictionModelSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = FragilityPredictionModel
        fields = ['id', 'version', 'algorithm', 'status', 'status_display', 'accuracy',
                  'precision', 'recall', 'f1_score', 'features_used', 'training_date',
                  'last_updated', 'training_samples']
        read_only_fields = ['id', 'training_date', 'last_updated']


class PatientPredictionSerializer(serializers.ModelSerializer):
    fragility_level_display = serializers.CharField(source='get_fragility_level_display', read_only=True)
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = PatientPrediction
        fields = ['id', 'patient', 'patient_name', 'fall_risk_score', 'fragility_level',
                  'fragility_level_display', 'confidence', 'fall_model_version',
                  'fragility_model_version', 'predicted_at', 'recommendation']
        read_only_fields = ['id', 'predicted_at']

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}"


class TrainingDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingData
        fields = ['id', 'dataset_name', 'description', 'samples_count', 'data_source',
                  'created_at', 'is_validated']
        read_only_fields = ['id', 'created_at']


class PredictionStatisticsSerializer(serializers.Serializer):
    """Serializer for aggregated prediction statistics"""
    total_predictions = serializers.IntegerField()
    high_risk_count = serializers.IntegerField()
    medium_risk_count = serializers.IntegerField()
    low_risk_count = serializers.IntegerField()
    average_fall_risk = serializers.FloatField()
    fragility_breakdown = serializers.DictField()
