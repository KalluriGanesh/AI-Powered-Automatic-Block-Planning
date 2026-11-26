import json
from django.test import TestCase, Client
from django.urls import reverse
from django.core.management import call_command
from core.models import Section
from requests_app.models import MaintenanceRequest
from planner.engine import run_plan
from planner.models import Block
from ai.gemini import explain_block, explain_block_with_gemini


class DeterministicExplainTests(TestCase):
    def setUp(self):
        call_command('seed_data')
        self.section = Section.objects.get(code='LDH-SIR')
        self.asset = self.section.assets.first()
        req = MaintenanceRequest.objects.create(
            asset=self.asset, description='Explain test',
            duration_hours=3, priority=5, deadline_day=4,
        )
        self.plan_run = run_plan(horizon_days=7, label='AI Test', persist_status=False)
        self.block = self.plan_run.blocks.select_related(
            'section', 'request', 'request__asset'
        ).first()

    def test_deterministic_explanation_exists(self):
        """explain_block should return a non-empty string."""
        explanation = explain_block(self.block)
        self.assertIsInstance(explanation, str)
        self.assertGreater(len(explanation), 50)

    def test_explanation_contains_window(self):
        """Explanation should reference the scheduling window."""
        explanation = explain_block(self.block)
        self.assertIn('Day', explanation)
        self.assertIn(':00', explanation)

    def test_explanation_contains_traffic(self):
        """Explanation should mention traffic density."""
        explanation = explain_block(self.block)
        self.assertIn('traffic', explanation.lower())

    def test_explain_with_gemini_fallback(self):
        """Without API key, explain_block_with_gemini should fall back to deterministic."""
        result = explain_block_with_gemini(self.block)
        self.assertEqual(result['source'], 'deterministic')
        self.assertGreater(len(result['explanation']), 50)


class ExplainViewTests(TestCase):
    def setUp(self):
        call_command('seed_data')
        self.client = Client()
        sec = Section.objects.first()
        req = MaintenanceRequest.objects.create(
            asset=sec.assets.first(), description='View test',
            duration_hours=2, priority=4, deadline_day=3,
        )
        plan = run_plan(horizon_days=7, label='AI View Test', persist_status=False)
        self.block = plan.blocks.first()

    def test_explain_endpoint_returns_json(self):
        url = reverse('ai:explain_block', kwargs={'block_id': self.block.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        data = response.json()
        self.assertIn('explanation', data)
        self.assertIn('source', data)
        self.assertIn('score_breakdown', data)
        self.assertEqual(data['source'], 'deterministic')

    def test_explain_endpoint_404_for_invalid_block(self):
        url = reverse('ai:explain_block', kwargs={'block_id': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class ChatViewTests(TestCase):
    def setUp(self):
        call_command('seed_data')
        self.client = Client()

    def test_chat_endpoint_returns_answer(self):
        url = reverse('ai:chat')
        response = self.client.post(
            url,
            data=json.dumps({'message': 'What are the hard constraints?'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('reply', data)
        self.assertIn('Midnight', data['reply'])

    def test_chat_endpoint_traffic_question(self):
        url = reverse('ai:chat')
        response = self.client.post(
            url,
            data=json.dumps({'message': 'How is traffic density calculated?'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('traffic', data['reply'].lower())

    def test_chat_endpoint_empty_message_returns_400(self):
        url = reverse('ai:chat')
        response = self.client.post(
            url,
            data=json.dumps({'message': ''}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

