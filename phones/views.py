from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from .models import Phone
from .forms import PhoneForm
from accounts.models import CreditAccount, Product

def phone_list(request):
    phones = Phone.objects.filter(is_active=True)
    brand = request.GET.get('brand')
    if brand:
        phones = phones.filter(brand=brand)
    
    paginator = Paginator(phones, 12)  # Show 12 phones per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    brands = Phone.BRAND_CHOICES
    
    context = {
        'page_obj': page_obj,
        'brands': brands,
        'selected_brand': brand,
    }
    return render(request, 'phones/phone_list.html', context)

def phone_detail(request, slug):
    phone = get_object_or_404(Phone, slug=slug, is_active=True)
    
    # Check if user is authenticated and has an existing credit account
    has_credit_account = False
    if request.user.is_authenticated:
        has_credit_account = hasattr(request.user, 'credit_account')
    
    context = {
        'phone': phone,
        'has_credit_account': has_credit_account
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
    phone = get_object_or_404(Phone, slug=slug, is_active=True)
    
    # Check if user already has a credit account
    if hasattr(request.user, 'credit_account'):
        messages.error(request, "You already have an active credit plan. You can only have one plan at a time.")
        return redirect('phones:phone_detail', slug=slug)
    
    # Check if user is verified
    if not request.user.is_verified:
        messages.error(request, "Your account must be verified before applying for credit.")
        return redirect('phones:phone_detail', slug=slug)
    
    # Create a Product instance from the Phone
    product = Product.objects.create(
        name=phone.name,
        brand=phone.brand,
        description=phone.description,
        price=phone.price,
        is_active=True,
        stock_quantity=phone.stock,
        credit_available=True
    )
    
    # Redirect to credit application
    return redirect('accounts:credit_application', product_id=product.id)
