from django.shortcuts import render, get_object_or_404
from .models import Section, Asset, TrafficSlot


def section_list(request):
    sections = Section.objects.all()
    return render(request, 'core/section_list.html', {'sections': sections})


def section_detail(request, code):
    section = get_object_or_404(Section, code=code)
    assets = section.assets.all()
    # Build 7x24 grid: day 0-6, hour 0-23
    slots = section.traffic_slots.all()
    grid = {d: {h: 0 for h in range(24)} for d in range(7)}
    for s in slots:
        grid[s.day][s.hour] = s.density
    grid_rows = [{'day': d, 'hours': [grid[d][h] for h in range(24)]} for d in range(7)]
    return render(request, 'core/section_detail.html', {
        'section': section,
        'assets': assets,
        'grid_rows': grid_rows,
        'hours': list(range(24)),
    })


def asset_list(request):
    assets = Asset.objects.select_related('section').all()
    section_filter = request.GET.get('section', '')
    type_filter = request.GET.get('asset_type', '')

    if section_filter:
        assets = assets.filter(section__code=section_filter)
    if type_filter:
        assets = assets.filter(asset_type=type_filter)

    sections = Section.objects.all()
    return render(request, 'core/asset_list.html', {
        'assets': assets,
        'sections': sections,
        'asset_types': Asset.ASSET_TYPE_CHOICES,
        'selected_section': section_filter,
        'selected_type': type_filter,
    })
