# ============================================================
#  backend/geriatrie_iot/views.py
#  Vues principales — Dashboard, Patients, Géolocalisation
# ============================================================
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.utils import timezone
import json, random, math

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
    # patients_gps = GPSLocation.objects.filter(
    #     created_at__gte=timezone.now() - timezone.timedelta(minutes=30)
    # ).select_related('patient').order_by('patient', '-created_at').distinct('patient')

    context = {
        'page': 'geolocation',
    }
    return render(request, 'geolocation.html', context)


# ============================================================
#  4b. ANALYSE EN TEMPS RÉEL
# ============================================================

def analyse(request):
    """
    L'analyse en temps réel est intégrée à la fiche patient.
    Redirection vers /patients/ (option ?patient=P00X pour ouvrir directement).
    """
    from django.shortcuts import redirect
    patient_id = request.GET.get('patient')
    if patient_id:
        return redirect(f'/patients/?analyse={patient_id}')
    return redirect('/patients/')


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

    # --- Données simulées Kinshasa (remplacez par queryset réel) ---
    PATIENTS_DATA = [
        {'id':'P001','prenom':'Jean',   'nom':'Dupont',   'age':78,'chambre':'Gombe',      'statut':'stable','bpm':72, 'risk':0.18,'temp':27.4,'humid':66,'lat':-4.3050,'lon':15.3080,'medecin':'Dr. Martin', 'contact':'Marie Dupont · +243 81 234 5678'},
        {'id':'P002','prenom':'Marie',  'nom':'Martin',   'age':84,'chambre':'Lingwala',   'statut':'alert', 'bpm':91, 'risk':0.82,'temp':27.1,'humid':68,'lat':-4.3180,'lon':15.3020,'medecin':'Dr. Leroux',  'contact':'Paul Martin · +243 82 987 6543'},
        {'id':'P003','prenom':'Lucie',  'nom':'Bernard',  'age':71,'chambre':'Kintambo',   'statut':'warn',  'bpm':68, 'risk':0.64,'temp':27.6,'humid':65,'lat':-4.3280,'lon':15.2750,'medecin':'Dr. Martin', 'contact':'Alain Bernard · +243 89 112 2334'},
        {'id':'P004','prenom':'Paul',   'nom':'Robert',   'age':80,'chambre':'Barumbu',    'statut':'stable','bpm':65, 'risk':0.22,'temp':27.3,'humid':67,'lat':-4.3120,'lon':15.3250,'medecin':'Dr. Leroux',  'contact':'Léa Robert · +243 81 554 4332'},
        {'id':'P005','prenom':'Claire', 'nom':'Lambert',  'age':76,'chambre':'Kinshasa',   'statut':'stable','bpm':77, 'risk':0.30,'temp':27.8,'humid':64,'lat':-4.3250,'lon':15.3150,'medecin':'Dr. Martin', 'contact':'Sophie Lambert · +243 82 778 8990'},
        {'id':'P006','prenom':'Georges','nom':'Petit',    'age':88,'chambre':'Ngaliema',   'statut':'warn',  'bpm':58, 'risk':0.71,'temp':26.9,'humid':70,'lat':-4.3350,'lon':15.2550,'medecin':'Dr. Leroux',  'contact':'Anne Petit · +243 81 345 6789'},
        {'id':'P007','prenom':'Hélène', 'nom':'Moreau',   'age':73,'chambre':'Bandalungwa','statut':'stable','bpm':74, 'risk':0.15,'temp':27.5,'humid':66,'lat':-4.3550,'lon':15.2850,'medecin':'Dr. Martin', 'contact':'Marc Moreau · +243 89 998 8776'},
        {'id':'P008','prenom':'André',  'nom':'Simon',    'age':82,'chambre':'Kalamu',     'statut':'alert', 'bpm':102,'risk':0.88,'temp':27.2,'humid':69,'lat':-4.3480,'lon':15.3050,'medecin':'Dr. Leroux',  'contact':'Julie Simon · +243 81 112 2334'},
        {'id':'P009','prenom':'Yvette', 'nom':'Garnier',  'age':79,'chambre':'Limete',     'statut':'stable','bpm':69, 'risk':0.25,'temp':27.7,'humid':63,'lat':-4.3650,'lon':15.3350,'medecin':'Dr. Martin', 'contact':'Pierre Garnier · +243 82 223 3445'},
        {'id':'P010','prenom':'René',   'nom':'Leroy',    'age':85,'chambre':'Lemba',      'statut':'warn',  'bpm':82, 'risk':0.58,'temp':27.0,'humid':71,'lat':-4.3850,'lon':15.3100,'medecin':'Dr. Leroux',  'contact':'Nathalie Leroy · +243 89 667 7889'},
        {'id':'P011','prenom':'Odette', 'nom':'Blanc',    'age':74,'chambre':'Matete',     'statut':'stable','bpm':71, 'risk':0.19,'temp':27.4,'humid':65,'lat':-4.3750,'lon':15.3450,'medecin':'Dr. Martin', 'contact':'Louis Blanc · +243 81 455 6678'},
        {'id':'P012','prenom':'Fernand','nom':'Rousseau', 'age':91,'chambre':'Masina',     'statut':'stable','bpm':66, 'risk':0.35,'temp':27.3,'humid':67,'lat':-4.3780,'lon':15.3900,'medecin':'Dr. Leroux',  'contact':'Camille Rousseau · +243 82 788 9901'},
    ]

    # Filtrage
    data = PATIENTS_DATA
    if statut != 'all':
        data = [p for p in data if p['statut'] == statut]
    if search:
        data = [p for p in data if
            search in p['nom'].lower() or
            search in p['prenom'].lower() or
            search in p['chambre'].lower() or
            search in p['id'].lower()
        ]

    # Simulation légère variation BPM temps réel
    for p in data:
        p['bpm'] = max(50, min(115, p['bpm'] + random.randint(-2, 2)))

    return JsonResponse({'patients': data, 'total': len(data)})


