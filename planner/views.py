from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import PlanRun, Block
from core.models import Section
from requests_app.models import MaintenanceRequest


def run_list(request):
    runs = PlanRun.objects.all().order_by('-created_at')
    return render(request, 'planner/run_list.html', {'runs': runs})


def generate_plan(request):
    if request.method == 'POST':
        from .engine import run_plan
        label = request.POST.get('label', 'Optimized Plan')
        horizon = int(request.POST.get('horizon_days', 7))
        blocked_ids = request.POST.getlist('blocked_sections')
        blocked_ids = [int(x) for x in blocked_ids if x.isdigit()]

        run = run_plan(
            horizon_days=horizon,
            blocked_section_ids=blocked_ids if blocked_ids else None,
            label=label,
            persist_status=True if not blocked_ids else False
        )
        messages.success(request, f"Generated {run.label} (#{run.pk}): {run.scheduled_count} scheduled, {run.deferred_count} deferred.")
        return redirect('planner:run_detail', pk=run.pk)

    sections = Section.objects.all()
    return render(request, 'planner/generate.html', {'sections': sections})


def run_detail(request, pk):
    run = get_object_or_404(PlanRun, pk=pk)
    blocks = run.blocks.select_related('request', 'section', 'request__asset').order_by('day', 'start_hour')

    # Reconstruct deferred requests
    deferred_items = []
    if run.deferred_reasons:
        req_ids = [int(k) for k in run.deferred_reasons.keys() if k.isdigit()]
        req_map = {r.id: r for r in MaintenanceRequest.objects.filter(id__in=req_ids).select_related('asset', 'asset__section')}
        for req_id_str, reason in run.deferred_reasons.items():
            req_id = int(req_id_str) if req_id_str.isdigit() else None
            req = req_map.get(req_id)
            deferred_items.append({
                'request_id': req_id_str,
                'request': req,
                'reason': reason
            })

    return render(request, 'planner/run_detail.html', {
        'run': run,
        'blocks': blocks,
        'deferred_items': deferred_items,
    })


def compare_plans(request):
    baseline_id = request.GET.get('baseline')
    optimized_id = request.GET.get('optimized')

    baselines = PlanRun.objects.filter(is_baseline=True).order_by('-created_at')
    optimized_runs = PlanRun.objects.filter(is_baseline=False).order_by('-created_at')

    baseline = None
    optimized = None

    if baseline_id:
        baseline = baselines.filter(pk=baseline_id).first()
    if not baseline:
        baseline = baselines.first()

    if optimized_id:
        optimized = optimized_runs.filter(pk=optimized_id).first()
    if not optimized:
        optimized = optimized_runs.first()

    comparison = None
    if baseline and optimized:
        traffic_diff = baseline.total_traffic_impact - optimized.total_traffic_impact
        traffic_pct = (traffic_diff / baseline.total_traffic_impact * 100) if baseline.total_traffic_impact > 0 else 0.0

        comparison = {
            'traffic_reduction': round(traffic_diff, 2),
            'traffic_pct': round(traffic_pct, 1),
            'scheduled_diff': optimized.scheduled_count - baseline.scheduled_count,
            'deferred_diff': optimized.deferred_count - baseline.deferred_count,
            'availability_diff': round(optimized.availability_pct - baseline.availability_pct, 2),
            'conflicts_diff': optimized.conflicts - baseline.conflicts,
        }

    return render(request, 'planner/compare.html', {
        'baseline': baseline,
        'optimized': optimized,
        'baselines': baselines,
        'optimized_runs': optimized_runs,
        'comparison': comparison,
    })
