"""Initialise une position GPS distincte pour chaque patient (Kinshasa)."""
from django.core.management.base import BaseCommand

from sensors.services import init_distinct_positions


class Command(BaseCommand):
    help = 'Réinitialise des positions GPS aléatoires distinctes par patient (Kinshasa)'

    def handle(self, *args, **options):
        rows = init_distinct_positions()
        self.stdout.write(self.style.SUCCESS(
            f'{len(rows)} patient(s) positionné(s) à des endroits distincts :'
        ))
        for r in rows:
            self.stdout.write(
                f"  {r['id']}  {r['nom']:<22}  {r['chambre']:<14}  "
                f"{r['lat']:.4f}, {r['lon']:.4f}"
            )
