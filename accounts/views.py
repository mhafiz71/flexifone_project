# accounts/views.py
from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib import messages
from .forms import CustomUserCreationForm, CreditApplicationForm, UserProfileForm
from .models import Product, CreditAccount, Transaction, CreditApplication
import stripe
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from dateutil.relativedelta import relativedelta
from django.contrib.admin.views.decorators import staff_member_required
from .models import User
import random


def login_view(request):
    # Redirect logged-in users to dashboard
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        from django.contrib.auth import authenticate
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('accounts:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'registration/login.html')


def signup_view(request):
    # Redirect logged-in users to dashboard
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Generate a random credit score for demo purposes
            user.credit_score = random.randint(550, 750)
            user.save()

            # Log the user in after a successful registration
            login(request, user)

            return redirect('accounts:dashboard')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def dashboard_view(request):
    # Check for payment success message
    session_id = request.GET.get('session_id')
    if session_id:
        messages.success(
            request, 'Payment completed successfully! Your account has been updated.')

    try:
        credit_account = request.user.credit_account
        transactions = credit_account.transactions.all().order_by('-timestamp')
    except CreditAccount.DoesNotExist:
        credit_account = None
        transactions = []

    # If a user has no account, show them products to choose from
    products = Product.objects.filter(
        is_active=True) if not credit_account else []

    context = {
        'credit_account': credit_account,
        'transactions': transactions,
        'products': products,
    }
    return render(request, 'dashboard.html', context)


@login_required
def select_product_view(request, product_id):
    # Prevent user from creating a second account if they already have one
    if hasattr(request.user, 'credit_account'):
        return redirect('accounts:dashboard')

    product = get_object_or_404(Product, id=product_id)

    # Create the credit account for the user with the selected product
    account = CreditAccount.objects.create(user=request.user, product=product)

    # We will later redirect to the agreement page, but for now, back to dashboard
    return redirect('accounts:agreement', account_id=account.id)


@login_required
def agreement_view(request, account_id):
    account = get_object_or_404(
        CreditAccount, id=account_id, user=request.user)

    # If already accepted, just go to dashboard
    if account.accepted_terms:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        # User has checked the box and submitted the form
        account.accepted_terms = True
        account.accepted_at = timezone.now()
        account.save()

        subject = f"Welcome to your FlexiFone Plan for the {account.product.name}!"

        # We can pass context to a text template
        message = render_to_string('emails/welcome_email.txt', {
            'user': request.user,
            'account': account,
        })

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            # Set to True in production if you don't want errors to stop the request
            fail_silently=False,
        )

        return redirect('accounts:dashboard')

    return render(request, 'agreement.html', {'account': account})


@login_required
def credit_application_view(request, product_id):
    """Handle credit applications for BNPL purchases"""
    product = get_object_or_404(Product, id=product_id)

    # Check if user is already verified
    if not request.user.is_verified:
        messages.error(
            request, "Your account must be verified before applying for credit.")
        return redirect('accounts:dashboard')

    # Check if user already has a credit account
    if hasattr(request.user, 'credit_account'):
        messages.error(request, "You already have an active credit account.")
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = CreditApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.user = request.user
            application.product = product
            application.requested_amount = product.price

            # Simple credit scoring logic
            monthly_income = form.cleaned_data['monthly_income']
            monthly_expenses = form.cleaned_data['monthly_expenses']
            debt_to_income = (monthly_expenses / monthly_income) * 100

            # Calculate credit score based on various factors
            base_score = request.user.credit_score
            income_score = min(100, (monthly_income / 5000)
                               * 100)  # Cap at ₵5000
            dti_score = max(0, 100 - debt_to_income)  # Lower DTI is better

            # Weighted average
            new_score = int((base_score * 0.4) +
                            (income_score * 0.3) + (dti_score * 0.3))
            application.credit_score = new_score

            # Simple approval logic
            if new_score >= 650 and debt_to_income <= 50:
                application.status = CreditApplication.Status.APPROVED
                application.decision_reason = "Approved based on credit score and debt-to-income ratio."
            else:
                application.status = CreditApplication.Status.DECLINED
                application.decision_reason = f"Declined. Credit score: {new_score}, DTI: {debt_to_income:.1f}%"

            application.save()

            if application.status == CreditApplication.Status.APPROVED:
                messages.success(
                    request, "Credit application approved! You can now proceed with your purchase.")
                return redirect('accounts:bnpl_checkout', product_id=product_id)
            else:
                messages.error(
                    request, f"Credit application declined. Reason: {application.decision_reason}")
                return redirect('accounts:dashboard')
    else:
        form = CreditApplicationForm()

    context = {
        'form': form,
        'product': product,
        'monthly_payment_12': product.monthly_payment_12_months,
        'monthly_payment_6': product.monthly_payment_6_months,
    }
    return render(request, 'credit_application.html', context)


