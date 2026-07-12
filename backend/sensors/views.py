# ============================================================
#  sensors/views.py — Réception ESP32 + APIs temps réel
# ============================================================
import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_GET
from django.utils import timezone

from geriatrie_iot.patient_data import NOMS, PATIENT_IDS, get_patient, parse_contact, MEDECIN_PHONES

from .models import (
    LiveSensorReading, FallEvent, PatientLiveState,
    PatientMovementLog, OutboundMessage, AppNotification, OutboundEmail,
)
from . import services


@csrf_exempt
@require_http_methods(['POST'])
def recevoir_donnees(request):
    """POST /api/recevoir/ — format Arduino IDE."""
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON invalide'}, status=400)

    if not payload:
        return JsonResponse({'ok': False, 'error': 'Corps vide'}, status=400)

    result = services.process_esp_payload(payload)
    reading = result['reading']
    fall_event = result['fall_event']

    return JsonResponse({
        'ok': True,
        'message': 'Données enregistrées pour tous les patients',
        'device_id': reading.device_id,
        'active_patient': result['active_patient'],
        'temperature': reading.temperature,
        'humidite': reading.humidity,
        'chute': reading.fall_detected,
        'latitude': reading.latitude,
        'longitude': reading.longitude,
        'ecg_bpm': reading.ecg_bpm,
        'fall_event_id': fall_event.id if fall_event else None,
        'messages_sent': len(result['messages']),
        'gsm_commands': result.get('gsm_commands', []),
        'updated_at': reading.updated_at.isoformat(),
    }, status=201)


@csrf_exempt
@require_http_methods(['POST'])
def ingest_sensors(request):
    """POST /api/sensors/ingest/"""
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON invalide'}, status=400)

    device_id = str(payload.get('device_id') or payload.get('device') or services.DEFAULT_DEVICE_ID).strip()
    result = services.process_esp_payload(payload, device_id=device_id)
    reading = result['reading']
    fall_event = result['fall_event']

    return JsonResponse({
        'ok': True,
        'device_id': reading.device_id,
        'active_patient': result['active_patient'],
        'fall_event_id': fall_event.id if fall_event else None,
        'updated_at': reading.updated_at.isoformat(),
    })


@require_GET
def latest_sensors(request):
    """GET /api/sensors/latest/?patient_id=P001 — capteurs partagés, GPS du patient."""
    patient_id = request.GET.get('patient_id', '').strip() or services.get_active_patient_code()
    device_id = request.GET.get('device_id', '').strip()

    qs = LiveSensorReading.objects.all()
    if device_id:
        qs = qs.filter(device_id=device_id)

    reading = qs.first()
    if not reading:
        return JsonResponse({'readings': [], 'total': 0, 'active_patient': services.get_active_patient_code()})

    data = [services.reading_to_json(reading, patient_code=patient_id)]
    return JsonResponse({
        'readings': data,
        'total': 1,
        'active_patient': services.get_active_patient_code(),
    })


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def monitoring_active(request):
    """GET/POST /api/monitoring/active/ — patient sélectionné pour chute."""
    if request.method == 'POST':
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            payload = {}
        patient_id = str(payload.get('patient_id') or request.POST.get('patient_id') or '').strip()
        if not patient_id:
            return JsonResponse({'ok': False, 'error': 'patient_id requis'}, status=400)
        try:
            code = services.set_active_patient_code(patient_id)
        except ValueError as e:
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
        return JsonResponse({
            'ok': True,
            'active_patient': code,
            'nom': NOMS.get(code, code),
        })

    code = services.get_active_patient_code()
    return JsonResponse({
        'active_patient': code,
        'nom': NOMS.get(code, code),
    })


@csrf_exempt
@require_http_methods(['POST'])
def simulate_fall(request):
    """POST /api/chutes/simulate/ — simule chute pour patient sélectionné."""
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        payload = {}
    patient_id = str(payload.get('patient_id') or services.get_active_patient_code()).strip()
    try:
        fall_event, messages = services.simulate_fall(patient_id)
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)

    if not fall_event:
        return JsonResponse({
            'ok': False,
            'error': 'Chute déjà enregistrée il y a moins de 30 s pour ce patient',
        }, status=409)

    return JsonResponse({
        'ok': True,
        'fall_event_id': fall_event.id,
        'patient_id': patient_id,
        'nom': NOMS.get(patient_id, patient_id),
        'messages_sent': len(messages),
        'detected_at': fall_event.detected_at.isoformat(),
    }, status=201)


