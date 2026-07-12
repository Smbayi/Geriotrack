"""Logique métier capteurs : données partagées, chute par patient sélectionné, messages."""
import logging
import math
import random
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from geriatrie_iot.patient_data import (
    PATIENTS_BASE, PATIENT_IDS, NOMS, get_patient,
    parse_contact, MEDECIN_PHONES, resolve_zone_from_gps, resolve_location_from_gps,
    KINSHASA_LAT_MIN, KINSHASA_LAT_MAX, KINSHASA_LON_MIN, KINSHASA_LON_MAX,
)
from .models import (
    LiveSensorReading, DeviceReadingLog, FallEvent, MonitoringContext,
    PatientLiveState, PatientMovementLog, OutboundMessage, AppNotification, OutboundEmail,
    GsmCommand,
)

logger = logging.getLogger(__name__)

DEFAULT_DEVICE_ID = 'ESP32-001'
ONLINE_THRESHOLD_SEC = 7
FALL_THRESHOLD_DEG = 50.0   # même seuil que l'ESP32 (SEUIL_CHUTE_ANGLE)
WARN_THRESHOLD_DEG = 30.0   # à partir de là le risque monte vite

# ECG AD8232 sur ESP32 (ADC 12 bits, midpoint ~2048)
ECG_ADC_MID = 2048
ECG_ADC_MAX = 4095
ECG_MV_SCALE = 1.65   # mV par unité normalisée
ECG_WAVEFORM_LEN = 80
ECG_BPM_MIN = 45
ECG_BPM_MAX = 130


def _absolute_url(path):
    """Transforme un chemin relatif en URL absolue pour les e-mails."""
    base = getattr(settings, 'PUBLIC_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
    if not path:
        return base
    if path.startswith('http://') or path.startswith('https://'):
        return path
    return f"{base}{path if path.startswith('/') else '/' + path}"


def build_analyse_url(patient_code):
    """Lien public vers le graphique ECG / analyse du patient."""
    return _absolute_url(f'/analyse/?patient={patient_code}#ecg')


def build_portail_login_url(target_path, patient_code=None, role='famille'):
    """
    Lien e-mail / alerte : page connexion portail puis redirection (carte, etc.).
    Ex. /portail/?next=/portail/carte/?patient=P001&role=famille&patient=P001
    """
    from urllib.parse import urlencode
    if not target_path.startswith('/'):
        target_path = '/' + target_path
    params = {'next': target_path, 'role': role or 'famille'}
    if patient_code:
        params['patient'] = patient_code
    return _absolute_url('/portail/?' + urlencode(params))


def build_carte_url(patient_code, portail=True, via_login=False):
    """Lien carte GPS. via_login=True pour e-mails famille (connexion puis carte)."""
    path = f'/portail/carte/?patient={patient_code}' if portail else f'/geolocalisation/?patient={patient_code}'
    if via_login and portail:
        return build_portail_login_url(path, patient_code=patient_code, role='famille')
    return _absolute_url(path)


def get_patient_gps(patient_code):
    """Coordonnées live ou position d'origine du patient."""
    st = PatientLiveState.objects.filter(patient_code=patient_code).first()
    home = get_patient(patient_code) or {}
    lat = st.latitude if st and st.latitude is not None else home.get('lat')
    lon = st.longitude if st and st.longitude is not None else home.get('lon')
    return lat, lon


def normalize_phone(phone):
    """Normalise un numéro pour SIM800L (format international)."""
    if not phone:
        return ''
    p = str(phone).strip().replace(' ', '').replace('-', '')
    if p.startswith('00'):
        p = '+' + p[2:]
    if p.startswith('0') and len(p) >= 9:
        p = '+243' + p[1:]
    if not p.startswith('+'):
        p = '+' + p
    return p


def calibrate_ecg_mv(raw_adc):
    """Convertit la valeur ADC brute en mV affichables (signal centré)."""
    if raw_adc is None:
        return 0.0
    centered = (float(raw_adc) - ECG_ADC_MID) / (ECG_ADC_MAX / 2.0)
    return round(centered * ECG_MV_SCALE, 3)


def classify_ecg_bpm(bpm):
    """Statut clinique simplifié pour personnes âgées."""
    if bpm is None:
        return 'unknown', 'En attente'
    b = int(bpm)
    if b < 50 or b > 110:
        return 'alert', 'Anormal'
    if b < 55 or b > 100:
        return 'warn', 'À surveiller'
    return 'normal', 'Normal'


def smooth_bpm(prev_bpm, new_bpm):
    """Lisse le BPM pour éviter les sauts (moniteur série instable)."""
    if new_bpm is None:
        return prev_bpm
    b = max(ECG_BPM_MIN, min(ECG_BPM_MAX, int(new_bpm)))
    if prev_bpm is None:
        return b
    return int(round(prev_bpm * 0.65 + b * 0.35))


def process_ecg_reading(raw_adc, bpm_device=None, prev_bpm=None, prev_waveform=None):
    """
    Calibre ECG : ADC → mV, BPM lissé, statut.
    prev_waveform : liste existante à laquelle ajouter le point.
    """
    waveform = list(prev_waveform or [])
    if raw_adc is not None:
        mv = calibrate_ecg_mv(raw_adc)
        waveform.append(mv)
        if len(waveform) > ECG_WAVEFORM_LEN:
            waveform = waveform[-ECG_WAVEFORM_LEN:]
    else:
        mv = None

    bpm = smooth_bpm(prev_bpm, bpm_device)
    status_key, status_label = classify_ecg_bpm(bpm)
    return {
        'ecg_raw': int(raw_adc) if raw_adc is not None else None,
        'ecg_mv': mv,
        'ecg_bpm': bpm,
        'ecg_status': status_key,
        'ecg_status_label': status_label,
        'ecg_waveform': waveform,
    }


def queue_gsm_command(device_id, channel, phone, message='', patient_code='', fall_event=None):
    """Ajoute une commande SIM800L dans la file (récupérée par l'ESP32)."""
    phone = normalize_phone(phone)
    if not phone:
        logger.warning('GSM ignoré : numéro vide (patient=%s)', patient_code)
        return None
    cmd = GsmCommand.objects.create(
        device_id=device_id or DEFAULT_DEVICE_ID,
        patient_code=patient_code or '',
        channel=channel,
        phone=phone,
        message=message or '',
        fall_event=fall_event,
        status='pending',
    )
    logger.info('GSM en file → %s %s (%s)', channel, phone, patient_code)
    return cmd


def _send_sms_via_http_api(phone, message):
    """
    Envoi SMS via API HTTP (passerelle SMS).
    Retourne 'sent' | 'failed' | 'skipped' (non configuré).
    """
    url = (getattr(settings, 'SMS_API_URL', '') or '').strip()
    if not url:
        return 'skipped'
    api_key = (getattr(settings, 'SMS_API_KEY', '') or '').strip()
    sender = getattr(settings, 'SMS_API_SENDER', 'GerioTrack')
    try:
        import json
        import urllib.request
        payload = {
            'to': phone,
            'message': message,
            'sender': sender,
            'api_key': api_key,
        }
        data = json.dumps(payload).encode('utf-8')
        headers = {'Content-Type': 'application/json', 'User-Agent': 'GerioTrack/1.0'}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=10) as resp:
            if 200 <= resp.status < 300:
                logger.info('SMS API HTTP envoyé → %s', phone)
                return 'sent'
            logger.warning('SMS API HTTP code %s → %s', resp.status, phone)
            return 'failed'
    except Exception as exc:
        logger.warning('SMS API HTTP échec → %s : %s', phone, exc)
        return 'failed'


