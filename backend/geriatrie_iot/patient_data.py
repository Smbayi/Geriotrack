# Données patients de démo (Kinshasa) — fusionnées avec capteurs live en base

PATIENTS_BASE = [
    {'id': 'P001', 'prenom': 'Jean',    'nom': 'Kabongo',   'age': 78, 'chambre': 'Gombe',       'statut': 'stable', 'risk': 0.18, 'temp': None, 'humid': None, 'lat': -4.3050, 'lon': 15.3080, 'medecin': 'Dr. Mutombo',  'contact': 'Marie Kabongo · +243 81 234 5678',   'device_id': 'ESP32-001'},
    {'id': 'P002', 'prenom': 'Marie',   'nom': 'Kadima',    'age': 84, 'chambre': 'Lingwala',    'statut': 'alert',  'risk': 0.82, 'temp': 27.1, 'humid': 68, 'lat': -4.3180, 'lon': 15.3020, 'medecin': 'Dr. Tshimanga', 'contact': 'Paul Kadima · +243 82 987 6543'},
    {'id': 'P003', 'prenom': 'Lucie',   'nom': 'Tshibangi', 'age': 71, 'chambre': 'Kintambo',    'statut': 'warn',   'risk': 0.64, 'temp': 27.6, 'humid': 65, 'lat': -4.3280, 'lon': 15.2750, 'medecin': 'Dr. Mutombo',  'contact': 'Alain Tshibangi · +243 89 112 2334'},
    {'id': 'P004', 'prenom': 'Paul',    'nom': 'Mukendi',   'age': 80, 'chambre': 'Barumbu',     'statut': 'stable', 'risk': 0.22, 'temp': 27.3, 'humid': 67, 'lat': -4.3120, 'lon': 15.3250, 'medecin': 'Dr. Tshimanga', 'contact': 'Léa Mukendi · +243 81 554 4332'},
    {'id': 'P005', 'prenom': 'Claire',  'nom': 'Ilunga',    'age': 76, 'chambre': 'Kinshasa',    'statut': 'stable', 'risk': 0.30, 'temp': 27.8, 'humid': 64, 'lat': -4.3250, 'lon': 15.3150, 'medecin': 'Dr. Mutombo',  'contact': 'Sophie Ilunga · +243 82 778 8990'},
    {'id': 'P006', 'prenom': 'Georges', 'nom': 'Kalala',    'age': 88, 'chambre': 'Ngaliema',    'statut': 'warn',   'risk': 0.71, 'temp': 26.9, 'humid': 70, 'lat': -4.3350, 'lon': 15.2550, 'medecin': 'Dr. Tshimanga', 'contact': 'Anne Kalala · +243 81 345 6789'},
    {'id': 'P007', 'prenom': 'Hélène',  'nom': 'Mwamba',    'age': 73, 'chambre': 'Bandalungwa', 'statut': 'stable', 'risk': 0.15, 'temp': 27.5, 'humid': 66, 'lat': -4.3550, 'lon': 15.2850, 'medecin': 'Dr. Mutombo',  'contact': 'Marc Mwamba · +243 89 998 8776'},
    {'id': 'P008', 'prenom': 'André',   'nom': 'Kabila',    'age': 82, 'chambre': 'Kalamu',      'statut': 'alert',  'risk': 0.88, 'temp': 27.2, 'humid': 69, 'lat': -4.3480, 'lon': 15.3050, 'medecin': 'Dr. Tshimanga', 'contact': 'Julie Kabila · +243 81 112 2334'},
    {'id': 'P009', 'prenom': 'Yvette',  'nom': 'Ngalula',   'age': 79, 'chambre': 'Limete',      'statut': 'stable', 'risk': 0.25, 'temp': 27.7, 'humid': 63, 'lat': -4.3650, 'lon': 15.3350, 'medecin': 'Dr. Mutombo',  'contact': 'Pierre Ngalula · +243 82 223 3445'},
    {'id': 'P010', 'prenom': 'René',    'nom': 'Lukusa',    'age': 85, 'chambre': 'Lemba',       'statut': 'warn',   'risk': 0.58, 'temp': 27.0, 'humid': 71, 'lat': -4.3850, 'lon': 15.3100, 'medecin': 'Dr. Tshimanga', 'contact': 'Nathalie Lukusa · +243 89 667 7889'},
    {'id': 'P011', 'prenom': 'Odette',  'nom': 'Mbuyi',     'age': 74, 'chambre': 'Matete',      'statut': 'stable', 'risk': 0.19, 'temp': 27.4, 'humid': 65, 'lat': -4.3750, 'lon': 15.3450, 'medecin': 'Dr. Mutombo',  'contact': 'Louis Mbuyi · +243 81 455 6678'},
    {'id': 'P012', 'prenom': 'Fernand', 'nom': 'Kasongo',   'age': 91, 'chambre': 'Masina',      'statut': 'stable', 'risk': 0.35, 'temp': 27.3, 'humid': 67, 'lat': -4.3780, 'lon': 15.3900, 'medecin': 'Dr. Tshimanga', 'contact': 'Camille Kasongo · +243 82 788 9901'},
]

NOMS = {p['id']: f"{p['prenom']} {p['nom']}" for p in PATIENTS_BASE}

MEDECIN_PHONES = {
    'Dr. Mutombo': '+243 81 000 1001',
    'Dr. Tshimanga': '+243 82 000 1002',
}

PATIENT_IDS = [p['id'] for p in PATIENTS_BASE]

# Bornes Kinshasa (carte médecin / ESP32)
KINSHASA_LAT_MIN, KINSHASA_LAT_MAX = -4.52, -4.22
KINSHASA_LON_MIN, KINSHASA_LON_MAX = 15.15, 15.52

# Centres des communes (référence pour déduire la zone depuis le GPS)
KINSHASA_COMMUNES = [
    {'name': p['chambre'], 'lat': p['lat'], 'lon': p['lon']}
    for p in PATIENTS_BASE
]


def resolve_zone_from_gps(lat, lon):
    """Retourne le nom de la commune Kinshasa la plus proche des coordonnées GPS."""
    if lat is None or lon is None:
        return None
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if lat == 0.0 and lon == 0.0:
        return None
    best_name = None
    best_d = float('inf')
    for c in KINSHASA_COMMUNES:
        d = (lat - c['lat']) ** 2 + (lon - c['lon']) ** 2
        if d < best_d:
            best_d = d
            best_name = c['name']
    return best_name or 'Kinshasa'


def get_patient(patient_code):
    for p in PATIENTS_BASE:
        if p['id'] == patient_code:
            return p
    return None


def parse_contact(contact_str):
    """Ex: 'Marie Kabongo · +243 81 234 5678' → (nom, téléphone)."""
    if not contact_str:
        return '', ''
    parts = contact_str.split('·')
    name = parts[0].strip()
    phone = parts[1].strip() if len(parts) > 1 else ''
    return name, phone

