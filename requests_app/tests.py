from django.test import TestCase, Client
from django.urls import reverse
from django.core.management import call_command
from core.models import Section, Asset
from requests_app.models import MaintenanceRequest
from requests_app.forms import MaintenanceRequestForm


class MaintenanceRequestFormTests(TestCase):
    def setUp(self):
        call_command('seed_data')
        self.asset = Asset.objects.first()

    def test_valid_form(self):
        form = MaintenanceRequestForm(data={
            'asset': self.asset.id,
            'description': 'Test maintenance',
            'duration_hours': 3,
            'priority': 4,
            'deadline_day': 5,
        })
        self.assertTrue(form.is_valid())

    def test_invalid_duration_too_high(self):
        form = MaintenanceRequestForm(data={
            'asset': self.asset.id,
            'description': 'Test',
            'duration_hours': 10,
            'priority': 3,
            'deadline_day': 3,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('duration_hours', form.errors)

    def test_invalid_priority_out_of_range(self):
        form = MaintenanceRequestForm(data={
            'asset': self.asset.id,
            'description': 'Test',
            'duration_hours': 2,
            'priority': 7,
            'deadline_day': 3,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('priority', form.errors)

    def test_invalid_deadline_negative(self):
        form = MaintenanceRequestForm(data={
            'asset': self.asset.id,
            'description': 'Test',
            'duration_hours': 2,
            'priority': 3,
            'deadline_day': -1,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('deadline_day', form.errors)


class MaintenanceRequestCRUDTests(TestCase):
    def setUp(self):
        call_command('seed_data')
        self.client = Client()
        self.asset = Asset.objects.first()

    def test_request_list_view(self):
        url = reverse('requests_app:request_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Maintenance Requests')

    def test_request_create_get(self):
        url = reverse('requests_app:request_create')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'New Maintenance Request')

    def test_request_create_post(self):
        url = reverse('requests_app:request_create')
        response = self.client.post(url, {
            'asset': self.asset.id,
            'description': 'Rail grinding test',
            'duration_hours': 3,
            'priority': 4,
            'deadline_day': 5,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MaintenanceRequest.objects.filter(description='Rail grinding test').exists())

    def test_request_edit_get_and_post(self):
        req = MaintenanceRequest.objects.create(
            asset=self.asset,
            description='Original description',
            duration_hours=2,
            priority=3,
            deadline_day=4,
        )
        # GET
        url = reverse('requests_app:request_edit', kwargs={'pk': req.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edit Request')

        # POST
        response = self.client.post(url, {
            'asset': self.asset.id,
            'description': 'Updated description',
            'duration_hours': 4,
            'priority': 5,
            'deadline_day': 6,
        })
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.description, 'Updated description')
        self.assertEqual(req.duration_hours, 4)
        self.assertEqual(req.priority, 5)

    def test_request_delete_get_and_post(self):
        req = MaintenanceRequest.objects.create(
            asset=self.asset,
            description='To be deleted',
            duration_hours=1,
            priority=1,
            deadline_day=1,
        )
        pk = req.pk
        # GET
        url = reverse('requests_app:request_delete', kwargs={'pk': pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Confirm Deletion')

        # POST
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(MaintenanceRequest.objects.filter(pk=pk).exists())

    def test_request_list_filter_by_status(self):
        MaintenanceRequest.objects.create(
            asset=self.asset, description='Pending req',
            duration_hours=2, priority=3, deadline_day=3, status='PENDING',
        )
        MaintenanceRequest.objects.create(
            asset=self.asset, description='Scheduled req',
            duration_hours=2, priority=3, deadline_day=3, status='SCHEDULED',
        )
        url = reverse('requests_app:request_list')
        # Filter by PENDING status — should only see 1 request
        response = self.client.get(url, {'status': 'PENDING'})
        self.assertEqual(response.status_code, 200)
        # The filtered response should contain exactly one row in the requests context
        requests_in_context = response.context['requests']
        self.assertEqual(requests_in_context.count(), 1)
        self.assertEqual(requests_in_context.first().status, 'PENDING')


class SeedRequestsCommandTests(TestCase):
    def setUp(self):
        call_command('seed_data')

    def test_seed_requests_creates_requests(self):
        call_command('seed_requests')
        self.assertEqual(MaintenanceRequest.objects.count(), 15)

    def test_seed_requests_reset(self):
        call_command('seed_requests')
        self.assertEqual(MaintenanceRequest.objects.count(), 15)
        call_command('seed_requests', '--reset', '--count', '5')
        self.assertEqual(MaintenanceRequest.objects.count(), 5)