def _deliver_sms(phone, message, device_id=None, patient_code='', fall_event=None):
    """Transport SMS : API HTTP si configurée, sinon file SIM800L."""
    phone = normalize_phone(phone)
    msg = (message or '').strip()
    if not phone or not msg:
        return {
            'ok': False,
            'status': 'failed',
            'channel': 'sms',
            'http_sent': False,
            'gsm_queued': False,
            'error': 'Numéro ou message vide',
        }

    http_status = _send_sms_via_http_api(phone, msg[:480])
    if http_status == 'sent':
        return {
            'ok': True,
            'status': 'sent',
            'channel': 'sms_api',
            'http_sent': True,
            'gsm_queued': False,
            'phone': phone,
        }

    gsm = queue_gsm_command(
        device_id or DEFAULT_DEVICE_ID, 'sms', phone, msg[:160],
        patient_code=patient_code, fall_event=fall_event,
    )
    return {
        'ok': bool(gsm) or http_status == 'skipped',
        'status': 'queued' if gsm else 'failed',
        'channel': 'sms_gsm',
        'http_sent': False,
        'gsm_queued': bool(gsm),
        'phone': phone,
        'http_skipped': http_status == 'skipped',
    }


def send_sms(
    phone, message, patient_code='', device_id=None, fall_event=None,
    recipient_type='famille', recipient_name='', log=True,
):
    """
    Envoi SMS unifié — API HTTP + repli SIM800L ESP32.
    POST /api/sms/send/ utilise cette fonction.
    """
    delivery = _deliver_sms(
        phone, message, device_id=device_id,
        patient_code=patient_code, fall_event=fall_event,
    )
    msg_record_id = None
    if log and delivery.get('phone'):
        rec = OutboundMessage.objects.create(
            patient_code=patient_code or '',
            fall_event=fall_event,
            channel=delivery.get('channel', 'sms'),
            recipient_type=recipient_type,
            recipient_name=recipient_name or recipient_type,
            recipient_phone=delivery['phone'],
            message_body=(message or '').strip(),
            status=delivery.get('status', 'failed'),
        )
        msg_record_id = rec.id
        delivery['message_id'] = msg_record_id
    return delivery


def resolve_sms_recipient(patient_code, recipient_type, phone_override=''):
    """Résout nom + téléphone pour un envoi SMS."""
    patient = get_patient(patient_code)
    if not patient:
        return None, None, None
    nom = NOMS.get(patient_code, patient_code)
    if phone_override:
        phone = normalize_phone(phone_override)
        if recipient_type == 'medecin':
            return patient.get('medecin', 'Médecin'), phone, nom
        if recipient_type == 'famille':
            fname, _ = parse_contact(patient.get('contact', ''))
            return fname or 'Famille', phone, nom
        return 'Patient', phone, nom

    if recipient_type == 'medecin':
        rname = patient.get('medecin', 'Médecin')
        rphone = MEDECIN_PHONES.get(rname, '+243 81 000 0000')
        return rname, rphone, nom

    if recipient_type == 'famille':
        from geriatrie_iot.family_data import get_family_for_patient
        fname, fphone = parse_contact(patient.get('contact', ''))
        fam = get_family_for_patient(patient_code)
        if fam and fam.get('phone'):
            fphone = fam['phone']
        return fname or (fam['name'] if fam else 'Famille'), fphone, nom

    return nom, '', nom


