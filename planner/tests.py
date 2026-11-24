from django.test import TestCase, Client
from django.urls import reverse
from django.core.management import call_command
from core.models import Section, Asset, TrafficSlot
from requests_app.models import MaintenanceRequest
from planner.models import PlanRun, Block
from planner.engine import run_plan, run_baseline
from planner.config import MIN_GAP_HOURS, MAX_BLOCKS_PER_SECTION_DAY


class PlannerSchedulingEngineTests(TestCase):
    def setUp(self):
        call_command('seed_data')
        self.ldh_sir = Section.objects.get(code='LDH-SIR')
        self.sir_umb = Section.objects.get(code='SIR-UMB')
        self.assets_ldh = list(self.ldh_sir.assets.all())
        self.assets_umb = list(self.sir_umb.assets.all())

    def test_no_overlaps_and_minimum_gaps(self):
        """Verify no two blocks overlap and min 1-hour gap is maintained on same section & day."""
        for i in range(3):
            MaintenanceRequest.objects.create(
                asset=self.assets_ldh[i],
                description=f"Task {i}",
                duration_hours=3,
                priority=4,
                deadline_day=2,
            )

        run = run_plan(horizon_days=7, label="Test Overlap & Gap")
        self.assertEqual(run.conflicts, 0)

        # Check blocks on LDH-SIR per day
        blocks = list(run.blocks.filter(section=self.ldh_sir).order_by('day', 'start_hour'))
        blocks_by_day = {}
        for b in blocks:
            blocks_by_day.setdefault(b.day, []).append(b)

        for day, d_blocks in blocks_by_day.items():
            for i in range(len(d_blocks) - 1):
                b1 = d_blocks[i]
                b2 = d_blocks[i + 1]
                # Non-overlap check
                self.assertLessEqual(b1.end_hour, b2.start_hour)
                # Minimum gap check
                self.assertGreaterEqual(b2.start_hour - b1.end_hour, MIN_GAP_HOURS)

    def test_midnight_and_deadline_constraints(self):
        """Verify blocks do not cross midnight and end on or before deadline day."""
        r1 = MaintenanceRequest.objects.create(
            asset=self.assets_ldh[0],
            description="Late day test",
            duration_hours=6,
            priority=5,
            deadline_day=3,
        )

        run = run_plan(horizon_days=7)
        self.assertEqual(run.scheduled_count, 1)
        b = run.blocks.first()
        self.assertLessEqual(b.end_hour, 24)
        self.assertLessEqual(b.day, r1.deadline_day)

    def test_blocked_section_constraint(self):
        """Verify blocked sections receive no blocks and provide deferral reasons."""
        self.ldh_sir.is_blocked = True
        self.ldh_sir.save()

        r = MaintenanceRequest.objects.create(
            asset=self.assets_ldh[0],
            description="Track fix on blocked section",
            duration_hours=2,
            priority=5,
            deadline_day=5,
        )

        run = run_plan(horizon_days=7, persist_status=True)
        self.assertEqual(run.scheduled_count, 0)
        self.assertEqual(run.deferred_count, 1)
        self.assertIn(str(r.id), run.deferred_reasons)
        self.assertIn("blocked", run.deferred_reasons[str(r.id)].lower())

        r.refresh_from_db()
        self.assertEqual(r.status, 'DEFERRED')

    def test_whatif_does_not_mutate_state(self):
        """Verify what-if run respects blocked_section_ids and does not mutate section or request state."""
        r = MaintenanceRequest.objects.create(
            asset=self.assets_ldh[0],
            description="What-if maintenance test",
            duration_hours=3,
            priority=5,
            deadline_day=4,
        )

        # Run what-if with LDH-SIR blocked and persist_status=False
        run = run_plan(
            horizon_days=7,
            blocked_section_ids=[self.ldh_sir.id],
            label="What-If Run",
            persist_status=False
        )
        self.assertTrue(run.is_whatif)
        self.assertEqual(run.scheduled_count, 0)
        self.assertEqual(run.deferred_count, 1)

        # Ensure DB Section is NOT blocked
        self.ldh_sir.refresh_from_db()
        self.assertFalse(self.ldh_sir.is_blocked)

        # Ensure request status was NOT altered (remains PENDING)
        r.refresh_from_db()
        self.assertEqual(r.status, 'PENDING')

    def test_maximum_blocks_per_day_constraint(self):
        """Verify no section has more than MAX_BLOCKS_PER_SECTION_DAY blocks scheduled per day."""
        # Create 5 requests all with deadline day 0 and duration 2 hours
        for i in range(5):
            MaintenanceRequest.objects.create(
                asset=self.assets_ldh[i % len(self.assets_ldh)],
                description=f"Day 0 heavy req {i}",
                duration_hours=2,
                priority=5,
                deadline_day=0,
            )

        run = run_plan(horizon_days=7)
        # Max blocks on LDH-SIR on Day 0 is 3
        day0_blocks = run.blocks.filter(section=self.ldh_sir, day=0).count()
        self.assertLessEqual(day0_blocks, MAX_BLOCKS_PER_SECTION_DAY)
        # The remaining requests must be deferred because deadline was Day 0
        self.assertEqual(run.deferred_count, 2)
        for req_id, reason in run.deferred_reasons.items():
            self.assertTrue(len(reason) > 0)

    def test_baseline_vs_optimized_traffic_reduction(self):
        """Verify optimized plan achieves equal or lower traffic impact than baseline."""
        for i, a in enumerate(self.assets_ldh[:3]):
            MaintenanceRequest.objects.create(
                asset=a,
                description=f"Comp test {i}",
                duration_hours=4,
                priority=4 - i,
                deadline_day=4,
            )

        baseline = run_baseline(horizon_days=7)
        optimized = run_plan(horizon_days=7, persist_status=False)

        self.assertEqual(baseline.conflicts, 0)
        self.assertEqual(optimized.conflicts, 0)
        self.assertTrue(baseline.is_baseline)
        self.assertFalse(optimized.is_baseline)

        # Optimized should have <= total traffic impact than FCFS baseline
        self.assertLessEqual(optimized.total_traffic_impact, baseline.total_traffic_impact)


