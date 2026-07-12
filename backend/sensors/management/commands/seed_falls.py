"""Enregistre 4 chutes simulées pour le dashboard (démo)."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from sensors.models import FallEvent


class Command(BaseCommand):
    help = 'Crée 4 événements de chute simulés pour le tableau de bord'

    def handle(self, *args, **options):
        now = timezone.now()
        seeds = [
            {
                'patient_code': 'P002',
                'latitude': -4.3180,
                'longitude': 15.3020,
                'notes': 'Chute simulée — Lingwala',
                'offset_minutes': 45,
            },
            {
                'patient_code': 'P008',
                'latitude': -4.3480,
                'longitude': 15.3050,
                'notes': 'Chute simulée — Kalamu',
                'offset_minutes': 120,
            },
            {
                'patient_code': 'P003',
                'latitude': -4.3280,
                'longitude': 15.2750,
                'notes': 'Chute simulée — Kintambo',
                'offset_minutes': 180,
            },
            {
                'patient_code': 'P006',
                'latitude': -4.3350,
                'longitude': 15.2550,
                'notes': 'Chute simulée — Ngaliema',
                'offset_minutes': 240,
            },
        ]

        created = 0
        for s in seeds:
            exists = FallEvent.objects.filter(
                patient_code=s['patient_code'],
                source='simulated',
                notes=s['notes'],
            ).exists()
            if exists:
                continue
            ev = FallEvent.objects.create(
                patient_code=s['patient_code'],
                device_id='SIM',
                latitude=s['latitude'],
                longitude=s['longitude'],
                source='simulated',
                notes=s['notes'],
            )
            FallEvent.objects.filter(pk=ev.pk).update(
                detected_at=now - timedelta(minutes=s['offset_minutes'])
            )
            created += 1

        total = FallEvent.objects.filter(source='simulated').count()
        self.stdout.write(self.style.SUCCESS(
            f'{created} chute(s) simulée(s) créée(s). Total simulées en base : {total}'
        ))