stripe.api_key = settings.STRIPE_SECRET_KEY

# --- NEW VIEW: Provide config to frontend ---


@login_required
def stripe_config(request):
    config = {'publicKey': settings.STRIPE_PUBLISHABLE_KEY}
    return JsonResponse(config, safe=False)


# --- EMBEDDED PAYMENT VIEWS ---


@login_required
def embedded_payment_view(request):
    """Handle embedded payment form"""
    try:
        credit_account = request.user.credit_account
    except CreditAccount.DoesNotExist:
        messages.error(request, "You don't have an active credit account.")
        return redirect('accounts:dashboard')

    context = {
        'credit_account': credit_account,
        'stripe_public_key': settings.STRIPE_PUBLISHABLE_KEY
    }
    return render(request, 'embedded_payment.html', context)


@login_required
def create_payment_intent(request):
    """Create payment intent for embedded form"""
    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount'))
             amount_pesewas = int(amount * 100)
            print(
                f"Creating payment intent for amount: ₵{amount} ({amount_pesewas} pesewas)")

            credit_account = request.user.credit_account
            print(
                f"Credit account: {credit_account.id} for user: {request.user.username}")

            payment_intent = stripe.PaymentIntent.create(
                amount=amount_pesewas,
                currency='ghs',
                metadata={
                    'credit_account_id': credit_account.id,
                    'user_id': request.user.id
                }
            )
            print(
                f"Created payment intent: {payment_intent.id} with metadata: {payment_intent.metadata}")

            return JsonResponse({
                'client_secret': payment_intent.client_secret
            })
        except Exception as e:
            print(f"Error creating payment intent: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)


@login_required
def payment_success_view(request):
    """Handle successful payment redirect"""
    payment_intent_id = request.GET.get('payment_intent')
    print(
        f"Payment success view called with payment_intent_id: {payment_intent_id}")

    if payment_intent_id:
        try:
            print(f"Retrieving payment intent: {payment_intent_id}")
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            print(
                f"Payment intent retrieved: {payment_intent.id}, status: {payment_intent.status}")

            if payment_intent.status == 'succeeded':
                print(f"Payment intent succeeded, processing payment...")
                return process_payment_success(request, payment_intent)
            else:
                print(
                    f"Payment intent not succeeded, status: {payment_intent.status}")
                messages.error(
                    request, f"Payment not completed. Status: {payment_intent.status}")
        except stripe.error.StripeError as e:
            print(f"Stripe error: {str(e)}")
            messages.error(request, f"Stripe error: {str(e)}")
        except Exception as e:
            print(f"Error processing payment: {str(e)}")
            messages.error(request, f"Error processing payment: {str(e)}")
    else:
        print("No payment_intent_id provided")
        messages.error(request, "No payment information found.")

    return redirect('accounts:dashboard')


def process_payment_success(request, payment_intent):
    """Process successful payment"""
    try:
        print(f"Processing payment intent: {payment_intent.id}")
        credit_account_id = payment_intent.metadata.get('credit_account_id')
        print(f"Credit account ID from metadata: {credit_account_id}")

        if not credit_account_id:
            print("Error: No credit_account_id in metadata")
            messages.error(
                request, "Error: No credit account ID found in payment metadata.")
            return redirect('accounts:dashboard')

        account = CreditAccount.objects.get(id=credit_account_id)
        print(f"Found account: {account.id} for user: {account.user.username}")

        # Convert from pesewas to cedis and ensure it's a Decimal
        from decimal import Decimal
        amount_paid = Decimal(str(payment_intent.amount / 100))
        print(f"Amount paid: ₵{amount_paid}")

        # Update account balance
        old_balance = account.balance
        account.balance += amount_paid
        print(f"Updated balance from ₵{old_balance} to ₵{account.balance}")

        # Create transaction record
        transaction = Transaction.objects.create(
            account=account,
            amount=amount_paid,
            transaction_type=Transaction.TransactionType.PAYMENT,
            transaction_id=payment_intent.id,
            stripe_payment_intent=payment_intent.id,
            description=f"Payment for {account.product.name}"
        )
        print(f"Created transaction: {transaction.id}")

        # Check if account is completed
        if account.balance >= account.product.price and account.status != CreditAccount.Status.COMPLETED:
            account.status = CreditAccount.Status.COMPLETED
            print(f"Account {account.id} marked as completed")

            # Send completion email
            subject = f"Congratulations! Your plan for the {account.product.name} is complete!"
            message = render_to_string('emails/plan_completed.txt', {
                'user': account.user,
                'account': account,
            })
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[account.user.email],
                fail_silently=True,
            )

        account.save()
        print(f"Account saved successfully")
        messages.success(
            request, f"Payment of ₵{amount_paid} processed successfully!")

    except CreditAccount.DoesNotExist:
        print(f"Error: CreditAccount with ID {credit_account_id} not found")
        messages.error(request, f"Error: Credit account not found.")
    except Exception as e:
        print(f"Error processing payment: {str(e)}")
        messages.error(request, f"Error processing payment: {str(e)}")

    return redirect('accounts:dashboard')


