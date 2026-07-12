# Comptes famille (portail) — chaque proche ne voit QUE son patient lié

from .patient_data import PATIENTS_BASE, parse_contact, MEDECIN_PHONES, NOMS

# Adresse réelle commune : tous les proches reçoivent les alertes ici
FAMILY_ALERT_EMAIL = 'mbayisoleil10@gmail.com'

# Identifiants F00x → patient P00x + email pour réception mail GérioTrack
FAMILY_ACCOUNTS = []
for i, p in enumerate(PATIENTS_BASE, start=1):
    fname, fphone = parse_contact(p.get('contact', ''))
    initials = ''.join(w[0] for w in (fname or 'P X').split()[:2]).upper()
    FAMILY_ACCOUNTS.append({
        'id': f'F{i:03d}',
        'name': fname or f"Famille {p['id']}",
        'initials': initials or 'FX',
        'phone': fphone,
        'email': FAMILY_ALERT_EMAIL,
        'patient_id': p['id'],
        'patient_prenom': p['prenom'],
        'patient_nom': p['nom'],
        'relation': 'proche / famille',
    })

FAMILY_BY_ID = {f['id']: f for f in FAMILY_ACCOUNTS}
FAMILY_BY_PATIENT = {f['patient_id']: f for f in FAMILY_ACCOUNTS}


def get_family(family_id):
    return FAMILY_BY_ID.get(family_id)


def get_family_for_patient(patient_id):
    return FAMILY_BY_PATIENT.get(patient_id)