def dispatch_family_portal_message(patient_code, action, message=None, family_id=None, device_id=None):
    """
    Messages portail famille : SMS réel + notification médecin sur plateforme.
    action: location_sms | message_medecin | message_patient
    """
    patient = get_patient(patient_code)
    if not patient:
        return {'ok': False, 'error': 'Patient inconnu'}

    nom = NOMS.get(patient_code, patient_code)
    lat, lon = get_patient_gps(patient_code)
    loc = resolve_location_from_gps(lat, lon)
    zone = loc['label'] or patient.get('chambre', 'Kinshasa')
    heure = timezone.now().astimezone().strftime('%d/%m/%Y à %H:%M')
    geo_url = build_carte_url(patient_code, portail=True, via_login=True)
    geo_carte_sms = build_carte_url(patient_code, portail=True, via_login=False)
    gps_line = f'GPS {lat:.5f}, {lon:.5f}' if lat is not None and lon is not None else ''
    dev = device_id or DEFAULT_DEVICE_ID
    text = (message or '').strip()

    if action == 'location_sms':
        body = (
            f'Position {nom} ({heure}) — {zone}. {gps_line}\n'
            f'Carte : {geo_url}'
        )
        rname, rphone, _ = resolve_sms_recipient(patient_code, 'famille')
        sms = send_sms(rphone, body[:480], patient_code=patient_code, device_id=dev,
                       recipient_type='famille', recipient_name=rname)
        sms['zone'] = zone
        sms['geo_url'] = geo_url
        return sms

    if action == 'message_medecin':
        body = text or f'La famille demande des nouvelles de {nom} ({heure}).'
        medecin = patient.get('medecin', 'Médecin')
        med_phone = MEDECIN_PHONES.get(medecin, '+243 81 000 0000')
        AppNotification.objects.create(
            patient_code=patient_code,
            notif_type='message',
            title=f'Famille — {nom}',
            body=f'{body} · {zone}'[:500],
        )
        OutboundMessage.objects.create(
            patient_code=patient_code,
            channel='app',
            recipient_type='medecin',
            recipient_name=medecin,
            recipient_phone=med_phone or '—',
            message_body=body,
            status='delivered',
        )
        return {'ok': True, 'status': 'delivered', 'channel': 'app', 'zone': zone}

    if action == 'message_patient':
        body = text or f'Votre famille vous envoie un message ({heure}).'
        OutboundMessage.objects.create(
            patient_code=patient_code,
            channel='app',
            recipient_type='patient',
            recipient_name=nom,
            recipient_phone='—',
            message_body=body,
            status='delivered',
        )
        return {'ok': True, 'status': 'delivered', 'channel': 'app', 'zone': zone}

    return {'ok': False, 'error': f'Action inconnue : {action}'}


def pop_pending_gsm_commands(device_id, limit=5):
    """Retourne et marque comme envoyées les commandes GSM en attente."""
    qs = GsmCommand.objects.filter(
        device_id=device_id,
        status='pending',
    ).order_by('created_at')[:limit]
    out = []
    now = timezone.now()
    for cmd in qs:
        out.append({
            'id': cmd.id,
            'channel': cmd.channel,
            'phone': cmd.phone,
            'message': cmd.message,
            'patient_code': cmd.patient_code,
        })
        cmd.status = 'sent'
        cmd.sent_at = now
        cmd.save(update_fields=['status', 'sent_at'])
    return out


def _send_real_email(subject, body, to_email):
    """
    Envoi SMTP réel. Retourne 'sent' | 'failed' | 'skipped'.
    skipped = mot de passe SMTP non configuré.
    """
    if not to_email:
        return 'skipped'
    password = (getattr(settings, 'EMAIL_HOST_PASSWORD', '') or '').strip()
    if not password:
        logger.warning(
            'E-mail NON envoyé (SMTP non configuré). '
            'Renseignez EMAIL_HOST_PASSWORD dans backend/.env'
        )
        return 'skipped'
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            fail_silently=False,
        )
        logger.info('E-mail envoyé → %s | %s', to_email, subject)
        return 'sent'
    except Exception as exc:
        logger.exception('Échec envoi e-mail → %s : %s', to_email, exc)
        return 'failed'


def compute_fall_risk(angle_x=None, angle_y=None, total_g=None, fall=False):
    """
    Risque 0..1 selon l'orientation MPU6050.
    Plus |angle| approche 50°, plus le risque monte (pour tous les patients).
    """
    if fall:
        return 0.97
    ax = abs(float(angle_x or 0.0))
    ay = abs(float(angle_y or 0.0))
    max_angle = max(ax, ay)

    if max_angle >= FALL_THRESHOLD_DEG:
        risk = 0.95
    elif max_angle >= WARN_THRESHOLD_DEG:
        # 30° → 0.42 , 50° → 0.95
        t = (max_angle - WARN_THRESHOLD_DEG) / (FALL_THRESHOLD_DEG - WARN_THRESHOLD_DEG)
        risk = 0.42 + t * 0.53
    else:
        # 0° → 0.08 , 40° → 0.40
        t = max_angle / WARN_THRESHOLD_DEG if WARN_THRESHOLD_DEG else 0
        risk = 0.08 + t * 0.32

    if total_g is not None and total_g > 1.85:
        risk = min(0.98, risk + 0.08)
    return round(risk, 3)


def ensure_patient_states(force_home_positions=False):
    """
    Crée l'état live de chaque patient.
    force_home_positions=True → réapplique les coords distinctes de PATIENTS_BASE
    (utile après qu'un GPS ESP32 a écrasé plusieurs patients).
    """
    for p in PATIENTS_BASE:
        state, created = PatientLiveState.objects.get_or_create(
            patient_code=p['id'],
            defaults={
                'latitude': p.get('lat'),
                'longitude': p.get('lon'),
            },
        )
        if created:
            continue
        # Position manquante OU réinitialisation demandée
        if force_home_positions or state.latitude is None or state.longitude is None:
            state.latitude = p.get('lat')
            state.longitude = p.get('lon')
            state.save(update_fields=['latitude', 'longitude', 'updated_at'])