# --- LEGACY WEBHOOK VIEWS (keeping for compatibility) ---


@login_required
def create_checkout_session(request):
    if request.method == 'POST':
        try:
            # Get the user's credit account
            credit_account = request.user.credit_account

            # Get the amount from the frontend form (in cedis)
            amount_cedis = float(request.POST.get('amount'))
            # Convert to pesewas for Stripe
            amount_pesewas = int(amount_cedis * 100)

            print(
                f"Creating checkout session for account {credit_account.id}, amount: ₵{amount_cedis}")

            # Create a new Checkout Session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[
                    {
                        'price_data': {
                            'currency': 'ghs',
                            'product_data': {
                                'name': f"Deposit for {credit_account.product.name}",
                            },
                            'unit_amount': amount_pesewas,
                        },
                        'quantity': 1,
                    }
                ],
                mode='payment',
                # IMPORTANT: These URLs are where Stripe will redirect the user
                success_url=request.build_absolute_uri(
                    '/accounts/dashboard/') + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=request.build_absolute_uri('/accounts/dashboard/'),
                # CRITICAL: Store our internal account ID in metadata to link the payment back
                metadata={
                    'credit_account_id': credit_account.id
                }
            )
            print(f"Created checkout session: {checkout_session['id']}")
            return JsonResponse({'sessionId': checkout_session['id']})
        except Exception as e:
            print(f"Error creating checkout session: {e}")
            return JsonResponse({'error': str(e)})


