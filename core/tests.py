from django.test import TestCase, Client
from django.urls import reverse
from django.core.management import call_command
from django.contrib.auth.models import User
from core.models import Section, Asset, TrafficSlot, UserAccount


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


class UserAccountAndAuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='planner_ganesh',
            email='ganesh@railways.gov.in',
            password='SecurePassword123!',
            first_name='Ganesh',
            last_name='Kalluri'
        )
        self.account = UserAccount.objects.create(
            user=self.user,
            employee_id='EMP-1001',
            role='PLANNER',
            department='Civil / Track Engineering',
            phone_number='+91 9876543210'
        )

    def test_user_account_model(self):
        self.assertEqual(str(self.account), "planner_ganesh (Maintenance Planner) - EMP-1001")
        self.assertEqual(self.account.role, 'PLANNER')
        self.assertTrue(self.account.is_approved)

    def test_login_existing_user_success(self):
        url = reverse('core:login')
        response = self.client.post(url, {
            'username': 'planner_ganesh',
            'password': 'SecurePassword123!',
        })
        # Successful login redirects to account page
        self.assertRedirects(response, reverse('core:account'))
        self.account.refresh_from_db()
        self.assertIsNotNone(self.account.last_login_at)

    def test_login_existing_user_wrong_password(self):
        url = reverse('core:login')
        response = self.client.post(url, {
            'username': 'planner_ganesh',
            'password': 'WrongPassword!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid password")

    def test_login_non_existing_user_redirects_to_signup(self):
        """CRITICAL: If user does not exist, redirect to signup page as required."""
        url = reverse('core:login')
        response = self.client.post(url, {
            'username': 'non_existent_user',
            'password': 'AnyPassword123!',
        })
        # Must redirect to signup page!
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('core:signup'), response.url)

    def test_signup_creates_user_and_account(self):
        url = reverse('core:signup')
        response = self.client.post(url, {
            'username': 'new_controller',
            'email': 'controller@railways.gov.in',
            'password': 'Password999!',
            'confirm_password': 'Password999!',
            'first_name': 'Ramesh',
            'last_name': 'Kumar',
            'employee_id': 'EMP-2002',
            'role': 'CHIEF_CONTROLLER',
            'department': 'Operations / Traffic',
            'phone_number': '+91 9999988888',
        })
        self.assertRedirects(response, reverse('core:account'))

        # Verify user & account created
        new_user = User.objects.get(username='new_controller')
        self.assertEqual(new_user.first_name, 'Ramesh')
        self.assertEqual(new_user.account.employee_id, 'EMP-2002')
        self.assertEqual(new_user.account.role, 'CHIEF_CONTROLLER')

    def test_signup_password_mismatch(self):
        url = reverse('core:signup')
        response = self.client.post(url, {
            'username': 'bad_signup',
            'password': 'Password123!',
            'confirm_password': 'DifferentPassword!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Passwords do not match")

    def test_account_page_requires_auth(self):
        url = reverse('core:account')
        response = self.client.get(url)
        # Redirects anonymous user to login
        self.assertRedirects(response, f"{reverse('core:login')}?next={url}")

    def test_account_page_authenticated_get_and_post(self):
        self.client.login(username='planner_ganesh', password='SecurePassword123!')
        url = reverse('core:account')

        # GET
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "planner_ganesh")
        self.assertContains(response, "EMP-1001")

        # POST update profile
        post_response = self.client.post(url, {
            'first_name': 'Ganesh Updated',
            'last_name': 'Kalluri',
            'email': 'ganesh.updated@railways.gov.in',
            'phone_number': '+91 1111122222',
            'department': 'Operations',
            'role': 'SECTION_ENGINEER',
            'employee_id': 'EMP-1001',
        })
        self.assertRedirects(post_response, reverse('core:account'))

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Ganesh Updated')
        self.assertEqual(self.user.account.role, 'SECTION_ENGINEER')
        self.assertEqual(self.user.account.phone_number, '+91 1111122222')

    def test_logout(self):
        self.client.login(username='planner_ganesh', password='SecurePassword123!')
        url = reverse('core:logout')
        response = self.client.get(url)
        self.assertRedirects(response, reverse('core:login'))

