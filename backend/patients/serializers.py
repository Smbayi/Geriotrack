from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Patient, Guardian, PatientVitals


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class GuardianSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guardian
        fields = ['id', 'name', 'relationship', 'phone_number', 'email', 'is_primary', 'created_at']
        read_only_fields = ['id', 'created_at']


class PatientVitalsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientVitals
        fields = ['id', 'resting_heart_rate', 'systolic_bp', 'diastolic_bp', 'body_temperature', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class PatientListSerializer(serializers.ModelSerializer):
    """Serializer for listing patients"""
    user = UserSerializer(read_only=True)
    guardians_count = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = ['id', 'user', 'first_name', 'last_name', 'date_of_birth', 'gender',
                  'phone_number', 'device_id', 'is_active', 'guardians_count', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_guardians_count(self, obj):
        return obj.guardians.count()


class PatientDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for patient with all information"""
    user = UserSerializer(read_only=True)
    guardians = GuardianSerializer(many=True, read_only=True)
    baseline_vitals = PatientVitalsSerializer(read_only=True)
    age = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = ['id', 'user', 'first_name', 'last_name', 'date_of_birth', 'age',
                  'gender', 'phone_number', 'emergency_contact', 'emergency_phone',
                  'medical_conditions', 'medications', 'allergies', 'device_id',
                  'is_active', 'guardians', 'baseline_vitals', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_age(self, obj):
        from datetime import date
        today = date.today()
        return today.year - obj.date_of_birth.year - ((today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day))


class PatientCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new patients"""
    username = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, min_length=8)
    baseline_heart_rate = serializers.IntegerField(write_only=True)
    baseline_systolic = serializers.IntegerField(write_only=True)
    baseline_diastolic = serializers.IntegerField(write_only=True)
    baseline_temp = serializers.FloatField(write_only=True)

    class Meta:
        model = Patient
        fields = ['first_name', 'last_name', 'date_of_birth', 'gender', 'phone_number',
                  'emergency_contact', 'emergency_phone', 'medical_conditions', 'medications',
                  'allergies', 'device_id', 'username', 'email', 'password',
                  'baseline_heart_rate', 'baseline_systolic', 'baseline_diastolic', 'baseline_temp']

    def create(self, validated_data):
        # Extract user data
        username = validated_data.pop('username')
        email = validated_data.pop('email')
        password = validated_data.pop('password')

        # Extract vitals data
        baseline_heart_rate = validated_data.pop('baseline_heart_rate')
        baseline_systolic = validated_data.pop('baseline_systolic')
        baseline_diastolic = validated_data.pop('baseline_diastolic')
        baseline_temp = validated_data.pop('baseline_temp')

        # Create user
        user = User.objects.create_user(username=username, email=email, password=password)

        # Create patient
        patient = Patient.objects.create(user=user, **validated_data)

        # Create baseline vitals
        PatientVitals.objects.create(
            patient=patient,
            resting_heart_rate=baseline_heart_rate,
            systolic_bp=baseline_systolic,
            diastolic_bp=baseline_diastolic,
            body_temperature=baseline_temp
        )

        return patient
