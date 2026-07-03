from rest_framework import serializers
from .models import Alert, NotificationLog, AlertThreshold


class AlertSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Alert
        fields = ['id', 'patient', 'patient_name', 'alert_type', 'alert_type_display',
                  'severity', 'severity_display', 'status', 'status_display',
                  'description', 'location', 'latitude', 'longitude', 'sensor_data',
                  'created_at', 'acknowledged_at', 'resolved_at']
        read_only_fields = ['id', 'created_at', 'acknowledged_at', 'resolved_at']


class NotificationLogSerializer(serializers.ModelSerializer):
    method_display = serializers.CharField(source='get_method_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = NotificationLog
        fields = ['id', 'alert', 'guardian', 'method', 'method_display', 'status',
                  'status_display', 'message', 'recipient', 'sent_at', 'delivered_at',
                  'read_at', 'error_message', 'external_id']
        read_only_fields = ['id', 'sent_at', 'delivered_at', 'read_at']


class AlertThresholdSerializer(serializers.ModelSerializer):
    threshold_type_display = serializers.CharField(source='get_threshold_type_display', read_only=True)

    class Meta:
        model = AlertThreshold
        fields = ['id', 'patient', 'threshold_type', 'threshold_type_display',
                  'min_value', 'max_value', 'is_enabled', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AlertDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for alerts with notifications"""
    patient_name = serializers.SerializerMethodField()
    notifications = NotificationLogSerializer(many=True, read_only=True)
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Alert
        fields = ['id', 'patient', 'patient_name', 'alert_type', 'alert_type_display',
                  'severity', 'severity_display', 'status', 'status_display',
                  'description', 'location', 'latitude', 'longitude', 'sensor_data',
                  'notifications', 'created_at', 'acknowledged_at', 'resolved_at']
        read_only_fields = ['id', 'created_at', 'acknowledged_at', 'resolved_at']

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}"