@require_GET
def api_chutes(request):
    """GET /api/chutes/?patient_id=P001&limit=50"""
    today = timezone.now().date()
    patient_id = request.GET.get('patient_id', '').strip()
    limit = min(int(request.GET.get('limit', 80) or 80), 200)
    qs = FallEvent.objects.all().order_by('-detected_at')
    if patient_id:
        qs = qs.filter(patient_code=patient_id)
    qs = qs[:limit]

    from geriatrie_iot.patient_data import resolve_zone_from_gps

    data = []
    for f in qs:
        zone = resolve_zone_from_gps(f.latitude, f.longitude)
        data.append({
            'id': f.id,
            'patient_id': f.patient_code,
            'nom': NOMS.get(f.patient_code, f.patient_code),
            'zone': zone,
            'lat': f.latitude,
            'lon': f.longitude,
            'source': f.source,
            'acknowledged': f.acknowledged,
            'detected_at': f.detected_at.isoformat(),
            'notes': f.notes,
        })

    return JsonResponse({
        'chutes': data,
        'total_today': FallEvent.objects.filter(detected_at__date=today).count(),
        'total_all': FallEvent.objects.count(),
    })


@require_GET
def api_notifications(request):
    """GET /api/notifications/ — cloche : chutes uniquement (1 notif par chute)."""
    unread = AppNotification.objects.filter(read=False, notif_type='fall').count()
    qs = AppNotification.objects.filter(notif_type='fall').select_related('fall_event').all()[:30]
    data = []
    for n in qs:
        lat = lon = None
        if n.fall_event_id and n.fall_event:
            lat, lon = n.fall_event.latitude, n.fall_event.longitude
        data.append({
            'id': n.id,
            'type': n.notif_type,
            'patient_id': n.patient_code,
            'nom': NOMS.get(n.patient_code, n.patient_code) if n.patient_code else '',
            'title': n.title,
            'body': n.body,
            'read': n.read,
            'created_at': n.created_at.isoformat(),
            'fall_event_id': n.fall_event_id,
            'message_id': None,
            'lat': lat,
            'lon': lon,
            'link': (
                f'/alertes/?chute={n.fall_event_id}' if n.fall_event_id
                else f'/alertes/?notif={n.id}'
            ),
        })

    return JsonResponse({'notifications': data, 'unread': unread})


@csrf_exempt
@require_http_methods(['POST'])
def mark_notifications_read(request):
    """POST /api/notifications/read/ — body optionnel {id: N} ou tout marquer."""
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        payload = {}
    nid = payload.get('id')
    if nid:
        AppNotification.objects.filter(pk=nid).update(read=True)
    else:
        AppNotification.objects.filter(read=False).update(read=True)
    return JsonResponse({'ok': True, 'unread': AppNotification.objects.filter(read=False).count()})


@require_GET
def api_messages(request):
    """GET /api/messages/?patient_id=P002"""
    patient_id = request.GET.get('patient_id', '').strip()
    msg_id = request.GET.get('id', '').strip()
    qs = OutboundMessage.objects.select_related('fall_event').all()
    if msg_id:
        qs = qs.filter(pk=msg_id)
    elif patient_id:
        qs = qs.filter(patient_code=patient_id)
    qs = qs[:50]
    data = []
    for m in qs:
        lat = lon = None
        if m.fall_event_id and m.fall_event:
            lat, lon = m.fall_event.latitude, m.fall_event.longitude
        data.append({
            'id': m.id,
            'patient_id': m.patient_code,
            'nom': NOMS.get(m.patient_code, m.patient_code),
            'channel': m.channel,
            'recipient_type': m.recipient_type,
            'recipient_name': m.recipient_name,
            'recipient_phone': m.recipient_phone,
            'message': m.message_body,
            'status': m.status,
            'created_at': m.created_at.isoformat(),
            'fall_event_id': m.fall_event_id,
            'lat': lat,
            'lon': lon,
            'geo_url': f'/geolocalisation/?patient={m.patient_code}',
        })
    return JsonResponse({'messages': data, 'total': len(data)})


