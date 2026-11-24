"""
Benchmark management command comparing baseline and optimized scheduling.

Evaluates:
1. Normal Scenario: Standard distribution of maintenance requests across sections.
2. Overloaded Scenario: High density of high-priority requests on a single section.
3. Blocked-Section Scenario: Section unavailability simulation (what-if).
"""

from django.core.management.base import BaseCommand
from core.models import Section, Asset, TrafficSlot
from requests_app.models import MaintenanceRequest
from planner.engine import run_plan, run_baseline
from planner.models import PlanRun


class Command(BaseCommand):
    help = 'Runs benchmarks comparing baseline (FCFS) vs optimized scheduling across scenarios.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Clean up benchmark requests and runs after execution',
        )

    def _setup_scenario(self, scenario_name: str):
        """Prepare requests tailored for each test scenario."""
        sections = list(Section.objects.all())
        if not sections:
            self.stdout.write(self.style.ERROR("No sections found. Running seed_data first..."))
            from django.core.management import call_command
            call_command('seed_data')
            sections = list(Section.objects.all())

        # Clean existing maintenance requests for clean benchmark
        MaintenanceRequest.objects.all().delete()

        ldh_sir = Section.objects.filter(code='LDH-SIR').first() or sections[0]
        sir_umb = Section.objects.filter(code='SIR-UMB').first() or sections[1]
        ldh_juc = Section.objects.filter(code='LDH-JUC').first() or sections[2]
        juc_asr = Section.objects.filter(code='JUC-ASR').first() or sections[3]
        ldh_mog = Section.objects.filter(code='LDH-MOG').first() or sections[4]

        reqs = []

        if scenario_name == 'normal':
            # Distributed across all sections with various durations, priorities, deadlines
            for s in [ldh_sir, sir_umb, ldh_juc, juc_asr, ldh_mog]:
                assets = list(s.assets.all())
                if not assets:
                    continue
                reqs.append(MaintenanceRequest(
                    asset=assets[0],
                    description=f"Standard track inspection on {s.code}",
                    duration_hours=3,
                    priority=4,
                    deadline_day=4,
                ))
                if len(assets) > 1:
                    reqs.append(MaintenanceRequest(
                        asset=assets[1],
                        description=f"Routine OHE maintenance on {s.code}",
                        duration_hours=4,
                        priority=3,
                        deadline_day=5,
                    ))
                if len(assets) > 2:
                    reqs.append(MaintenanceRequest(
                        asset=assets[2],
                        description=f"Signal point overhaul on {s.code}",
                        duration_hours=2,
                        priority=5,
                        deadline_day=2,
                    ))
            MaintenanceRequest.objects.bulk_create(reqs)

        elif scenario_name == 'overloaded':
            # Concentrated heavy requests on LDH-SIR to test max daily blocks and deferrals
            assets = list(ldh_sir.assets.all())
            for i in range(8):
                asset = assets[i % len(assets)]
                reqs.append(MaintenanceRequest(
                    asset=asset,
                    description=f"Urgent concentrated renewal #{i+1} on LDH-SIR",
                    duration_hours=4,
                    priority=5 if i < 4 else 3,
                    deadline_day=2 if i < 4 else 4,
                ))
            # Plus 2 normal requests on other sections
            reqs.append(MaintenanceRequest(
                asset=juc_asr.assets.first(),
                description="Routine inspection on JUC-ASR",
                duration_hours=2,
                priority=2,
                deadline_day=6,
            ))
            MaintenanceRequest.objects.bulk_create(reqs)

        elif scenario_name == 'blocked_section':
            # Requests across all sections, but LDH-SIR will be blocked
            for s in [ldh_sir, sir_umb, ldh_juc]:
                for a in s.assets.all()[:2]:
                    reqs.append(MaintenanceRequest(
                        asset=a,
                        description=f"Maintenance for {a.name}",
                        duration_hours=3,
                        priority=4,
                        deadline_day=5,
                    ))
            MaintenanceRequest.objects.bulk_create(reqs)

    def handle(self, *args, **options):
        clean = options.get('clean', False)

        scenarios = ['normal', 'overloaded', 'blocked_section']
        results = []

        self.stdout.write(self.style.MIGRATE_HEADING("=== Railway Block Planner Benchmark Suite ==="))

        for scen in scenarios:
            self.stdout.write(f"\nEvaluating Scenario: [{scen.upper()}]...")
            self._setup_scenario(scen)

            blocked_ids = None
            if scen == 'blocked_section':
                ldh_sir = Section.objects.filter(code='LDH-SIR').first()
                if ldh_sir:
                    blocked_ids = [ldh_sir.id]

            # 1. Run Baseline (FCFS)
            baseline_run = run_baseline(horizon_days=7)
            baseline_run.label = f"[Benchmark] {scen.capitalize()} Baseline"
            baseline_run.save(update_fields=['label'])

            # 2. Run Optimized
            opt_run = run_plan(
                horizon_days=7,
                blocked_section_ids=blocked_ids,
                label=f"[Benchmark] {scen.capitalize()} Optimized",
                persist_status=False
            )

            # Calculate difference
            traffic_saved = baseline_run.total_traffic_impact - opt_run.total_traffic_impact
            traffic_pct = (
                (traffic_saved / baseline_run.total_traffic_impact * 100)
                if baseline_run.total_traffic_impact > 0 else 0.0
            )

            results.append({
                'scenario': scen,
                'baseline': baseline_run,
                'optimized': opt_run,
                'traffic_saved': traffic_saved,
                'traffic_pct': traffic_pct,
            })

            self.stdout.write(f"  Requests Total: {baseline_run.total_requests}")
            self.stdout.write(
                f"  Baseline (FCFS): Scheduled={baseline_run.scheduled_count}, "
                f"Deferred={baseline_run.deferred_count}, Conflicts={baseline_run.conflicts}, "
                f"Traffic Impact={baseline_run.total_traffic_impact:.1f}"
            )
            self.stdout.write(
                f"  Optimized:       Scheduled={opt_run.scheduled_count}, "
                f"Deferred={opt_run.deferred_count}, Conflicts={opt_run.conflicts}, "
                f"Traffic Impact={opt_run.total_traffic_impact:.1f}"
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"  -> Traffic Disruption Reduction: {traffic_saved:.1f} ({traffic_pct:.1f}%)"
                )
            )

        # Print formatted summary table
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(f"{'SCENARIO':<16} | {'FCFS TRAFFIC':<12} | {'OPT TRAFFIC':<12} | {'REDUCTION %':<12} | {'CONFLICTS':<9}")
        self.stdout.write("-" * 80)
        for r in results:
            self.stdout.write(
                f"{r['scenario']:<16} | {r['baseline'].total_traffic_impact:<12.1f} | "
                f"{r['optimized'].total_traffic_impact:<12.1f} | {r['traffic_pct']:<11.1f}% | "
                f"Base:{r['baseline'].conflicts} Opt:{r['optimized'].conflicts}"
            )
        self.stdout.write("=" * 80 + "\n")

        if clean:
            self.stdout.write(self.style.WARNING("Cleaning up benchmark runs and requests..."))
            for r in results:
                r['baseline'].delete()
                r['optimized'].delete()
            MaintenanceRequest.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Cleanup completed."))
