from django.test import TestCase, Client
from django.urls import reverse
from django.core.management import call_command
from core.models import Section
from requests_app.models import MaintenanceRequest
from planner.models import PlanRun
from planner.engine import run_plan, run_baseline


class DashboardViewTests(TestCase):
    def setUp(self):
        call_command('seed_data')
        self.client = Client()
        self.section = Section.objects.first()
        self.asset = self.section.assets.first()

    def test_dashboard_empty_state(self):
        """Dashboard should show empty state when no plans exist."""
        url = reverse('dashboard:home')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No Scheduled Plan Yet')

    def test_dashboard_with_plan(self):
        """Dashboard should show KPIs and timeline when a plan exists."""
        MaintenanceRequest.objects.create(
            asset=self.asset, description='Test req',
            duration_hours=2, priority=4, deadline_day=3,
        )
        run_plan(horizon_days=7, label='Dashboard Test', persist_status=True)

        url = reverse('dashboard:home')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Schedule Timeline')
        self.assertContains(response, 'Dashboard Test')

    def test_dashboard_kpi_counts(self):
        """Dashboard KPIs should reflect request counts."""
        MaintenanceRequest.objects.create(
            asset=self.asset, description='Pending',
            duration_hours=2, priority=3, deadline_day=4, status='PENDING',
        )
        MaintenanceRequest.objects.create(
            asset=self.asset, description='Scheduled',
            duration_hours=2, priority=3, deadline_day=4, status='SCHEDULED',
        )

        url = reverse('dashboard:home')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_requests'], 2)
        self.assertEqual(response.context['pending_count'], 1)
        self.assertEqual(response.context['scheduled_count'], 1)


class WhatIfViewTests(TestCase):
    def setUp(self):
        call_command('seed_data')
        self.client = Client()
        self.section = Section.objects.get(code='LDH-SIR')
        self.asset = self.section.assets.first()
        MaintenanceRequest.objects.create(
            asset=self.asset, description='WI test',
            duration_hours=3, priority=5, deadline_day=4,
        )

    def test_whatif_get(self):
        url = reverse('dashboard:whatif')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'What-If Analysis')

    def test_whatif_post_runs_simulation(self):
        url = reverse('dashboard:whatif')
        response = self.client.post(url, {'section_id': self.section.id})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'What-If')
        # A what-if PlanRun should have been created
        self.assertTrue(PlanRun.objects.filter(is_whatif=True).exists())

    def test_whatif_does_not_alter_section(self):
        """What-if should not change section.is_blocked in the database."""
        url = reverse('dashboard:whatif')
        self.client.post(url, {'section_id': self.section.id})
        self.section.refresh_from_db()
        self.assertFalse(self.section.is_blocked)

    def test_whatif_defers_blocked_section_requests(self):
        """Requests on the blocked section should be deferred in what-if output."""
        url = reverse('dashboard:whatif')
        response = self.client.post(url, {'section_id': self.section.id})
        whatif_run = response.context.get('whatif_run')
        self.assertIsNotNone(whatif_run)
        self.assertTrue(whatif_run.is_whatif)
        self.assertGreater(whatif_run.deferred_count, 0)