@csrf_exempt
@require_http_methods(['POST'])
def send_message(request):
    """POST /api/messages/send/ — alertes portail patient ou SMS admin."""
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON invalide'}, status=400)

    patient_id = str(payload.get('patient_id', '')).strip()
    alert_type = str(payload.get('alert_type', '')).strip()
    channel = str(payload.get('channel', 'sms')).strip()
    recipient_type = str(payload.get('recipient_type', 'famille')).strip()
    body = str(payload.get('message', '')).strip()
    device_id = str(payload.get('device_id', 'ESP32-001')).strip()

    patient = get_patient(patient_id)
    if not patient:
        return JsonResponse({'ok': False, 'error': 'Patient inconnu'}, status=404)

    if alert_type:
        result = services.dispatch_patient_portal_alert(
            patient_id, alert_type, body or None, device_id,
        )
        status = 201 if result.get('ok') else 400
        return JsonResponse(result, status=status)

    nom = NOMS.get(patient_id, patient_id)
    analyse_url = services.build_analyse_url(patient_id)

    if recipient_type == 'medecin':
        rname = patient.get('medecin', 'Médecin')
        rphone = MEDECIN_PHONES.get(rname, '+243 81 000 0000')
    else:
        rname, rphone = parse_contact(patient.get('contact', ''))

    if channel == 'call':
        body = body or f'Appel urgence GérioTrack — {nom} ({patient_id}).'
        gsm = services.queue_gsm_command(
            device_id, 'call', rphone, body,
            patient_code=patient_id,
        )
        msg = OutboundMessage.objects.create(
            patient_code=patient_id,
            channel='call',
            recipient_type=recipient_type,
            recipient_name=rname,
            recipient_phone=rphone or '—',
            message_body=body,
            status='queued' if gsm else 'failed',
        )
        AppNotification.objects.create(
            patient_code=patient_id,
            notif_type='call',
            title=f"Appel GSM → {rname}",
            body=f'Appel SIM800L en cours vers {rphone}',
        )
        return JsonResponse({
            'ok': bool(gsm),
            'message_id': msg.id,
            'gsm_queued': bool(gsm),
            'channel': 'call',
            'phone': services.normalize_phone(rphone),
        }, status=201 if gsm else 400)

    if not body:
        body = (
            f'Alerte GérioTrack — {nom} ({patient_id}). '
            f'Suivi ECG et capteurs : {analyse_url}'
        )
    gsm_sms = (
        f'GérioTrack: {nom}. {body[:120]}. Graphique: {analyse_url}'
    )[:160]
    sms_result = services.send_sms(
        rphone, gsm_sms, patient_code=patient_id, device_id=device_id,
        recipient_type=recipient_type, recipient_name=rname,
        log=False,
    )
    msg = OutboundMessage.objects.create(
        patient_code=patient_id,
        channel=sms_result.get('channel', 'sms'),
        recipient_type=recipient_type,
        recipient_name=rname,
        recipient_phone=rphone or '—',
        message_body=body + ' [SMS API/GSM]',
        status=sms_result.get('status', 'failed'),
    )

    from geriatrie_iot.family_data import FAMILY_ALERT_EMAIL, get_family_for_patient
    family_acc = get_family_for_patient(patient_id)
    famille_email = (
        getattr(settings, 'FAMILY_ALERT_EMAIL', None)
        or FAMILY_ALERT_EMAIL
        or (family_acc['email'] if family_acc else 'mbayisoleil10@gmail.com')
    )
    mail_status = 'skipped'
    if recipient_type == 'famille':
        mail_subject = f'GérioTrack — Alerte {nom}'
        mail_body = f'{body}\n\nGraphique ECG / analyse : {analyse_url}'
        mail_status = services._send_real_email(mail_subject, mail_body, famille_email)

    AppNotification.objects.create(
        patient_code=patient_id,
        notif_type='message',
        title=f"SMS → {rname}",
        body=body[:500],
    )
    return JsonResponse({
        'ok': sms_result.get('ok', True),
        'message_id': msg.id,
        'gsm_queued': sms_result.get('gsm_queued', False),
        'sms_api': sms_result.get('http_sent', False),
        'channel': sms_result.get('channel', 'sms'),
        'email_status': mail_status,
        'analyse_url': analyse_url,
    }, status=201)


