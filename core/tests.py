from django.test import TestCase, Client
from django.urls import reverse
from django.core.management import call_command
from core.models import Section, Asset, TrafficSlot


class CoreModelTests(TestCase):
    def setUp(self):
        self.section = Section.objects.create(
            name="Ludhiana–Sirhind",
            code="LDH-SIR",
            length_km=60.0
        )
        self.asset = Asset.objects.create(
            section=self.section,
            name="Up Main Line",
            asset_type="TRACK",
            health_score=85
        )
        self.slot = TrafficSlot.objects.create(
            section=self.section,
            day=0,
            hour=8,
            density=9
        )

    def test_section_creation_and_str(self):
        self.assertEqual(str(self.section), "LDH-SIR - Ludhiana–Sirhind")
        self.assertFalse(self.section.is_blocked)
        self.assertEqual(self.section.length_km, 60.0)

    def test_asset_creation_and_str(self):
        self.assertIn("Up Main Line", str(self.asset))
        self.assertEqual(self.asset.asset_type, "TRACK")
        self.assertEqual(self.asset.health_score, 85)

    def test_traffic_slot_str_and_unique(self):
        self.assertIn("LDH-SIR Day 0 08:00 - Density: 9", str(self.slot))
        self.assertEqual(self.slot.density, 9)


class SeedDataCommandTests(TestCase):
    def test_seed_data_idempotence(self):
        # First execution
        call_command('seed_data')
        self.assertEqual(Section.objects.count(), 5)
        self.assertEqual(Asset.objects.count(), 28)
        self.assertEqual(TrafficSlot.objects.count(), 840)

        # Second execution (idempotent, no duplicates)
        call_command('seed_data')
        self.assertEqual(Section.objects.count(), 5)
        self.assertEqual(Asset.objects.count(), 28)
        self.assertEqual(TrafficSlot.objects.count(), 840)

    def test_seed_data_reset(self):
        call_command('seed_data')
        self.assertEqual(Section.objects.count(), 5)

        # Run with reset
        call_command('seed_data', reset=True)
        self.assertEqual(Section.objects.count(), 5)
        self.assertEqual(Asset.objects.count(), 28)
        self.assertEqual(TrafficSlot.objects.count(), 840)


class CoreViewTests(TestCase):
    def setUp(self):
        call_command('seed_data')
        self.client = Client()

    def test_section_list_view(self):
        url = reverse('core:section_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "LDH-SIR")
        self.assertContains(response, "SIR-UMB")

    def test_section_detail_view(self):
        url = reverse('core:section_detail', kwargs={'code': 'LDH-SIR'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ludhiana–Sirhind")
        self.assertContains(response, "7×24 Traffic Density Heat Table")
        self.assertIn('grid_rows', response.context)
        self.assertEqual(len(response.context['grid_rows']), 7)

    def test_asset_list_view_and_filters(self):
        url = reverse('core:asset_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Up Main Line")

        # Filter by section
        resp_sec = self.client.get(url, {'section': 'LDH-SIR'})
        self.assertEqual(resp_sec.status_code, 200)
        for a in resp_sec.context['assets']:
            self.assertEqual(a.section.code, 'LDH-SIR')

        # Filter by asset_type
        resp_type = self.client.get(url, {'asset_type': 'SIGNAL'})
        self.assertEqual(resp_type.status_code, 200)
        for a in resp_type.context['assets']:
            self.assertEqual(a.asset_type, 'SIGNAL')
