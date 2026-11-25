from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import MaintenanceRequest
from .forms import MaintenanceRequestForm


def request_list(request):
    """List all maintenance requests with filtering by status and priority."""
    reqs = MaintenanceRequest.objects.select_related('asset', 'asset__section').all()

    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')

    if status_filter:
        reqs = reqs.filter(status=status_filter)
    if priority_filter:
        reqs = reqs.filter(priority=int(priority_filter))

    return render(request, 'requests_app/request_list.html', {
        'requests': reqs,
        'status_choices': MaintenanceRequest.STATUS_CHOICES,
        'selected_status': status_filter,
        'selected_priority': priority_filter,
    })


def request_create(request):
    """Create a new maintenance request via form submission."""
    if request.method == 'POST':
        form = MaintenanceRequestForm(request.POST)
        if form.is_valid():
            req = form.save()
            messages.success(
                request,
                f'Maintenance request #{req.pk} created for {req.asset.name} '
                f'(P{req.priority}, Deadline Day {req.deadline_day}).'
            )
            return redirect('requests_app:request_list')
    else:
        form = MaintenanceRequestForm()

    return render(request, 'requests_app/request_form.html', {
        'form': form,
        'title': 'New Maintenance Request',
        'submit_label': 'Submit Request',
    })


def request_edit(request, pk):
    """Edit an existing maintenance request."""
    req_obj = get_object_or_404(MaintenanceRequest, pk=pk)

    if request.method == 'POST':
        form = MaintenanceRequestForm(request.POST, instance=req_obj)
        if form.is_valid():
            form.save()
            messages.success(request, f'Request #{req_obj.pk} updated successfully.')
            return redirect('requests_app:request_list')
    else:
        form = MaintenanceRequestForm(instance=req_obj)

    return render(request, 'requests_app/request_form.html', {
        'form': form,
        'title': f'Edit Request #{req_obj.pk}',
        'submit_label': 'Save Changes',
        'editing': True,
    })


def request_delete(request, pk):
    """Delete a maintenance request with confirmation."""
    req_obj = get_object_or_404(MaintenanceRequest, pk=pk)

    if request.method == 'POST':
        req_id = req_obj.pk
        asset_name = req_obj.asset.name
        req_obj.delete()
        messages.success(request, f'Request #{req_id} ({asset_name}) deleted.')
        return redirect('requests_app:request_list')

    return render(request, 'requests_app/request_confirm_delete.html', {
        'req': req_obj,
    })
