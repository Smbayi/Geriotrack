"""Fusion patients statiques + état live par patient (capteurs partagés ESP32)."""
from copy import deepcopy
from datetime import timedelta

from django.utils import timezone

from sensors.models import FallEvent, PatientLiveState
from sensors.services import get_active_patient_code, ONLINE_THRESHOLD_SEC, compute_fall_risk
from .patient_data import PATIENTS_BASE


def merge_patients_with_live():
    patients = deepcopy(PATIENTS_BASE)
    states = {s.patient_code: s for s in PatientLiveState.objects.all()}
    active = get_active_patient_code()

    recent_falls = set(
        FallEvent.objects.filter(
            detected_at__gte=timezone.now() - timedelta(hours=4),
            acknowledged=False,
        ).values_list('patient_code', flat=True)
    )

    now = timezone.now()
    for p in patients:
        pid = p['id']
        base_risk = float(p.get('risk') or 0.2)
        st = states.get(pid)
        if st:
            if st.temperature is not None:
                p['temp'] = round(st.temperature, 1)
            if st.humidity is not None:
                p['humid'] = round(st.humidity, 0)
            if st.latitude is not None and st.longitude is not None:
                p['lat'] = st.latitude
                p['lon'] = st.longitude
            age = (now - st.updated_at).total_seconds()
            p['sensor_online'] = age < ONLINE_THRESHOLD_SEC
            p['sensor_age'] = round(age, 1)
            p['angle_x'] = st.angle_x
            p['angle_y'] = st.angle_y
            p['accel_x'] = st.accel_x
            p['accel_y'] = st.accel_y
            p['accel_z'] = st.accel_z

            # Risque MPU en temps réel (colé à tous les patients)
            if st.fall_risk is not None:
                live_risk = float(st.fall_risk)
            else:
                live_risk = compute_fall_risk(st.angle_x, st.angle_y)
            # garde un plancher bas, mais laisse le MPU moniter le risque
            p['risk'] = round(max(base_risk * 0.35, live_risk), 3)

            if live_risk >= 0.85 or pid in recent_falls:
                p['statut'] = 'alert'
            elif live_risk >= 0.45:
                p['statut'] = 'warn'
            elif pid not in recent_falls:
                # ne forcer stable que s'il n'y a pas d'alerte chute
                if p.get('statut') == 'alert' and live_risk < 0.45:
                    p['statut'] = 'stable'
        elif pid in recent_falls:
            p['statut'] = 'alert'
            p['risk'] = max(base_risk, 0.85)

        if pid in recent_falls:
            p['statut'] = 'alert'
            p['risk'] = max(float(p.get('risk') or 0), 0.9)

        p['is_active_monitoring'] = (pid == active)

    return patients
