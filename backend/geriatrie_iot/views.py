# ============================================================
#  backend/geriatrie_iot/views.py
#  Vues principales — Dashboard, Patients, Géolocalisation
# ============================================================
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.utils import timezone

from sensors.models import LiveSensorReading, FallEvent
from sensors.services import get_active_patient_code
from .live_sync import merge_patients_with_live
from .patient_data import NOMS, PATIENTS_BASE

# ── Importez vos modèles (adaptez selon votre models.py) ──
# from patients.models import Patient
# from alerts.models import Alert
# from sensors.models import SensorData, GPSLocation


# ============================================================
#  1. DASHBOARD PRINCIPAL
# ============================================================

def dashboard(request):
    """
    Vue principale du dashboard.
    Passe les stats globales au template.
    """
    # --- Données réelles (décommentez quand vos models sont prêts) ---
    # total_patients  = Patient.objects.filter(actif=True).count()
    # chutes_today    = Alert.objects.filter(type='fall', created_at__date=timezone.now().date()).count()
    # alertes_actives = Alert.objects.filter(acquittee=False).count()
    # bpm_moyen       = SensorData.objects.filter(
    #     type='ecg', created_at__gte=timezone.now() - timezone.timedelta(minutes=10)
    # ).aggregate(models.Avg('valeur'))['valeur__avg'] or 0

    # --- Données simulées (à remplacer) ---
    context = {
        'total_patients':  12,
        'chutes_today':    3,
        'alertes_actives': 3,
        'bpm_moyen':       72,
        'page': 'dashboard',
    }
    return render(request, 'dashboard.html', context)


# ============================================================
#  2. LISTE DES PATIENTS
# ============================================================

def patient_list(request):
    """
    Vue liste de tous les patients avec filtres.
    """
    statut = request.GET.get('statut', 'all')   # all | stable | warn | alert
    search = request.GET.get('q', '').strip()

    # --- Données réelles ---
    # qs = Patient.objects.filter(actif=True).select_related('medecin')
    # if statut != 'all':
    #     qs = qs.filter(statut=statut)
    # if search:
    #     qs = qs.filter(
    #         models.Q(nom__icontains=search) |
    #         models.Q(prenom__icontains=search) |
    #         models.Q(numero_chambre__icontains=search)
    #     )

    context = {
        'statut': statut,
        'search': search,
        'page': 'patients',
    }
    return render(request, 'patients.html', context)


# ============================================================
#  3. FICHE PATIENT (détail)
# ============================================================

def patient_detail(request, patient_id):
    """
    Fiche détaillée d'un patient.
    Ouvre le panneau latéral avec toutes les données.
    """
    # patient = get_object_or_404(Patient, pk=patient_id, actif=True)
    # vitals  = SensorData.objects.filter(patient=patient).order_by('-created_at')[:50]
    # alerts  = Alert.objects.filter(patient=patient).order_by('-created_at')[:10]

    context = {
        'patient_id': patient_id,
        'page': 'patients',
    }
    return render(request, 'patients.html', context)


# ============================================================
#  4. GÉOLOCALISATION
# ============================================================

def geolocation(request):
    """
    Vue carte géolocalisation — tous les patients actifs.
    """
    context = {
        'page': 'geolocation',
    }
    return render(request, 'geolocation.html', context)


def alertes(request):
    """Page Alertes — chutes + messages famille/médecin."""
    return render(request, 'alertes.html', {'page': 'alertes'})


# ============================================================
#  4b. ANALYSE EN TEMPS RÉEL
# ============================================================

def analyse(request):
    """Page analyse temps réel — MPU, ECG, GSM."""
    return render(request, 'analyse.html', {'page': 'analyse'})


# ============================================================
#  PORTAIL USAGERS (famille + patient) — hors admin médecin
# ============================================================

def portail_login(request):
    """Connexion : choix Famille ou Patient."""
    return render(request, 'portail_login.html')


def famille_espace(request):
    """Espace famille (suivi du proche)."""
    return render(request, 'famille_espace.html')


def patient_espace(request):
    """Espace patient (suivi personnel)."""
    return render(request, 'patient_espace.html')


def portail_carte(request):
    """Carte GPS dédiée au portail famille/patient (un seul patient, hors admin)."""
    return render(request, 'portail_carte.html')


# ============================================================
#  5. API JSON — Données patients (appelée par le JS frontend)
# ============================================================

@require_GET
def api_patients(request):
    """
    Endpoint JSON pour la liste des patients avec leurs vitaux.
    GET /api/patients/?statut=all&q=dupont
    """
    statut = request.GET.get('statut', 'all')
    search = request.GET.get('q', '').strip().lower()

    data = merge_patients_with_live()

    if statut != 'all':
        data = [p for p in data if p['statut'] == statut]
    if search:
        data = [
            p for p in data if
            search in p['nom'].lower() or
            search in p['prenom'].lower() or
            search in p['chambre'].lower() or
            search in p['id'].lower()
        ]

    return JsonResponse({'patients': data, 'total': len(data)})


# ============================================================
#  6. API JSON — Géolocalisation temps réel
# ============================================================

@require_GET
def api_gps(request):
    """
    Endpoint JSON pour les positions GPS de tous les patients.
    GET /api/gps/
    GET /api/gps/?patient_id=P002
    """
    patient_id = request.GET.get('patient_id', None)
    patients = merge_patients_with_live()

    if patient_id:
        patients = [p for p in patients if p['id'] == patient_id]

    data = []
    for p in patients:
        data.append({
            'id': p['id'],
            'nom': f"{p['prenom']} {p['nom']}",
            'chambre': p['chambre'],
            'zone_label': p.get('zone_label') or p['chambre'],
            'zone_street': p.get('zone_street'),
            'statut': p['statut'],
            'lat': p['lat'],
            'lon': p['lon'],
            'temp': p.get('temp'),
            'humid': p.get('humid'),
            'angle_x': p.get('angle_x'),
            'angle_y': p.get('angle_y'),
            'precision': 5 if p.get('sensor_online') else 8,
            'timestamp': timezone.now().isoformat(),
            'sensor_online': p.get('sensor_online', False),
            'is_active_monitoring': p.get('is_active_monitoring', False),
        })

    return JsonResponse({'positions': data})


# ============================================================
#  7. API JSON — Stats dashboard (rafraîchissement auto)
# ============================================================

@require_GET
def api_dashboard_stats(request):
    """
    Stats temps réel pour le dashboard.
    GET /api/stats/
    """
    today = timezone.now().date()
    reading = LiveSensorReading.objects.first()

    temp_moy = reading.temperature if reading and reading.temperature is not None else 27.2
    humid = reading.humidity if reading and reading.humidity is not None else 66

    stats = {
        'total_patients': len(PATIENTS_BASE),
        'chutes_today': FallEvent.objects.filter(detected_at__date=today).count(),
        'alertes_actives': FallEvent.objects.filter(
            detected_at__date=today, acknowledged=False
        ).count(),
        'temp_moyenne': round(temp_moy, 1),
        'humidite': round(humid, 0) if humid else 66,
        'sensor_online': bool(
            reading and (timezone.now() - reading.updated_at).total_seconds() < 7
        ),
        'active_patient': get_active_patient_code(),
    }
    return JsonResponse(stats)