def init_distinct_positions():
    """Réinitialise chaque patient à une position aléatoire distincte dans Kinshasa."""
    used = []
    rows = []
    for p in PATIENTS_BASE:
        for _ in range(40):
            lat = round(random.uniform(KINSHASA_LAT_MIN, KINSHASA_LAT_MAX), 6)
            lon = round(random.uniform(KINSHASA_LON_MIN, KINSHASA_LON_MAX), 6)
            key = (round(lat, 4), round(lon, 4))
            if key not in used:
                used.append(key)
                break
        p['lat'] = lat
        p['lon'] = lon
        zone = resolve_zone_from_gps(lat, lon) or p['chambre']
        state, _ = PatientLiveState.objects.get_or_create(patient_code=p['id'])
        state.latitude = lat
        state.longitude = lon
        state.save(update_fields=['latitude', 'longitude', 'updated_at'])
        rows.append({
            'id': p['id'],
            'nom': f"{p['prenom']} {p['nom']}",
            'chambre': zone,
            'lat': lat,
            'lon': lon,
        })
    return rows


def get_active_patient_code():
    ensure_patient_states()
    ctx, _ = MonitoringContext.objects.get_or_create(key='default')
    return ctx.active_patient_code


def set_active_patient_code(patient_code):
    if patient_code not in PATIENT_IDS:
        raise ValueError(f'Patient inconnu : {patient_code}')
    ensure_patient_states()
    ctx, _ = MonitoringContext.objects.get_or_create(key='default')
    ctx.active_patient_code = patient_code
    ctx.save(update_fields=['active_patient_code', 'updated_at'])
    return ctx.active_patient_code


def _num(data, *keys, default=None):
    if not isinstance(data, dict):
        return default
    for k in keys:
        if k in data and data[k] is not None:
            try:
                return float(data[k])
            except (TypeError, ValueError):
                pass
    return default


def _bool_val(data, *keys, default=False):
    if not isinstance(data, dict):
        return default
    for k in keys:
        if k in data:
            v = data[k]
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.lower() in ('true', '1', 'oui', 'yes')
            return bool(v)
    return default


def parse_esp_payload(payload):
    motion = payload.get('motion') or payload.get('motion_data') or {}
    env = payload.get('env') or payload.get('env_data') or {}
    gps = payload.get('gps') or payload.get('gps_data') or {}

    temperature = _num(payload, 'temperature', 'temp', 't')
    humidity = _num(payload, 'humidite', 'humidity', 'hum', 'h')
    if temperature is None:
        temperature = _num(env, 'temperature', 'temp', 't')
    if humidity is None:
        humidity = _num(env, 'humidite', 'humidity', 'hum', 'h')

    fall = _bool_val(payload, 'chute', 'fall', 'fall_detected')

    angle_x = _num(payload, 'angle_x', 'angleX')
    angle_y = _num(payload, 'angle_y', 'angleY')
    if angle_x is None:
        angle_x = _num(motion, 'angle_x', 'angleX', default=0.0)
    if angle_y is None:
        angle_y = _num(motion, 'angle_y', 'angleY', default=0.0)

    ax = _num(payload, 'accel_x')
    ay = _num(payload, 'accel_y')
    az = _num(payload, 'accel_z')
    if ax is None:
        ax = _num(motion, 'ax', 'accel_x', default=0.0)
    if ay is None:
        ay = _num(motion, 'ay', 'accel_y', default=0.0)
    if az is None:
        az = _num(motion, 'az', 'accel_z', default=9.81)

    gx = _num(payload, 'gyro_x')
    gy = _num(payload, 'gyro_y')
    gz = _num(payload, 'gyro_z')
    if gx is None:
        gx = _num(motion, 'gx', 'gyro_x', default=0.0)
    if gy is None:
        gy = _num(motion, 'gy', 'gyro_y', default=0.0)
    if gz is None:
        gz = _num(motion, 'gz', 'gyro_z', default=0.0)

    # Si angles absents, estime depuis accélération (comme ESP32)
    if (angle_x is None or angle_y is None) and ax is not None and ay is not None and az is not None:
        denom_x = math.sqrt(ay * ay + az * az) or 1e-6
        denom_y = math.sqrt(ax * ax + az * az) or 1e-6
        if angle_x is None:
            angle_x = math.degrees(math.atan2(ax, denom_x))
        if angle_y is None:
            angle_y = math.degrees(math.atan2(ay, denom_y))

    total_g = _num(payload, 'total_g') or _num(motion, 'total_g', 'total_acceleration')
    if total_g is None and ax is not None:
        total_g = math.sqrt(ax * ax + ay * ay + az * az) / 9.81

    lat = _num(payload, 'latitude', 'lat')
    lon = _num(payload, 'lon', 'lng', 'longitude')
    if lat is None:
        lat = _num(gps, 'lat', 'latitude')
    if lon is None:
        lon = _num(gps, 'lon', 'lng', 'longitude')
    if lat == 0.0 and lon == 0.0:
        lat, lon = None, None

    ecg_raw = payload.get('ecg_raw', payload.get('ecg', payload.get('ecg_adc')))
    if ecg_raw is not None:
        try:
            ecg_raw = int(float(ecg_raw))
        except (TypeError, ValueError):
            ecg_raw = None
    ecg_bpm = _num(payload, 'bpm', 'heart_rate', 'ecg_bpm')
    if ecg_bpm is not None:
        ecg_bpm = int(ecg_bpm)

    return {
        'temperature': temperature,
        'humidity': humidity,
        'fall': fall,
        'angle_x': angle_x,
        'angle_y': angle_y,
        'ax': ax, 'ay': ay, 'az': az,
        'gx': gx, 'gy': gy, 'gz': gz,
        'total_g': total_g,
        'lat': lat, 'lon': lon,
        'altitude': _num(gps, 'altitude', 'alt'),
        'accuracy': _num(gps, 'accuracy', 'acc', 'precision'),
        'speed': _num(gps, 'speed'),
        'ecg_raw': ecg_raw,
        'ecg_bpm': ecg_bpm,
    }


