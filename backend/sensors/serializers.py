from rest_framework import serializers
from .models import ECGReading, AccelerometerGyroscope, TemperatureHumidity, GPSLocation


class ECGReadingSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = ECGReading
        fields = ['id', 'patient', 'patient_name', 'heart_rate', 'timestamp', 'raw_data', 'is_normal', 'notes']
        read_only_fields = ['id', 'timestamp']

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}"


class AccelerometerGyroscopeSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = AccelerometerGyroscope
        fields = ['id', 'patient', 'patient_name', 'accel_x', 'accel_y', 'accel_z',
                  'gyro_x', 'gyro_y', 'gyro_z', 'total_acceleration', 'timestamp']
        read_only_fields = ['id', 'timestamp']

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}"


class TemperatureHumiditySerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = TemperatureHumidity
        fields = ['id', 'patient', 'patient_name', 'temperature', 'humidity', 'timestamp']
        read_only_fields = ['id', 'timestamp']

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}"


class GPSLocationSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    coordinates = serializers.SerializerMethodField()

    class Meta:
        model = GPSLocation
        fields = ['id', 'patient', 'patient_name', 'latitude', 'longitude', 'altitude',
                  'accuracy', 'speed', 'coordinates', 'timestamp']
        read_only_fields = ['id', 'timestamp']

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}"

    def get_coordinates(self, obj):
        return {
            'type': 'Point',
            'coordinates': [obj.longitude, obj.latitude]
        }


class SensorDataBatchSerializer(serializers.Serializer):
    """Serializer for receiving batch sensor data from ESP32"""
    device_id = serializers.CharField()
    timestamp = serializers.DateTimeField()
    ecg_data = serializers.DictField(required=False)
    motion_data = serializers.DictField(required=False)
    env_data = serializers.DictField(required=False)
    gps_data = serializers.DictField(required=False)
