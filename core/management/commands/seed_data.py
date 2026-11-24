"""
Seed data management command for Core Railway Models.

Seeds synthetic railway data:
- 5 Sections (LDH-SIR, SIR-UMB, LDH-JUC, JUC-ASR, LDH-MOG)
- 4-6 Assets per section across TRACK, OHE, SIGNAL
- 7x24 TrafficSlot density matrix per section with repeatable random seed.
"""

import random
from django.core.management.base import BaseCommand
from core.models import Section, Asset, TrafficSlot


class Command(BaseCommand):
    help = 'Seeds synthetic railway sections, assets, and traffic density slots.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing core railway data before seeding',
        )

    def handle(self, *args, **options):
        reset = options.get('reset', False)
        if reset:
            self.stdout.write(self.style.WARNING("Reset requested. Deleting existing TrafficSlots, Assets, and Sections..."))
            TrafficSlot.objects.all().delete()
            Asset.objects.all().delete()
            Section.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Existing data cleared."))

        # 1. Synthetic Railway Sections
        sections_data = [
            {'code': 'LDH-SIR', 'name': 'Ludhiana–Sirhind', 'length_km': 60.0},
            {'code': 'SIR-UMB', 'name': 'Sirhind–Ambala', 'length_km': 54.0},
            {'code': 'LDH-JUC', 'name': 'Ludhiana–Jalandhar', 'length_km': 58.0},
            {'code': 'JUC-ASR', 'name': 'Jalandhar–Amritsar', 'length_km': 79.0},
            {'code': 'LDH-MOG', 'name': 'Ludhiana–Moga', 'length_km': 70.0},
        ]

        section_objs = {}
        for s_data in sections_data:
            sec, created = Section.objects.update_or_create(
                code=s_data['code'],
                defaults={
                    'name': s_data['name'],
                    'length_km': s_data['length_km'],
                    'is_blocked': False,
                }
            )
            section_objs[sec.code] = sec
            action = "Created" if created else "Updated"
            self.stdout.write(f"  {action} Section: {sec.code} ({sec.name})")

        # 2. Assets per Section (4-6 across TRACK, OHE, SIGNAL)
        assets_data = {
            'LDH-SIR': [
                ('Up Main Line', 'TRACK', 85),
                ('Down Main Line', 'TRACK', 80),
                ('Sirhind Overhead Catenary Grid', 'OHE', 78),
                ('Ludhiana Feeder Substation Mast', 'OHE', 82),
                ('Sirhind Junction Electronic Interlocking', 'SIGNAL', 90),
                ('Doraha Point Machine 22A', 'SIGNAL', 72),
            ],
            'SIR-UMB': [
                ('Through Corridor Track', 'TRACK', 82),
                ('Ambala Loop Line Track', 'TRACK', 76),
                ('Shambhu Sector Catenary Wire', 'OHE', 80),
                ('Ambala Cantt Traction Substation', 'OHE', 75),
                ('Automatic Block Signaling Unit S4', 'SIGNAL', 88),
            ],
            'LDH-JUC': [
                ('Northbound Fast Track', 'TRACK', 84),
                ('Southbound Slow Track', 'TRACK', 79),
                ('Phillaur Catenary Wire', 'OHE', 83),
                ('Goraya Substation Transformer', 'OHE', 77),
                ('Phillaur Interlocking Station', 'SIGNAL', 86),
                ('Jalandhar South Relay Rack', 'SIGNAL', 74),
            ],
            'JUC-ASR': [
                ('Main Amritsar Express Track', 'TRACK', 81),
                ('Down Line Track', 'TRACK', 75),
                ('Beas River Bridge Catenary', 'OHE', 72),
                ('Khilchian Traction Post', 'OHE', 85),
                ('Amritsar Outer Home Signal', 'SIGNAL', 89),
                ('Beas Automated Point Machine', 'SIGNAL', 83),
            ],
            'LDH-MOG': [
                ('Single Main Line Track', 'TRACK', 78),
                ('Moga Station Loop Track', 'TRACK', 82),
                ('Moga Sector Electrification Feeder', 'OHE', 80),
                ('Ajitwal Approach Signal Panel', 'SIGNAL', 86),
                ('Level Crossing LC-14 Interlocking Gate', 'SIGNAL', 81),
            ],
        }

        total_assets = 0
        for code, a_list in assets_data.items():
            sec = section_objs[code]
            for name, a_type, health in a_list:
                Asset.objects.update_or_create(
                    section=sec,
                    name=name,
                    defaults={
                        'asset_type': a_type,
                        'health_score': health,
                    }
                )
                total_assets += 1
        self.stdout.write(f"  Ensured {total_assets} Assets across all sections.")

        # 3. Repeatable Traffic Data Generation with Fixed Random Seed
        # Peak hours 6-10 and 17-21: density 7-10
        # Night hours 0-5: density 1-3
        # Other hours (11-16, 22-23): density 4-6
        # Weekends (day 5, 6): approximately 20% lighter (density * 0.8)
        rng = random.Random(42)

        peak_hours = {6, 7, 8, 9, 10, 17, 18, 19, 20, 21}
        night_hours = {0, 1, 2, 3, 4, 5}

        traffic_slots_to_upsert = []
        for code, sec in section_objs.items():
            for day in range(7):
                is_weekend = (day >= 5)
                for hour in range(24):
                    if hour in peak_hours:
                        base_density = rng.randint(7, 10)
                    elif hour in night_hours:
                        base_density = rng.randint(1, 3)
                    else:
                        base_density = rng.randint(4, 6)

                    if is_weekend:
                        density = max(1, int(round(base_density * 0.8)))
                    else:
                        density = base_density

                    traffic_slots_to_upsert.append((sec, day, hour, density))

        for sec, day, hour, density in traffic_slots_to_upsert:
            TrafficSlot.objects.update_or_create(
                section=sec,
                day=day,
                hour=hour,
                defaults={'density': density}
            )

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded {len(sections_data)} sections, {total_assets} assets, "
            f"and {len(traffic_slots_to_upsert)} traffic slots (repeatable seed 42)."
        ))