class PlannerViewTests(TestCase):
    def setUp(self):
        call_command('seed_data')
        self.client = Client()
        sec = Section.objects.first()
        MaintenanceRequest.objects.create(
            asset=sec.assets.first(),
            description="Test Request",
            duration_hours=2,
            priority=4,
            deadline_day=3,
        )
        self.baseline = run_baseline(horizon_days=7)
        self.optimized = run_plan(horizon_days=7, label="Opt Test", persist_status=False)

    def test_run_list_view(self):
        url = reverse('planner:run_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maintenance Plan Runs")
        self.assertContains(response, f"#{self.optimized.pk}")

    def test_run_detail_view(self):
        url = reverse('planner:run_detail', kwargs={'pk': self.optimized.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.optimized.label)
        self.assertContains(response, "Scheduled Maintenance Blocks")

    def test_generate_plan_get_and_post(self):
        url = reverse('planner:generate_plan')
        # GET
        get_resp = self.client.get(url)
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, "Generate Maintenance Plan")

        # POST
        post_resp = self.client.post(url, {
            'label': 'New User Run',
            'horizon_days': 7,
        })
        self.assertEqual(post_resp.status_code, 302)
        new_run = PlanRun.objects.filter(label='New User Run').first()
        self.assertIsNotNone(new_run)

    def test_compare_plans_view(self):
        url = reverse('planner:compare_plans')
        response = self.client.get(url, {
            'baseline': self.baseline.pk,
            'optimized': self.optimized.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plan Comparison: Baseline vs. Optimized")
        self.assertIn('comparison', response.context)
        self.assertIsNotNone(response.context['comparison'])