@csrf_exempt
@require_http_methods(['POST'])
def api_sms_send(request):
    """
    POST /api/sms/send/
    Envoi SMS unifié : API HTTP (si SMS_API_URL) + repli SIM800L ESP32.

    Corps JSON :
      patient_id, message, recipient_type (famille|medecin|patient),
      phone (optionnel), action (location_sms|message_medecin|message_patient)
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON invalide'}, status=400)

    patient_id = str(payload.get('patient_id', '')).strip()
    message = str(payload.get('message', '')).strip()
    recipient_type = str(payload.get('recipient_type', 'famille')).strip()
    phone = str(payload.get('phone', '')).strip()
    action = str(payload.get('action', '')).strip()
    device_id = str(payload.get('device_id', 'ESP32-001')).strip()
    family_id = str(payload.get('family_id', '')).strip()

    if not patient_id:
        return JsonResponse({'ok': False, 'error': 'patient_id requis'}, status=400)

    if action in ('location_sms', 'message_medecin', 'message_patient'):
        result = services.dispatch_family_portal_message(
            patient_id, action, message or None, family_id=family_id, device_id=device_id,
        )
        status = 201 if result.get('ok') else 400
        return JsonResponse(result, status=status)

    rname, rphone, nom = services.resolve_sms_recipient(patient_id, recipient_type, phone)
    if not rphone and recipient_type != 'patient':
        return JsonResponse({'ok': False, 'error': 'Numéro destinataire introuvable'}, status=400)

    if not message:
        lat, lon = services.get_patient_gps(patient_id)
        from geriatrie_iot.patient_data import resolve_location_from_gps
        loc = resolve_location_from_gps(lat, lon)
        geo = services.build_carte_url(patient_id)
        message = f'GérioTrack — {nom} · {loc["label"]}. Carte: {geo}'

    if recipient_type == 'medecin':
        AppNotification.objects.create(
            patient_code=patient_id,
            notif_type='message',
            title=f'SMS / message — {nom}',
            body=message[:500],
        )

    if recipient_type == 'patient':
        OutboundMessage.objects.create(
            patient_code=patient_id,
            channel='app',
            recipient_type='patient',
            recipient_name=nom,
            recipient_phone='—',
            message_body=message,
            status='delivered',
        )
        return JsonResponse({'ok': True, 'status': 'delivered', 'channel': 'app'}, status=201)

    result = services.send_sms(
        rphone, message, patient_code=patient_id, device_id=device_id,
        recipient_type=recipient_type, recipient_name=rname,
    )
    status = 201 if result.get('ok') else 400
    return JsonResponse(result, status=status)


@require_GET
def api_emails(request):
    """GET /api/emails/?patient_id=P001 — mails envoyés par le logiciel."""
    patient_id = request.GET.get('patient_id', '').strip()
    email_id = request.GET.get('id', '').strip()
    qs = OutboundEmail.objects.select_related('fall_event').all()
    if email_id:
        qs = qs.filter(pk=email_id)
    elif patient_id:
        qs = qs.filter(patient_code=patient_id)
    qs = qs[:50]
    data = []
    for m in qs:
        lat = lon = None
        if m.fall_event_id and m.fall_event:
            lat, lon = m.fall_event.latitude, m.fall_event.longitude
        data.append({
            'id': m.id,
            'patient_id': m.patient_code,
            'nom': NOMS.get(m.patient_code, m.patient_code),
            'recipient_type': m.recipient_type,
            'recipient_name': m.recipient_name,
            'recipient_email': m.recipient_email,
            'subject': m.subject,
            'body': m.body_text,
            'geo_url': m.geo_url,
            'status': m.status,
            'created_at': m.created_at.isoformat(),
            'fall_event_id': m.fall_event_id,
            'lat': lat,
            'lon': lon,
        })
    return JsonResponse({'emails': data, 'total': len(data)})


@require_GET
def api_family_inbox(request):
    """
    GET /api/family/inbox/?family_id=F001
    Boîte de réception famille : SMS + mails + chutes du patient lié uniquement.
    """
    from geriatrie_iot.family_data import get_family

    family_id = request.GET.get('family_id', '').strip() or 'F001'
    fam = get_family(family_id)
    if not fam:
        return JsonResponse({'ok': False, 'error': 'Profil famille inconnu'}, status=404)

    patient_id = fam['patient_id']
    patient = get_patient(patient_id)
    from sensors.models import PatientLiveState
    from geriatrie_iot.live_sync import merge_patients_with_live

    live = next((p for p in merge_patients_with_live() if p['id'] == patient_id), None)
    st = PatientLiveState.objects.filter(patient_code=patient_id).first()

    chutes = []
    for f in FallEvent.objects.filter(patient_code=patient_id).order_by('-detected_at')[:20]:
        chutes.append({
            'id': f.id,
            'patient_id': f.patient_code,
            'nom': NOMS.get(f.patient_code, f.patient_code),
            'lat': f.latitude,
            'lon': f.longitude,
            'source': f.source,
            'detected_at': f.detected_at.isoformat(),
            'notes': f.notes,
            'geo_url': f'/portail/carte/?patient={patient_id}',
        })

    messages = []
    for m in OutboundMessage.objects.filter(
        patient_code=patient_id, recipient_type='famille'
    ).select_related('fall_event')[:30]:
        messages.append({
            'id': m.id,
            'channel': m.channel,
            'recipient_name': m.recipient_name,
            'message': m.message_body,
            'status': m.status,
            'created_at': m.created_at.isoformat(),
            'fall_event_id': m.fall_event_id,
            'lat': m.fall_event.latitude if m.fall_event else None,
            'lon': m.fall_event.longitude if m.fall_event else None,
            'geo_url': f'/portail/carte/?patient={patient_id}',
            'direction': 'reçu',
        })

    emails = []
    for e in OutboundEmail.objects.filter(
        patient_code=patient_id, recipient_type='famille'
    ).select_related('fall_event')[:30]:
        emails.append({
            'id': e.id,
            'subject': e.subject,
            'body': e.body_text,
            'recipient_email': e.recipient_email,
            'recipient_name': e.recipient_name,
            'geo_url': e.geo_url or f'/portail/carte/?patient={patient_id}',
            'status': e.status,
            'created_at': e.created_at.isoformat(),
            'fall_event_id': e.fall_event_id,
            'lat': e.fall_event.latitude if e.fall_event else None,
            'lon': e.fall_event.longitude if e.fall_event else None,
            'direction': 'reçu',
        })

    return JsonResponse({
        'ok': True,
        'family': fam,
        'patient': {
            'id': patient_id,
            'prenom': patient['prenom'] if patient else '',
            'nom': patient['nom'] if patient else '',
            'age': patient.get('age') if patient else None,
            'chambre': patient.get('chambre') if patient else '',
            'medecin': patient.get('medecin') if patient else '',
            'statut': live.get('statut') if live else 'stable',
            'risk': live.get('risk') if live else 0.2,
            'temp': live.get('temp') if live else None,
            'humid': live.get('humid') if live else None,
            'lat': (st.latitude if st and st.latitude is not None else (patient or {}).get('lat')),
            'lon': (st.longitude if st and st.longitude is not None else (patient or {}).get('lon')),
            'sensor_online': live.get('sensor_online') if live else False,
            'geo_url': f'/portail/carte/?patient={patient_id}',
        },
        'chutes': chutes,
        'messages': messages,
        'emails': emails,
        'unread': len([c for c in chutes[:5]]) + len(messages[:3]),
    })


@require_GET
def api_family_accounts(request):
    """GET /api/family/accounts/ — liste des profils famille (login)."""
    from geriatrie_iot.family_data import FAMILY_ACCOUNTS
    from geriatrie_iot.portail_credentials import family_password
    data = [{
        'id': f['id'],
        'name': f['name'],
        'patient_id': f['patient_id'],
        'patient_label': f"{f['patient_prenom']} {f['patient_nom']}",
        'email': f['email'],
        'initial_password': family_password(f['id']),
        'label': f"{f['name']} — proche de {f['patient_prenom']} {f['patient_nom']}",
    } for f in FAMILY_ACCOUNTS]
    return JsonResponse({'accounts': data})


@csrf_exempt
@require_http_methods(['POST'])
def api_portail_login(request):
    """POST /api/portail/login/ — authentification famille ou patient."""
    from geriatrie_iot.portail_credentials import verify_portail_login
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON invalide'}, status=400)

    role = str(payload.get('role', '')).strip()
    profil_id = str(payload.get('profil_id', '')).strip()
    password = str(payload.get('password', '')).strip()

    if role not in ('famille', 'patient'):
        return JsonResponse({'ok': False, 'error': 'Rôle invalide'}, status=400)
    if not verify_portail_login(role, profil_id, password):
        return JsonResponse({'ok': False, 'error': 'Identifiants incorrects'}, status=401)

    return JsonResponse({'ok': True, 'role': role, 'profil_id': profil_id})


@require_GET
def api_portail_credentials(request):
    """GET /api/portail/credentials/ — liste médecin famille ↔ patient + mots de passe."""
    from geriatrie_iot.portail_credentials import list_portail_credentials
    return JsonResponse({'credentials': list_portail_credentials(), 'total': len(list_portail_credentials())})


@require_GET
def api_patient_inbox(request):
    """
    GET /api/patient/inbox/?patient_id=P001
    Données portail patient : état live, alertes, contacts.
    """
    from geriatrie_iot.live_sync import merge_patients_with_live
    from geriatrie_iot.family_data import get_family_for_patient
    from sensors.models import PatientLiveState, AppNotification

    patient_id = request.GET.get('patient_id', '').strip() or 'P001'
    patient = get_patient(patient_id)
    if not patient:
        return JsonResponse({'ok': False, 'error': 'Patient inconnu'}, status=404)

    live = next((p for p in merge_patients_with_live() if p['id'] == patient_id), None)
    st = PatientLiveState.objects.filter(patient_code=patient_id).first()
    fam = get_family_for_patient(patient_id)
    famille_nom, famille_phone = parse_contact(patient.get('contact', ''))
    medecin = patient.get('medecin', 'Médecin')
    medecin_phone = MEDECIN_PHONES.get(medecin, '+243 81 000 0000')

    alerts = []
    for f in FallEvent.objects.filter(patient_code=patient_id).order_by('-detected_at')[:10]:
        alerts.append({
            'type': 'red',
            'm': f'Chute détectée — {f.notes or "alerte"}',
            'tm': f.detected_at.astimezone().strftime('%d/%m/%Y %H:%M'),
            'geo_url': f'/portail/carte/?patient={patient_id}',
        })
    for n in AppNotification.objects.filter(patient_code=patient_id).order_by('-created_at')[:5]:
        alerts.append({
            'type': 'blue' if n.notif_type == 'message' else 'red',
            'm': n.title,
            'tm': n.created_at.astimezone().strftime('%d/%m/%Y %H:%M'),
            'geo_url': f'/portail/carte/?patient={patient_id}',
        })

    lat = st.latitude if st and st.latitude is not None else patient.get('lat')
    lon = st.longitude if st and st.longitude is not None else patient.get('lon')
    zone = live.get('chambre') if live else patient.get('chambre', 'Kinshasa')

    return JsonResponse({
        'ok': True,
        'patient': {
            'id': patient_id,
            'prenom': patient['prenom'],
            'nom': patient['nom'],
            'age': patient.get('age'),
            'zone': zone,
            'chambre': zone,
            'statut': live.get('statut') if live else 'stable',
            'lat': lat,
            'lon': lon,
            'sensor_online': live.get('sensor_online') if live else False,
            'medecin': medecin,
            'medecin_tel': medecin_phone,
            'famille': famille_nom or (fam['name'] if fam else 'Famille'),
            'famille_tel': famille_phone or (fam['phone'] if fam else ''),
            'note': patient.get('notes', patient.get('note', 'Suivi en cours.')),
            'hist': patient.get('historique', []),
            'alerts': alerts,
            'geo_url': f'/portail/carte/?patient={patient_id}',
        },
    })


@require_GET
def api_movements(request):
    """GET /api/movements/?patient_id=P001&limit=50"""
    patient_id = request.GET.get('patient_id', '').strip()
    limit = min(int(request.GET.get('limit', 50)), 200)
    qs = PatientMovementLog.objects.all()
    if patient_id:
        qs = qs.filter(patient_code=patient_id)
    qs = qs[:limit]
    data = [{
        'patient_id': m.patient_code,
        'angle_x': m.angle_x,
        'angle_y': m.angle_y,
        'accel_x': m.accel_x,
        'accel_y': m.accel_y,
        'recorded_at': m.recorded_at.isoformat(),
    } for m in qs]
    return JsonResponse({'movements': data, 'total': len(data)})
