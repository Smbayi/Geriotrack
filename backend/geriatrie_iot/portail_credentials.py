# Mots de passe initiaux portail — fournis par le médecin à l'enregistrement
# Format : gerio + ID (ex. gerioP001, gerioF001)

from .patient_data import PATIENTS_BASE, parse_contact
from .family_data import FAMILY_ACCOUNTS


def patient_password(patient_id: str) -> str:
    return f'gerio{patient_id}'


def family_password(family_id: str) -> str:
    return f'gerio{family_id}'


def verify_portail_login(role: str, profil_id: str, password: str) -> bool:
    password = (password or '').strip()
    if not password or not profil_id:
        return False
    if role == 'patient':
        if profil_id not in {p['id'] for p in PATIENTS_BASE}:
            return False
        return password == patient_password(profil_id) or password == 'gerio123'
    if role == 'famille':
        if profil_id not in {f['id'] for f in FAMILY_ACCOUNTS}:
            return False
        return password == family_password(profil_id) or password == 'gerio123'
    return False


def list_portail_credentials():
    """Liste médecin : chaque famille ↔ patient + mots de passe initiaux."""
    rows = []
    for f in FAMILY_ACCOUNTS:
        rows.append({
            'family_id': f['id'],
            'family_name': f['name'],
            'family_password': family_password(f['id']),
            'patient_id': f['patient_id'],
            'patient_name': f"{f['patient_prenom']} {f['patient_nom']}",
            'patient_password': patient_password(f['patient_id']),
            'patient_zone': next(
                (p['chambre'] for p in PATIENTS_BASE if p['id'] == f['patient_id']),
                'Kinshasa',
            ),
            'family_phone': f.get('phone', ''),
            'family_email': f.get('email', ''),
        })
    return rows
