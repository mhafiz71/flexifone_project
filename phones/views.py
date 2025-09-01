from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from .models import Phone
from .forms import PhoneForm
from accounts.models import CreditAccount

def phone_list(request):
    # Only show phones that are active AND have stock available
    phones = Phone.objects.filter(is_active=True, stock__gt=0)
    brand = request.GET.get('brand')
    if brand:
        phones = phones.filter(brand=brand)

    # Add credit eligibility filter for authenticated users
    credit_filter = request.GET.get('credit_filter')
    user_credit_limit = 0
    if request.user.is_authenticated:
        user_credit_limit = request.user.get_available_credit_limit()
        if credit_filter == 'affordable':
            phones = phones.filter(price__lte=user_credit_limit)
        elif credit_filter == 'aspirational':
            phones = phones.filter(price__gt=user_credit_limit)

    paginator = Paginator(phones, 12)  # Show 12 phones per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    brands = Phone.BRAND_CHOICES

    context = {
        'page_obj': page_obj,
        'brands': brands,
        'selected_brand': brand,
        'credit_filter': credit_filter,
        'user_credit_limit': user_credit_limit,
    }
    return render(request, 'phones/phone_list.html', context)

def phone_detail(request, slug):
    # Only allow access to phones that are active AND have stock available
    phone = get_object_or_404(Phone, slug=slug, is_active=True, stock__gt=0)

    # Check if user is authenticated and has an active plan
    has_active_plan = False
    can_afford = False
    credit_info = {}

    if request.user.is_authenticated:
        if hasattr(request.user, 'credit_account'):
            has_active_plan = request.user.credit_account.is_plan_active()

        # Check credit eligibility
        can_afford = request.user.can_afford_phone(phone.price)
        available_credit = request.user.get_available_credit_limit()

        credit_info = {
            'can_afford': can_afford,
            'available_credit': available_credit,
            'credit_limit': request.user.credit_limit,
            'credit_tier': request.user.get_credit_tier_info(),
            'is_eligible': request.user.is_eligible_for_credit(),
            'needed_amount': max(0, phone.price - available_credit) if not can_afford else 0
        }

    context = {
        'phone': phone,
        'has_active_plan': has_active_plan,
        'can_afford': can_afford,
        'credit_info': credit_info,
    }
    return render(request, 'phones/phone_detail.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def phone_create(request):
    if request.method == 'POST':
        form = PhoneForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Phone added successfully!')
            return redirect('phones:phone_list')
    else:
        form = PhoneForm()
    
    context = {
        'form': form,
        'title': 'Add New Phone',
    }
    return render(request, 'phones/phone_form.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def phone_update(request, slug):
    phone = get_object_or_404(Phone, slug=slug)
    if request.method == 'POST':
        form = PhoneForm(request.POST, request.FILES, instance=phone)
        if form.is_valid():
            form.save()
            messages.success(request, 'Phone updated successfully!')
            return redirect('phones:phone_detail', slug=phone.slug)
    else:
        form = PhoneForm(instance=phone)
    
    context = {
        'form': form,
        'title': 'Update Phone',
        'phone': phone,
    }
    return render(request, 'phones/phone_form.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def phone_delete(request, slug):
    phone = get_object_or_404(Phone, slug=slug)
    if request.method == 'POST':
        phone.delete()
        messages.success(request, 'Phone deleted successfully!')
        return redirect('phones:phone_list')
    
    context = {
        'phone': phone,
    }
    return render(request, 'phones/phone_confirm_delete.html', context)

@login_required
def buy_on_credit(request, slug):
    # Only allow purchase of phones that are active AND have stock available
    phone = get_object_or_404(Phone, slug=slug, is_active=True, stock__gt=0)
    
    # Check if user already has an active credit account
    if hasattr(request.user, 'credit_account') and request.user.credit_account.is_plan_active():
        messages.error(request, "You already have an active credit plan. You can only have one plan at a time.")
        return redirect('phones:phone_detail', slug=slug)
    
    # Check if user is verified
    if not request.user.is_verified:
        messages.error(request, "Your account must be verified before applying for credit.")
        return redirect('phones:phone_detail', slug=slug)
    
    # Check if user is eligible for credit
    if not request.user.is_eligible_for_credit():
        messages.error(request, "You are not eligible for credit at this time. Credit eligibility requires account verification and a minimum credit score of 600.")
        return redirect('phones:phone_detail', slug=slug)
    
    # Redirect to credit application
    return redirect('accounts:credit_application', phone_id=phone.id)

@login_required
def save_to_own(request, slug):
    # Only allow purchase of phones that are active AND have stock available
    phone = get_object_or_404(Phone, slug=slug, is_active=True, stock__gt=0)
    
    # Check if user already has an active credit account
    if hasattr(request.user, 'credit_account') and request.user.credit_account.is_plan_active():
        messages.error(request, "You already have an active plan. You can only have one plan at a time.")
        return redirect('phones:phone_detail', slug=slug)
    
    # Check if user is verified
    if not request.user.is_verified:
        messages.error(request, "Your account must be verified before starting a Save-to-Own plan.")
        return redirect('phones:phone_detail', slug=slug)
    
    # Redirect to select_phone view with a parameter indicating this is a save-to-own plan
    return redirect('accounts:select_phone', phone_id=phone.id)
