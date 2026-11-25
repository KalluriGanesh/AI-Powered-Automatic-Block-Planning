from django.shortcuts import render, redirect
from django.contrib import messages
from planner.models import PlanRun, Block
from core.models import Section
from requests_app.models import MaintenanceRequest


def dashboard_home(request):
    """
    Main dashboard: KPI summary, latest plan overview, and 7x24 timeline grid.
    Shows the latest optimized plan or an empty-state prompt.
    """
    latest_plan = (
        PlanRun.objects
        .filter(is_baseline=False, is_whatif=False)
        .order_by('-created_at')
        .first()
    )

    sections = Section.objects.all()
    total_requests = MaintenanceRequest.objects.count()
    pending_count = MaintenanceRequest.objects.filter(status='PENDING').count()
    scheduled_count = MaintenanceRequest.objects.filter(status='SCHEDULED').count()
    deferred_count = MaintenanceRequest.objects.filter(status='DEFERRED').count()

    # Build timeline grid for the latest plan
    timeline_grid = None
    section_colors = {}
    section_legend = []
    color_palette = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
                     '#06b6d4', '#ec4899', '#f97316']

    for i, sec in enumerate(sections):
        color = color_palette[i % len(color_palette)]
        section_colors[sec.id] = color
        section_legend.append({'section': sec, 'color': color})

    if latest_plan:
        blocks = latest_plan.blocks.select_related('section', 'request', 'request__asset').order_by('day', 'start_hour')

        # Build grid: 7 days × 24 hours
        grid = []
        for day in range(latest_plan.horizon_days):
            day_row = {
                'day': day,
                'hours': [],
            }
            for hour in range(24):
                day_row['hours'].append({
                    'hour': hour,
                    'blocks': [],
                })
            grid.append(day_row)

        # Place blocks into grid cells
        for block in blocks:
            for h in range(block.start_hour, block.end_hour):
                if block.day < len(grid) and h < 24:
                    grid[block.day]['hours'][h]['blocks'].append({
                        'section_code': block.section.code,
                        'section_color': section_colors.get(block.section_id, '#6b7280'),
                        'asset_name': block.request.asset.name,
                        'request_id': block.request_id,
                        'block_id': block.id,
                        'is_start': (h == block.start_hour),
                        'duration': block.end_hour - block.start_hour,
                        'cost': block.cost,
                    })

        timeline_grid = grid

    return render(request, 'dashboard/home.html', {
        'latest_plan': latest_plan,
        'sections': sections,
        'section_colors': section_colors,
        'section_legend': section_legend,
        'timeline_grid': timeline_grid,
        'total_requests': total_requests,
        'pending_count': pending_count,
        'scheduled_count': scheduled_count,
        'deferred_count': deferred_count,
    })


def whatif_view(request):
    """
    What-If simulation page: select a section to block and view the impact.
    """
    sections = Section.objects.all()
    whatif_run = None
    selected_section = None

    if request.method == 'POST':
        section_id = request.POST.get('section_id')
        if section_id:
            from planner.engine import run_plan
            selected_section = Section.objects.filter(id=section_id).first()
            if selected_section:
                whatif_run = run_plan(
                    horizon_days=7,
                    blocked_section_ids=[selected_section.id],
                    label=f"What-If: Section {selected_section.code} Blocked",
                    persist_status=False,
                )
                messages.info(
                    request,
                    f"What-If simulation complete: {whatif_run.scheduled_count} scheduled, "
                    f"{whatif_run.deferred_count} deferred when {selected_section.code} is blocked."
                )

    # Retrieve existing what-if runs for reference
    whatif_runs = PlanRun.objects.filter(is_whatif=True).order_by('-created_at')[:10]

    # Get blocks and deferred items for the what-if run
    whatif_blocks = []
    deferred_items = []
    if whatif_run:
        whatif_blocks = whatif_run.blocks.select_related(
            'request', 'section', 'request__asset'
        ).order_by('day', 'start_hour')

        if whatif_run.deferred_reasons:
            req_ids = [int(k) for k in whatif_run.deferred_reasons.keys() if k.isdigit()]
            req_map = {
                r.id: r for r in
                MaintenanceRequest.objects.filter(id__in=req_ids).select_related('asset', 'asset__section')
            }
            for req_id_str, reason in whatif_run.deferred_reasons.items():
                req_id = int(req_id_str) if req_id_str.isdigit() else None
                deferred_items.append({
                    'request_id': req_id_str,
                    'request': req_map.get(req_id),
                    'reason': reason,
                })

    return render(request, 'dashboard/whatif.html', {
        'sections': sections,
        'selected_section': selected_section,
        'whatif_run': whatif_run,
        'whatif_blocks': whatif_blocks,
        'deferred_items': deferred_items,
        'whatif_runs': whatif_runs,
    })