@csrf_exempt  # Stripe does not send a CSRF token
def stripe_webhook(request):
    # Retrieve the event payload and signature
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        print(f"Invalid payload: {e}")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        print(f"Invalid signature: {e}")
        return HttpResponse(status=400)

    print(f"Received webhook event: {event['type']}")

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        print(f"Processing completed session: {session.get('id')}")

        # Retrieve our metadata
        credit_account_id = session.get(
            'metadata', {}).get('credit_account_id')
        if not credit_account_id:
            print("Error: Missing credit_account_id in metadata")
            return HttpResponse(status=400, content='Error: Missing credit_account_id in metadata.')

        try:
            account = CreditAccount.objects.get(id=credit_account_id)
            # Convert from pesewas to cedis and ensure it's a Decimal
            from decimal import Decimal
            amount_paid = Decimal(str(session.get('amount_total', 0) / 100))
            print(
                f"Processing payment of ₵{amount_paid} for account {account.id}")

            # 1. Update the account balance
            account.balance += amount_paid

            # 2. Create a Transaction record with proper transaction_type
            Transaction.objects.create(
                account=account,
                amount=amount_paid,
                transaction_type=Transaction.TransactionType.PAYMENT,
                transaction_id=session.get(
                    'payment_intent', f"stripe_{session.get('id')}"),
                stripe_payment_intent=session.get('payment_intent'),
                description=f"Payment for {account.product.name}"
            )

            # 3. Update account status if needed
            if account.balance >= account.product.price and account.status != CreditAccount.Status.COMPLETED:
                account.status = CreditAccount.Status.COMPLETED
                print(f"Account {account.id} marked as completed")

                # Send completion email
                subject = f"Congratulations! Your plan for the {account.product.name} is complete!"
                message = render_to_string('emails/plan_completed.txt', {
                    'user': account.user,
                    'account': account,
                })
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[account.user.email],
                    fail_silently=True,  # Don't fail if email fails
                )

            account.save()
            print(f"Successfully processed payment for account {account.id}")

        except CreditAccount.DoesNotExist:
            print(f"CreditAccount not found: {credit_account_id}")
            return HttpResponse(status=404, content='Error: CreditAccount not found.')
        except Exception as e:
            print(f"Error processing payment: {e}")
            return HttpResponse(status=500, content=f'Error processing payment: {str(e)}')

    # Acknowledge receipt of the event
    return HttpResponse(status=200)


@login_required
def bnpl_checkout_view(request, product_id):
    # SECURITY: Only verified users can use BNPL
    if not request.user.is_verified:
        messages.error(
            request, "Your account must be verified to use this feature.")
        return redirect('accounts:dashboard')

    if hasattr(request.user, 'credit_account'):
        messages.error(request, "You already have an active credit account.")
        return redirect('accounts:dashboard')

    product = get_object_or_404(Product, id=product_id)

    # Check if user has an approved credit application
    credit_app = CreditApplication.objects.filter(
        user=request.user,
        product=product,
        status=CreditApplication.Status.APPROVED
    ).first()

    if not credit_app:
        messages.error(request, "You need to apply for credit first.")
        return redirect('accounts:credit_application', product_id=product_id)

    # Create a Stripe Customer if one doesn't exist
    if not request.user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=request.user.email,
            name=request.user.username,
        )
        request.user.stripe_customer_id = customer.id
        request.user.save()

    # Create the account record in our DB first, but as a CREDIT account
    # We will finalize it after they've added their card details
    account = CreditAccount.objects.create(
        user=request.user,
        product=product,
        account_type=CreditAccount.AccountType.CREDIT,
        status=CreditAccount.Status.ACTIVE,  # Still 'Active' until card is saved
        loan_amount=product.price,
        installment_count=credit_app.installment_count,
        installment_amount=round(
            product.price / credit_app.installment_count, 2),
        interest_rate=product.interest_rate,
    )

    # Create a Stripe Checkout session in 'setup' mode
    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        mode='setup',
        customer=request.user.stripe_customer_id,
        success_url=request.build_absolute_uri(
            f'/accounts/bnpl-success/{account.id}/'),
        cancel_url=request.build_absolute_uri('/accounts/dashboard/'),
    )

    return redirect(checkout_session.url, code=303)