# ============================================================
#  6. API JSON — Géolocalisation temps réel
# ============================================================

@require_GET
def api_gps(request):
    """
    Endpoint JSON pour les positions GPS de tous les patients.
    Appelé toutes les 5 secondes par le frontend.
    GET /api/gps/
    GET /api/gps/?patient_id=P002
    """
    patient_id = request.GET.get('patient_id', None)

    # --- Données réelles ---
    # qs = GPSLocation.objects.filter(
    #     created_at__gte=timezone.now() - timezone.timedelta(minutes=5)
    # ).select_related('patient')
    # if patient_id:
    #     qs = qs.filter(patient__numero=patient_id)
    # data = [{'id': g.patient.numero, 'lat': g.latitude, 'lon': g.longitude,
    #          'acc': g.precision, 'ts': g.created_at.isoformat()} for g in qs]

    # --- Simulation GPS Kinshasa (remplacer par données ESP32/NEO-6M réelles) ---
    BASE_POSITIONS = {
        'P001': (-4.3050, 15.3080), 'P002': (-4.3180, 15.3020),
        'P003': (-4.3280, 15.2750), 'P004': (-4.3120, 15.3250),
        'P005': (-4.3250, 15.3150), 'P006': (-4.3350, 15.2550),
        'P007': (-4.3550, 15.2850), 'P008': (-4.3480, 15.3050),
        'P009': (-4.3650, 15.3350), 'P010': (-4.3850, 15.3100),
        'P011': (-4.3750, 15.3450), 'P012': (-4.3780, 15.3900),
    }
    STATUTS = {
        'P001':'stable','P002':'alert','P003':'warn','P004':'stable',
        'P005':'stable','P006':'warn','P007':'stable','P008':'alert',
        'P009':'stable','P010':'warn','P011':'stable','P012':'stable',
    }
    NOMS = {
        'P001':'Jean Dupont','P002':'Marie Martin','P003':'Lucie Bernard',
        'P004':'Paul Robert','P005':'Claire Lambert','P006':'Georges Petit',
        'P007':'Hélène Moreau','P008':'André Simon','P009':'Yvette Garnier',
        'P010':'René Leroy','P011':'Odette Blanc','P012':'Fernand Rousseau',
    }
    CHAMBRES = {
        'P001':'Gombe','P002':'Lingwala','P003':'Kintambo','P004':'Barumbu',
        'P005':'Kinshasa','P006':'Ngaliema','P007':'Bandalungwa','P008':'Kalamu',
        'P009':'Limete','P010':'Lemba','P011':'Matete','P012':'Masina',
    }

    positions = BASE_POSITIONS
    if patient_id and patient_id in positions:
        positions = {patient_id: positions[patient_id]}

    data = []
    for pid, (lat, lon) in positions.items():
        # Légère dérive simulée (ESP32 enverrait les vraies coords)
        drift = 0.0001
        data.append({
            'id':      pid,
            'nom':     NOMS.get(pid, pid),
            'chambre': CHAMBRES.get(pid, ''),
            'statut':  STATUTS.get(pid, 'stable'),
            'lat':     lat + random.uniform(-drift, drift),
            'lon':     lon + random.uniform(-drift, drift),
            'precision': random.randint(3, 8),
            'timestamp': timezone.now().isoformat(),
        })

    return JsonResponse({'positions': data})


# ============================================================
#  7. API JSON — Stats dashboard (rafraîchissement auto)
# ============================================================

@require_GET
def api_dashboard_stats(request):
    """
    Stats temps réel pour le dashboard.
    Appelé toutes les 10 secondes.
    GET /api/stats/
    """
    # --- Données réelles ---
    # stats = {
    #     'total_patients':  Patient.objects.filter(actif=True).count(),
    #     'chutes_today':    Alert.objects.filter(type='fall', created_at__date=timezone.now().date()).count(),
    #     'alertes_actives': Alert.objects.filter(acquittee=False).count(),
    #     'bpm_moyen':       round(SensorData.objects.filter(
    #         type='ecg', created_at__gte=timezone.now()-timezone.timedelta(minutes=5)
    #     ).aggregate(models.Avg('valeur'))['valeur__avg'] or 0),
    # }

    stats = {
        'total_patients':  12,
        'chutes_today':    random.randint(2, 4),
        'alertes_actives': random.randint(2, 5),
        'bpm_moyen':       random.randint(68, 78),
    }
    return JsonResponse(stats)