from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Section, Asset, TrafficSlot, UserAccount


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


# ============================================================================
# User Authentication & Account Management Views
# ============================================================================

def account_view(request):
    """
    User Account & Profile page.
    Displays credentials, employee ID, role, department, and allows profile updates.
    If not authenticated, redirects to login page.
    """
    if not request.user.is_authenticated:
        from django.urls import reverse
        messages.info(request, "Please log in to view or manage your account.")
        return redirect(f"{reverse('core:login')}?next={request.path}")

    account, _ = UserAccount.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'PLANNER',
            'department': 'Civil / Track Engineering',
        }
    )

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        department = request.POST.get('department', '').strip()
        role = request.POST.get('role', account.role)
        employee_id = request.POST.get('employee_id', '').strip()

        # Update User fields
        request.user.first_name = first_name
        request.user.last_name = last_name
        if email:
            request.user.email = email
        request.user.save()

        # Update UserAccount fields
        if employee_id:
            # Check unique employee_id
            existing = UserAccount.objects.filter(employee_id=employee_id).exclude(pk=account.pk).first()
            if existing:
                messages.error(request, f"Employee ID '{employee_id}' is already registered to another user.")
                return redirect('core:account')
            account.employee_id = employee_id

        account.phone_number = phone_number
        if department:
            account.department = department
        if role in dict(UserAccount.ROLE_CHOICES):
            account.role = role
        account.save()

        messages.success(request, "Your account profile has been updated successfully.")
        return redirect('core:account')

    return render(request, 'core/account.html', {
        'account': account,
        'role_choices': UserAccount.ROLE_CHOICES,
    })


def login_view(request):
    """
    Login page for existing users.
    If user credentials/account do not exist, redirects to the signup page.
    """
    if request.user.is_authenticated:
        return redirect('core:account')

    next_url = request.GET.get('next', '')

    if request.method == 'POST':
        username_input = request.POST.get('username', '').strip()
        password_input = request.POST.get('password', '')
        next_url = request.POST.get('next', '') or next_url

        if not username_input or not password_input:
            messages.error(request, "Please enter both username/email and password.")
            return render(request, 'core/login.html', {'username': username_input, 'next': next_url})

        # 1. Check if user exists by username or email
        user_obj = User.objects.filter(username=username_input).first()
        if not user_obj:
            user_obj = User.objects.filter(email=username_input).first()

        # 2. If user does NOT exist: Redirect to signup page as required
        if user_obj is None:
            messages.warning(
                request,
                f"No account found for '{username_input}'. Please sign up below to create a new account."
            )
            return redirect(f"{redirect('core:signup').url}?username={username_input}")

        # 3. User exists: Authenticate credentials
        user = authenticate(request, username=user_obj.username, password=password_input)
        if user is not None:
            login(request, user)
            # Update last login timestamp in UserAccount
            account, _ = UserAccount.objects.get_or_create(user=user)
            account.last_login_at = timezone.now()
            account.save(update_fields=['last_login_at'])

            display_name = user.get_full_name() or user.username
            messages.success(request, f"Welcome back, {display_name}!")

            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect('core:account')
        else:
            messages.error(request, "Invalid password for this account. Please try again.")
            return render(request, 'core/login.html', {'username': username_input, 'next': next_url})

    return render(request, 'core/login.html', {'next': next_url})


def signup_view(request):
    """
    Sign Up / Registration page for new users.
    Creates both standard User and custom UserAccount profile record.
    """
    if request.user.is_authenticated:
        return redirect('core:account')

    initial_username = request.GET.get('username', '')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        employee_id = request.POST.get('employee_id', '').strip() or None
        role = request.POST.get('role', 'PLANNER')
        department = request.POST.get('department', 'Civil / Track Engineering').strip()
        phone_number = request.POST.get('phone_number', '').strip()

        form_data = {
            'username': username,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'employee_id': employee_id or '',
            'role': role,
            'department': department,
            'phone_number': phone_number,
        }

        # Validation
        if not username or not password:
            messages.error(request, "Username and password are required.")
            return render(request, 'core/signup.html', {
                'form_data': form_data,
                'role_choices': UserAccount.ROLE_CHOICES,
            })

        if password != confirm_password:
            messages.error(request, "Passwords do not match. Please verify your password.")
            return render(request, 'core/signup.html', {
                'form_data': form_data,
                'role_choices': UserAccount.ROLE_CHOICES,
            })

        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters long.")
            return render(request, 'core/signup.html', {
                'form_data': form_data,
                'role_choices': UserAccount.ROLE_CHOICES,
            })

        if User.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' is already taken. Please choose another.")
            return render(request, 'core/signup.html', {
                'form_data': form_data,
                'role_choices': UserAccount.ROLE_CHOICES,
            })

        if email and User.objects.filter(email=email).exists():
            messages.error(request, f"Email address '{email}' is already registered. Please log in.")
            return render(request, 'core/signup.html', {
                'form_data': form_data,
                'role_choices': UserAccount.ROLE_CHOICES,
            })

        if employee_id and UserAccount.objects.filter(employee_id=employee_id).exists():
            messages.error(request, f"Employee ID '{employee_id}' is already registered.")
            return render(request, 'core/signup.html', {
                'form_data': form_data,
                'role_choices': UserAccount.ROLE_CHOICES,
            })

        # Create User & UserAccount
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        account = UserAccount.objects.create(
            user=user,
            employee_id=employee_id,
            role=role if role in dict(UserAccount.ROLE_CHOICES) else 'PLANNER',
            department=department or 'Civil / Track Engineering',
            phone_number=phone_number,
            last_login_at=timezone.now(),
        )

        # Log the user in immediately
        login(request, user)
        messages.success(request, f"Account created successfully! Welcome to the Block Planning System, {user.username}.")
        return redirect('core:account')

    return render(request, 'core/signup.html', {
        'form_data': {'username': initial_username},
        'role_choices': UserAccount.ROLE_CHOICES,
    })


def logout_view(request):
    """
    Logs out the current user and redirects to login page.
    """
    username = request.user.username if request.user.is_authenticated else "User"
    logout(request)
    messages.info(request, f"You have been logged out successfully. Goodbye, {username}!")
    return redirect('core:login')