# --- NEW VIEW: Handle successful card setup ---
@login_required
def bnpl_success_view(request, account_id):
    account = get_object_or_404(
        CreditAccount, id=account_id, user=request.user)

    # The plan is now officially starting
    account.status = CreditAccount.Status.REPAYING
    account.accepted_terms = True  # Implicitly accepted by completing checkout
    account.accepted_at = timezone.now()
    # Set the first payment date (e.g., one month from now)
    account.next_payment_due_date = timezone.now().date() + relativedelta(months=1)
    account.save()

    # TODO: Send a "BNPL Plan Started" email notification

    return redirect('accounts:dashboard')


@login_required
def create_customer_portal_session(request):
    # Ensure the user is a stripe customer
    if not request.user.stripe_customer_id:
        return redirect('accounts:dashboard')

    # The URL your user will be sent to after they are done managing their billing
    return_url = request.build_absolute_uri('/accounts/dashboard/')

    portal_session = stripe.billing_portal.Session.create(
        customer=request.user.stripe_customer_id,
        return_url=return_url,
    )
    # Redirect the user to the portal session URL
    return redirect(portal_session.url, code=303)


@staff_member_required  # Ensures only staff members can access this view
def business_dashboard_view(request):
    # Calculate raw counts for charts
    active_savings_count = CreditAccount.objects.filter(
        account_type='SAVINGS', status='ACTIVE').count()
    repaying_count = CreditAccount.objects.filter(status='REPAYING').count()
    overdue_count = CreditAccount.objects.filter(status='OVERDUE').count()
    paid_off_count = CreditAccount.objects.filter(status='PAID_OFF').count()
    completed_count = CreditAccount.objects.filter(status='COMPLETED').count()

    active_bnpl_count = repaying_count + overdue_count

    # Calculate default rate
    default_rate = (overdue_count / active_bnpl_count *
                    100) if active_bnpl_count > 0 else 0

    context = {
        'total_users': User.objects.count(),
        'verified_users': User.objects.filter(is_verified=True).count(),
        'active_savings_plans': active_savings_count,
        'active_bnpl_plans': active_bnpl_count,
        'overdue_plans': overdue_count,
        'default_rate': f"{default_rate:.2f}%",
        'total_paid_off': paid_off_count + completed_count,

        # --- Data specifically for Chart.js ---
        'chart_data': {
            'plan_status_labels': ['Active Savings', 'Active BNPL', 'Paid Off/Completed'],
            'plan_status_data': [active_savings_count, active_bnpl_count, paid_off_count + completed_count],

            'bnpl_health_labels': ['Currently Repaying', 'Overdue'],
            'bnpl_health_data': [repaying_count, overdue_count],
        }
    }
    return render(request, 'admin/business_dashboard.html', context)


@login_required
def payment_history_view(request):
    """Display payment history for the logged-in user"""
    try:
        credit_account = request.user.credit_account
        transactions = Transaction.objects.filter(
            account=credit_account).order_by('-timestamp')
    except CreditAccount.DoesNotExist:
        credit_account = None
        transactions = []

    context = {
        'credit_account': credit_account,
        'transactions': transactions,
    }
    return render(request, 'payment_history.html', context)


@csrf_exempt
def test_webhook(request):
    """Test endpoint for webhook debugging"""
    if request.method == 'POST':
        print("Test webhook received:")
        print(f"Headers: {dict(request.headers)}")
        print(f"Body: {request.body}")
        return HttpResponse(status=200)
    return HttpResponse("Test webhook endpoint", status=200)


def webhook_test_page(request):
    """Display webhook testing information"""
    return render(request, 'webhook_test.html')


def logout_view(request):
    """Custom logout view that redirects to login page"""
    from django.contrib.auth import logout
    logout(request)
    return redirect('accounts:login')