def _register_fall(patient_code, device_id, lat, lon, source='esp32', angle_x=None, angle_y=None):
    recent = FallEvent.objects.filter(
        patient_code=patient_code,
        detected_at__gte=timezone.now() - timedelta(seconds=30),
    ).exists()
    if recent:
        return None

    loc = resolve_location_from_gps(lat, lon)
    zone = loc['label']
    notes = 'Détection MPU6050'
    if zone:
        notes += f' · Lieu : {zone}'
    if angle_x is not None and angle_y is not None:
        notes += f' · X={angle_x:.1f}° Y={angle_y:.1f}°'
    if source == 'simulated':
        notes = 'Chute simulée (patient sélectionné)'
        if zone:
            notes += f' · Zone : {zone}'

    return FallEvent.objects.create(
        patient_code=patient_code,
        device_id=device_id or '',
        latitude=lat,
        longitude=lon,
        source=source,
        notes=notes,
    )


def _dispatch_fall_messages(fall_event, patient_code, device_id=None):
    """
    Alertes chute : SIM800L (SMS GSM) + journal logiciel + e-mail avec lien graphique.
    """
    from geriatrie_iot.family_data import get_family_for_patient, FAMILY_ALERT_EMAIL

    patient = get_patient(patient_code)
    if not patient:
        return []

    nom = NOMS.get(patient_code, patient_code)
    lat = fall_event.latitude
    lon = fall_event.longitude
    loc = resolve_location_from_gps(lat, lon)
    zone = loc['label'] or patient.get('chambre', 'Kinshasa')
    street = loc.get('street') or ''
    heure = fall_event.detected_at.astimezone().strftime('%d/%m/%Y à %H:%M')
    gps_line = ''
    analyse_url = build_analyse_url(patient_code)
    geo_famille = build_carte_url(patient_code, portail=True, via_login=True)
    geo_carte_sms = build_carte_url(patient_code, portail=True, via_login=False)
    geo_medecin = build_carte_url(patient_code, portail=False)
    espace_famille = _absolute_url('/portail/famille/')
    if lat is not None and lon is not None:
        gps_line = f'Coordonnées GPS : {lat:.6f}, {lon:.6f}'

    lieu_line = f'Lieu : {zone}'
    if street and street not in zone:
        lieu_line += f' ({street})'
    base_msg = (
        f'{nom} a eu une chute le {heure} ({patient_code}).\n'
        f'{lieu_line}.\n'
        f'{gps_line}\n'
        f'Voir position : {geo_medecin}\n'
        f'Graphique ECG : {analyse_url}\n'
        f'Intervention immédiate requise. Médecin : {patient.get("medecin", "")}.'
    )
    famille_msg = (
        f'ALERTE FAMILLE — {nom} a eu une chute le {heure}.\n'
        f'{lieu_line}.\n'
        f'{gps_line}\n'
        f'Voir la position sur la carte (après connexion) : {geo_famille}\n'
        f'Suivi ECG : {analyse_url}\n'
        f'Le médecin {patient.get("medecin", "")} a été prévenu sur la plateforme.'
    )
    gsm_sms_short = (
        f'ALERTE GérioTrack: {nom} chute {heure}. Zone {zone}. '
        f'Carte: {geo_carte_sms}'
    )[:160]

    famille_nom, famille_phone = parse_contact(patient.get('contact', ''))
    family_acc = get_family_for_patient(patient_code)
    famille_email = (
        getattr(settings, 'FAMILY_ALERT_EMAIL', None)
        or FAMILY_ALERT_EMAIL
        or (family_acc['email'] if family_acc else 'mbayisoleil10@gmail.com')
    )
    medecin = patient.get('medecin', 'Médecin')
    medecin_phone = MEDECIN_PHONES.get(medecin, '+243 81 000 0000')
    dev = device_id or DEFAULT_DEVICE_ID

    # SMS réel : API HTTP ou file SIM800L
    _deliver_sms(
        famille_phone, gsm_sms_short, device_id=dev,
        patient_code=patient_code, fall_event=fall_event,
    )

    specs = [
        ('sms', 'famille', famille_nom or 'Famille', famille_phone, famille_msg + ' [SIM800L]'),
        ('sms', 'medecin', medecin, medecin_phone, base_msg),
    ]

    created = []
    for channel, rtype, rname, rphone, body in specs:
        msg = OutboundMessage.objects.create(
            patient_code=patient_code,
            fall_event=fall_event,
            channel=channel,
            recipient_type=rtype,
            recipient_name=rname,
            recipient_phone=rphone or '—',
            message_body=body,
            status='sent',
        )
        created.append(msg)

    subject = f'GérioTrack — Alerte chute : {nom} ({zone})'
    mail_body = (
        f'{famille_msg}\n\n'
        f'—\n'
        f'Graphique ECG / analyse : {analyse_url}\n'
        f'Lien carte / position (mot de passe puis carte) : {geo_famille}\n'
        f'Espace famille : {espace_famille}\n'
        f'Ce message a été envoyé automatiquement par GérioTrack.'
    )
    send_status = _send_real_email(subject, mail_body, famille_email)
    OutboundEmail.objects.create(
        patient_code=patient_code,
        fall_event=fall_event,
        recipient_type='famille',
        recipient_name=famille_nom or (family_acc['name'] if family_acc else 'Famille'),
        recipient_email=famille_email,
        subject=subject,
        body_text=mail_body,
        geo_url=geo_famille,
        status=send_status,
    )

    # Une seule notification cloche par chute
    fall_summary = (
        f'{nom} a chuté le {heure} · Zone {zone}.'
        + (f' GPS {lat:.5f}, {lon:.5f}.' if lat is not None and lon is not None else '')
        + ' Voir détails dans Alertes.'
    )
    AppNotification.objects.create(
        patient_code=patient_code,
        notif_type='fall',
        title=f'Chute — {nom} · {zone}',
        body=fall_summary[:500],
        fall_event=fall_event,
    )
    return created


