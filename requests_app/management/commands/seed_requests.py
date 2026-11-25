"""
Seed synthetic maintenance requests for testing and demonstration.

Creates 15 maintenance requests distributed across all sections with
varied priorities, durations, deadlines, and descriptions.
"""

import random
from django.core.management.base import BaseCommand
from core.models import Asset
from requests_app.models import MaintenanceRequest


class Command(BaseCommand):
    help = 'Seeds synthetic maintenance requests for testing and demonstration.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete all existing maintenance requests before seeding',
        )
        parser.add_argument(
            '--count',
            type=int,
            default=15,
            help='Number of maintenance requests to create (default: 15)',
        )

    def handle(self, *args, **options):
        reset = options.get('reset', False)
        count = options.get('count', 15)

        if reset:
            deleted_count = MaintenanceRequest.objects.all().delete()[0]
            self.stdout.write(self.style.WARNING(
                f"Reset: Deleted {deleted_count} existing maintenance requests."
            ))

        assets = list(Asset.objects.select_related('section').all())
        if not assets:
            self.stdout.write(self.style.ERROR(
                "No assets found. Run 'python manage.py seed_data' first."
            ))
            return

        rng = random.Random(99)

        descriptions = [
            'Rail grinding and resurfacing',
            'Catenary wire tension adjustment',
            'Point machine lubrication and calibration',
            'Track geometry correction at curve',
            'OHE mast foundation inspection',
            'Signal relay rack overhaul',
            'Fishplate bolt tightening',
            'Insulated rail joint replacement',
            'Dropper wire replacement',
            'Automatic block signal LED upgrade',
            'Weld defect ultrasonic testing',
            'Track ballast tamping',
            'Pantograph clearance verification',
            'Level crossing gate mechanism repair',
            'Electronic interlocking software update',
            'Turnout sleeper replacement',
            'OHE neutral section marking refresh',
            'Track circuit bond wire check',
            'Axle counter reset and calibration',
            'Traction substation transformer oil test',
        ]

        created_count = 0
        for i in range(count):
            asset = rng.choice(assets)
            description = rng.choice(descriptions)
            duration_hours = rng.choice([1, 2, 2, 3, 3, 3, 4, 4, 5, 6])
            priority = rng.choice([1, 2, 3, 3, 4, 4, 4, 5, 5, 5])
            deadline_day = rng.randint(1, 6)

            req = MaintenanceRequest.objects.create(
                asset=asset,
                description=description,
                duration_hours=duration_hours,
                priority=priority,
                deadline_day=deadline_day,
                status='PENDING',
                source='FORM',
            )
            created_count += 1
            self.stdout.write(
                f"  Created Request #{req.pk}: {asset.name} ({asset.section.code}) "
                f"P{priority} D{deadline_day} {duration_hours}h — {description}"
            )

        self.stdout.write(self.style.SUCCESS(
            f"\nSuccessfully created {created_count} maintenance requests."
        ))