def dispatch_patient_portal_alert(patient_code, alert_type, custom_message=None, device_id=None):
    """
    Alertes portail patient (bouton urgence, messages, position).
    Famille : SMS + e-mail avec lien carte et zone réelle.
    Médecin : notification plateforme GérioTrack uniquement (pas d'e-mail).
    """
    from geriatrie_iot.family_data import get_family_for_patient, FAMILY_ALERT_EMAIL

    patient = get_patient(patient_code)
    if not patient:
        return {'ok': False, 'error': 'Patient inconnu'}

    nom = NOMS.get(patient_code, patient_code)
    lat, lon = get_patient_gps(patient_code)
    loc = resolve_location_from_gps(lat, lon)
    zone = loc['label'] or patient.get('chambre', 'Kinshasa')
    heure = timezone.now().astimezone().strftime('%d/%m/%Y à %H:%M')
    analyse_url = build_analyse_url(patient_code)
    geo_famille = build_carte_url(patient_code, portail=True, via_login=True)
    geo_carte_sms = build_carte_url(patient_code, portail=True, via_login=False)
    gps_line = f'GPS : {lat:.6f}, {lon:.6f}' if lat is not None and lon is not None else ''

    famille_nom, famille_phone = parse_contact(patient.get('contact', ''))
    family_acc = get_family_for_patient(patient_code)
    famille_email = (
        getattr(settings, 'FAMILY_ALERT_EMAIL', None)
        or FAMILY_ALERT_EMAIL
        or (family_acc['email'] if family_acc else 'mbayisoleil10@gmail.com')
    )
    medecin = patient.get('medecin', 'Médecin')
    medecin_phone = MEDECIN_PHONES.get(medecin, '+243 81 000 0000')
    dev = device_id or DEFAULT_DEVICE_ID
    result = {'ok': True, 'alert_type': alert_type, 'zone': zone, 'geo_url': geo_famille}

    def _notify_medecin_platform(title, body, notif_type='urgence'):
        AppNotification.objects.create(
            patient_code=patient_code,
            notif_type=notif_type,
            title=title[:120],
            body=body[:500],
        )
        OutboundMessage.objects.create(
            patient_code=patient_code,
            channel='app',
            recipient_type='medecin',
            recipient_name=medecin,
            recipient_phone=medecin_phone or '—',
            message_body=body,
            status='delivered',
        )

    def _notify_famille_sms_email(sms_short, full_body, subject, notif_type='message'):
        delivery = _deliver_sms(
            famille_phone, sms_short, device_id=dev, patient_code=patient_code,
        )
        OutboundMessage.objects.create(
            patient_code=patient_code,
            channel=delivery.get('channel', 'sms'),
            recipient_type='famille',
            recipient_name=famille_nom or 'Famille',
            recipient_phone=famille_phone or '—',
            message_body=full_body,
            status=delivery.get('status', 'failed'),
        )
        mail_body = (
            f'{full_body}\n\n'
            f'—\n'
            f'Carte / position : {geo_famille}\n'
            f'Analyse ECG : {analyse_url}\n'
            f'GérioTrack — alerte automatique.'
        )
        mail_status = _send_real_email(subject, mail_body, famille_email)
        OutboundEmail.objects.create(
            patient_code=patient_code,
            recipient_type='famille',
            recipient_name=famille_nom or (family_acc['name'] if family_acc else 'Famille'),
            recipient_email=famille_email,
            subject=subject,
            body_text=mail_body,
            geo_url=geo_famille,
            status=mail_status,
        )
        result['gsm_queued'] = delivery.get('gsm_queued', False)
        result['sms_api'] = delivery.get('http_sent', False)
        result['email_status'] = mail_status
        return delivery

    if alert_type == 'sos':
        full = (
            f'URGENCE — {nom} a appuyé sur le bouton urgence le {heure}.\n'
            f'Lieu : {zone}.\n{gps_line}\n'
            f'Intervention immédiate recommandée.'
        )
        sms = f'URGENCE GérioTrack: {nom} demande aide ({zone}). Carte: {geo_carte_sms}'[:160]
        _notify_famille_sms_email(sms, full, f'URGENCE — {nom} · {zone}')
        med_body = f'{nom} — URGENCE portail patient · {zone}. {gps_line}'
        _notify_medecin_platform(f'URGENCE — {nom} · {zone}', med_body, 'urgence')

    elif alert_type == 'im_ok':
        text = custom_message or f'Je vais bien.'
        full = f'{nom} ({heure}) : {text}\nLieu : {zone}.'
        sms = f'GérioTrack: {nom} va bien ({zone}). {text[:60]}'[:160]
        _notify_famille_sms_email(sms, full, f'{nom} — Je vais bien')
        _notify_medecin_platform(
            f'{nom} — Je vais bien',
            f'{nom} signale : {text} · {zone}',
            'message',
        )

    elif alert_type == 'location':
        full = (
            f'{nom} partage sa position le {heure}.\n'
            f'Lieu : {zone}.\n{gps_line}'
        )
        sms = f'GérioTrack: position {nom} — {zone}. Carte: {geo_carte_sms}'[:160]
        _notify_famille_sms_email(sms, full, f'Position — {nom} · {zone}')
        _notify_medecin_platform(
            f'Position — {nom}',
            f'{nom} partage sa position · {zone}. {gps_line}',
            'message',
        )

    elif alert_type == 'message':
        text = (custom_message or '').strip() or 'Message du patient'
        full = f'Message de {nom} ({heure}) :\n{text}\nLieu : {zone}.'
        sms = f'GérioTrack msg {nom}: {text[:80]}'[:160]
        _notify_famille_sms_email(sms, full, f'Message — {nom}')
        _notify_medecin_platform(f'Message patient — {nom}', f'{text} · {zone}', 'message')

    elif alert_type == 'message_medecin':
        text = (custom_message or '').strip() or 'Message du patient'
        med_body = f'{nom} ({heure}) : {text} · {zone}'
        _notify_medecin_platform(f'Message — {nom}', med_body, 'message')
        OutboundMessage.objects.create(
            patient_code=patient_code,
            channel='app',
            recipient_type='medecin',
            recipient_name=medecin,
            recipient_phone=medecin_phone or '—',
            message_body=med_body,
            status='delivered',
        )

    elif alert_type == 'message_famille':
        text = (custom_message or '').strip() or 'Message du patient'
        full = f'Message de {nom} ({heure}) :\n{text}\nLieu : {zone}.'
        sms = f'GérioTrack msg {nom}: {text[:80]}'[:160]
        _notify_famille_sms_email(sms, full, f'Message — {nom}')

    else:
        return {'ok': False, 'error': f'Type alerte inconnu : {alert_type}'}

    return result


def process_esp_payload(payload, device_id=None):
    """
    Un ESP32 → données partagées (temp, humidité, MPU) pour TOUS les patients.
    GPS mis à jour pour le patient actuellement sélectionné.
    Chute enregistrée pour le patient sélectionné uniquement.
    """
    ensure_patient_states()
    device_id = str(device_id or payload.get('device_id') or DEFAULT_DEVICE_ID).strip()
    active_patient = get_active_patient_code()
    data = parse_esp_payload(payload)
    now = timezone.now()

    has_motion = any(
        k in payload for k in (
            'angle_x', 'angle_y', 'accel_x', 'accel_y', 'accel_z',
            'gyro_x', 'gyro_y', 'gyro_z', 'motion', 'motion_data',
        )
    )
    fall_risk = compute_fall_risk(
        data['angle_x'], data['angle_y'], data['total_g'], fall=data['fall']
    )

    has_ecg = data.get('ecg_raw') is not None or data.get('ecg_bpm') is not None
    shared_ecg = None
    if has_ecg:
        st_ref = PatientLiveState.objects.filter(patient_code=active_patient).first()
        shared_ecg = process_ecg_reading(
            data.get('ecg_raw'),
            bpm_device=data.get('ecg_bpm'),
            prev_bpm=st_ref.ecg_bpm if st_ref else None,
            prev_waveform=st_ref.ecg_waveform if st_ref else [],
        )

    DeviceReadingLog.objects.create(
        device_id=device_id,
        patient_code=active_patient,
        temperature=data['temperature'],
        humidity=data['humidity'],
        fall_detected=data['fall'],
        latitude=data['lat'],
        longitude=data['lon'],
        raw_payload=payload,
    )

    reading_defaults = {
        'patient_code': '',
        'temperature': data['temperature'],
        'humidity': data['humidity'],
        'latitude': data['lat'],
        'longitude': data['lon'],
        'altitude': data['altitude'],
        'accuracy': data['accuracy'],
        'speed': data['speed'],
        'fall_detected': data['fall'],
        'raw_payload': payload,
    }
    if shared_ecg:
        reading_defaults.update({
            'ecg_raw': shared_ecg['ecg_raw'],
            'ecg_bpm': shared_ecg['ecg_bpm'],
            'ecg_mv': shared_ecg['ecg_mv'],
            'ecg_waveform': shared_ecg['ecg_waveform'],
        })
    if has_motion:
        reading_defaults.update({
            'accel_x': data['ax'], 'accel_y': data['ay'], 'accel_z': data['az'],
            'gyro_x': data['gx'], 'gyro_y': data['gy'], 'gyro_z': data['gz'],
            'total_acceleration': data['total_g'] or 1.0,
        })

    reading, _ = LiveSensorReading.objects.update_or_create(
        device_id=device_id,
        defaults=reading_defaults,
    )

    motion_logs = []
    for pid in PATIENT_IDS:
        state, _ = PatientLiveState.objects.get_or_create(patient_code=pid)
        state.temperature = data['temperature']
        state.humidity = data['humidity']

        if has_motion:
            state.angle_x = data['angle_x']
            state.angle_y = data['angle_y']
            state.accel_x = data['ax']
            state.accel_y = data['ay']
            state.accel_z = data['az']
            state.gyro_x = data['gx']
            state.gyro_y = data['gy']
            state.gyro_z = data['gz']
            state.fall_risk = fall_risk
        elif state.angle_x is not None or state.angle_y is not None:
            state.fall_risk = compute_fall_risk(
                state.angle_x, state.angle_y, data['total_g'], fall=data['fall']
            )
        else:
            state.fall_risk = fall_risk

        state.sensor_online = True
        state.updated_at = now

        if pid == active_patient and data['lat'] is not None and data['lon'] is not None:
            state.latitude = data['lat']
            state.longitude = data['lon']

        if shared_ecg:
            state.ecg_raw = shared_ecg['ecg_raw']
            state.ecg_bpm = shared_ecg['ecg_bpm']
            state.ecg_mv = shared_ecg['ecg_mv']
            state.ecg_status = shared_ecg['ecg_status']
            state.ecg_waveform = shared_ecg['ecg_waveform']

        state.save()

        if has_motion:
            motion_logs.append(PatientMovementLog.objects.create(
                patient_code=pid,
                angle_x=data['angle_x'] if data['angle_x'] is not None else 0.0,
                angle_y=data['angle_y'] if data['angle_y'] is not None else 0.0,
                accel_x=data['ax'],
                accel_y=data['ay'],
                device_id=device_id,
            ))

    fall_event = None
    messages = []
    if data['fall']:
        # Chute : prendre GPS ESP si valide, sinon position propre du patient
        fall_lat = data['lat']
        fall_lon = data['lon']
        st = PatientLiveState.objects.filter(patient_code=active_patient).first()
        home = get_patient(active_patient) or {}
        if fall_lat is None or fall_lon is None:
            fall_lat = (st.latitude if st and st.latitude is not None else home.get('lat'))
            fall_lon = (st.longitude if st and st.longitude is not None else home.get('lon'))

        fall_event = _register_fall(
            active_patient, device_id, fall_lat, fall_lon, source='esp32',
            angle_x=data['angle_x'], angle_y=data['angle_y'],
        )
        if fall_event and st:
            st.latitude = fall_lat
            st.longitude = fall_lon
            st.save(update_fields=['latitude', 'longitude', 'updated_at'])
            messages = _dispatch_fall_messages(fall_event, active_patient, device_id)

    gsm_commands = pop_pending_gsm_commands(device_id)

    return {
        'reading': reading,
        'fall_event': fall_event,
        'messages': messages,
        'active_patient': active_patient,
        'motion_logs_count': len(motion_logs),
        'gsm_commands': gsm_commands,
        'ecg': shared_ecg,
    }


def simulate_fall(patient_code):
    """Simule une chute pour le patient sélectionné (GPS propre au patient)."""
    ensure_patient_states()
    if patient_code not in PATIENT_IDS:
        raise ValueError(f'Patient inconnu : {patient_code}')

    set_active_patient_code(patient_code)
    st = PatientLiveState.objects.filter(patient_code=patient_code).first()
    home = get_patient(patient_code) or {}
    # Priorité : position live du patient, sinon position d'origine (commune)
    lat = st.latitude if st and st.latitude is not None else home.get('lat')
    lon = st.longitude if st and st.longitude is not None else home.get('lon')
    if st and (st.latitude is None or st.longitude is None):
        st.latitude = lat
        st.longitude = lon
        st.save(update_fields=['latitude', 'longitude', 'updated_at'])
    angle_x = st.angle_x if st else 0.0
    angle_y = st.angle_y if st else 0.0

    fall_event = _register_fall(
        patient_code, 'SIM', lat, lon, source='simulated',
        angle_x=angle_x, angle_y=angle_y,
    )
    messages = []
    if fall_event:
        messages = _dispatch_fall_messages(fall_event, patient_code, 'SIM')
    return fall_event, messages


def reading_to_json(r, patient_code=None):
    age_s = (timezone.now() - r.updated_at).total_seconds()
    st = None
    if patient_code:
        st = PatientLiveState.objects.filter(patient_code=patient_code).first()

    angle_x = st.angle_x if st and st.angle_x is not None else 0.0
    angle_y = st.angle_y if st and st.angle_y is not None else 0.0
    fall_risk = st.fall_risk if st and st.fall_risk is not None else compute_fall_risk(
        angle_x, angle_y, r.total_acceleration, fall=r.fall_detected
    )
    max_angle = max(abs(angle_x), abs(angle_y))

    motion = {
        'ax': (st.accel_x if st and st.accel_x is not None else r.accel_x),
        'ay': (st.accel_y if st and st.accel_y is not None else r.accel_y),
        'az': (st.accel_z if st and st.accel_z is not None else r.accel_z),
        'gx': (st.gyro_x if st and st.gyro_x is not None else r.gyro_x),
        'gy': (st.gyro_y if st and st.gyro_y is not None else r.gyro_y),
        'gz': (st.gyro_z if st and st.gyro_z is not None else r.gyro_z),
        'total_g': r.total_acceleration,
        'angle_x': angle_x,
        'angle_y': angle_y,
        'max_angle': round(max_angle, 2),
        'threshold_deg': FALL_THRESHOLD_DEG,
        'warn_deg': WARN_THRESHOLD_DEG,
        'fall_risk': fall_risk,
        'near_threshold': max_angle >= WARN_THRESHOLD_DEG,
    }
    gps_lat = st.latitude if st and st.latitude is not None else r.latitude
    gps_lon = st.longitude if st and st.longitude is not None else r.longitude

    ecg_bpm = st.ecg_bpm if st and st.ecg_bpm is not None else r.ecg_bpm
    ecg_raw = st.ecg_raw if st and st.ecg_raw is not None else r.ecg_raw
    ecg_mv = st.ecg_mv if st and st.ecg_mv is not None else r.ecg_mv
    ecg_wave = (st.ecg_waveform if st and st.ecg_waveform else r.ecg_waveform) or []
    ecg_status = st.ecg_status if st and st.ecg_status else ''
    _, ecg_label = classify_ecg_bpm(ecg_bpm)

    return {
        'device_id': r.device_id,
        'patient_id': patient_code or '',
        'motion': motion,
        'env': {'temperature': r.temperature, 'humidity': r.humidity},
        'ecg': {
            'raw': ecg_raw,
            'bpm': ecg_bpm,
            'mv': ecg_mv,
            'status': ecg_status or classify_ecg_bpm(ecg_bpm)[0],
            'status_label': ecg_label,
            'waveform': ecg_wave[-ECG_WAVEFORM_LEN:],
            'analyse_url': build_analyse_url(patient_code) if patient_code else '',
        },
        'gps': {
            'lat': gps_lat, 'lon': gps_lon,
            'altitude': r.altitude, 'accuracy': r.accuracy, 'speed': r.speed,
        },
        'fall_detected': r.fall_detected,
        'fall_risk': fall_risk,
        'updated_at': r.updated_at.isoformat(),
        'age_seconds': round(age_s, 1),
        'online': age_s < ONLINE_THRESHOLD_SEC,
        'active_patient': get_active_patient_code(),
    }
