# accounts/views.py
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib import messages
from .forms import CustomUserCreationForm, CreditApplicationForm, UserProfileForm, UserAddressForm, UserPreferencesForm, ProfilePictureForm
from .models import CreditAccount, Transaction, CreditApplication
from phones.models import Phone
import stripe
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from dateutil.relativedelta import relativedelta
from django.contrib.admin.views.decorators import staff_member_required
from .models import User
import random
import uuid
from decimal import Decimal
from .currency_utils import ghs_to_usd_cents, usd_cents_to_ghs, format_ghs_amount


def send_html_email(subject, template_name, context, recipient_list, fail_silently=True):
    """Send HTML email with text fallback using Gmail SMTP"""
    try:
        # Render HTML template
        html_content = render_to_string(f'emails/{template_name}.html', context)

        # Try to render text template as fallback
        try:
            text_content = render_to_string(f'emails/{template_name}.txt', context)
        except:
            # If no text template exists, create a simple text version
            text_content = f"Please view this email in an HTML-capable email client.\n\nSubject: {subject}"

        # Use EMAIL_FROM if available, otherwise DEFAULT_FROM_EMAIL
        from_email = getattr(settings, 'EMAIL_FROM', settings.DEFAULT_FROM_EMAIL)

        # Create email message
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=recipient_list
        )
        email.attach_alternative(html_content, "text/html")

        # Send email with enhanced error handling
        try:
            email.send(fail_silently=fail_silently)
            print(f"✅ HTML Email sent successfully via Gmail SMTP")
            print(f"   📧 To: {', '.join(recipient_list)}")
            print(f"   📝 Subject: {subject}")
            print(f"   📤 From: {from_email}")
            return True
        except Exception as e:
            print(f"❌ Email sending failed: {e}")
            print(f"   📧 To: {', '.join(recipient_list)}")
            print(f"   📝 Subject: {subject}")
            print(f"   📤 From: {from_email}")
            if not fail_silently:
                raise
            return False

    except Exception as e:
        print(f"❌ Error preparing HTML email: {e}")
        if not fail_silently:
            raise
        return False


@login_required
def support_view(request):
    """View for the support page"""
    return render(request, 'support.html')


def credit_eligibility_view(request):
    """View for explaining credit eligibility criteria"""
    return render(request, 'credit_eligibility.html')


@login_required
def documents_view(request):
    """View for the documents page"""
    try:
        credit_account = request.user.credit_account
    except CreditAccount.DoesNotExist:
        credit_account = None
        
    context = {
        'credit_account': credit_account,
    }
    return render(request, 'documents.html', context)


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

        # Check if the account is actually active (not completed/picked up)
        is_active_plan = credit_account.is_plan_active()

    except CreditAccount.DoesNotExist:
        credit_account = None
        transactions = []
        is_active_plan = False

    # Show phones if user has no account OR if their plan is completed
    phones = Phone.objects.filter(is_active=True, stock__gt=0) if not credit_account or not is_active_plan else []

    # Get user's credit applications (only those with valid phone references)
    credit_applications = CreditApplication.objects.filter(
        user=request.user,
        phone__isnull=False
    ).select_related('phone').order_by('-created_at')

    context = {
        'credit_account': credit_account,
        'transactions': transactions,
        'phones': phones,
        'is_active_plan': is_active_plan,
        'credit_applications': credit_applications,
    }
    return render(request, 'dashboard.html', context)


@login_required
def select_phone_view(request, phone_id):
    phone = get_object_or_404(Phone, id=phone_id)

    # Check if user has an existing account
    if hasattr(request.user, 'credit_account'):
        existing_account = request.user.credit_account

        # If user has an active plan (not completed), redirect to dashboard
        is_active_plan = existing_account.is_plan_active()

        if is_active_plan:
            messages.error(request, "You already have an active plan. Complete your current plan before selecting a new phone.")
            return redirect('accounts:dashboard')

        # If plan is completed, allow new plan selection
        # We'll handle this by creating a new account or updating the existing one
        messages.info(request, f"Starting a new plan for {phone.name}. Your previous plan history is preserved.")
    
    # Determine the account type based on the referrer
    referrer = request.META.get('HTTP_REFERER', '')
    
    # Default to SAVINGS (Save to Own) if coming from save_to_own view
    account_type = CreditAccount.AccountType.SAVINGS
    
    # If coming from buy_on_credit view, set to CREDIT (BNPL)
    if 'buy-on-credit' in referrer:
        account_type = CreditAccount.AccountType.CREDIT
        # For BNPL, redirect to credit application instead
        return redirect('accounts:credit_application', phone_id=phone_id)

    # Handle account creation or update
    if hasattr(request.user, 'credit_account'):
        # Update existing account for new plan
        account = request.user.credit_account
        account.phone = phone
        account.account_type = account_type
        account.status = CreditAccount.Status.PENDING
        account.balance = 0.00
        account.accepted_terms = False
        account.accepted_at = None
        account.loan_amount = None
        account.installment_amount = None
        account.next_payment_due_date = None
        account.last_payment_date = None
        account.is_active_plan = True  # Mark as active plan
        account.save()
    else:
        # Create new account for first-time users
        account = CreditAccount.objects.create(
            user=request.user,
            phone=phone,
            account_type=account_type,
            is_active_plan=True
        )

    # Redirect to the agreement page
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

        phone_name = account.phone.name if account.phone else "Unknown Phone"
        subject = f"Welcome to your FlexiFone Plan for the {phone_name}!"

        # Send HTML email
        send_html_email(
            subject=subject,
            template_name='welcome_email',
            context={
                'user': request.user,
                'account': account,
            },
            recipient_list=[request.user.email],
            fail_silently=True,
        )

        return redirect('accounts:dashboard')

    return render(request, 'agreement.html', {'account': account})


@login_required
def credit_application_view(request, phone_id):
    """Handle credit applications for BNPL purchases"""
    phone = get_object_or_404(Phone, id=phone_id)

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
        form.set_user(request.user)  # Set user for guarantor validation
        if form.is_valid():
            application = form.save(commit=False)
            application.user = request.user
            application.phone = phone

            # Store guarantor information
            application.guarantor_username = form.cleaned_data['guarantor_username']
            application.guarantor_national_id = form.cleaned_data['guarantor_national_id']

            # Validate guarantor and store validation result
            guarantor_validation = request.user.validate_guarantor(
                application.guarantor_username,
                application.guarantor_national_id
            )
            application.guarantor_validated = guarantor_validation['valid']
            application.guarantor_validation_notes = guarantor_validation.get('error', guarantor_validation.get('message', ''))

            # Progressive Credit System Logic
            monthly_income = form.cleaned_data['monthly_income']
            monthly_expenses = form.cleaned_data['monthly_expenses']

            # Update user's income information
            request.user.monthly_income = monthly_income

            # Update internal credit score based on current profile
            request.user.update_internal_credit_score()
            request.user.save()

            # Check if user can afford this phone with their current credit limit
            phone_price = float(phone.price)  # Ensure it's a float for calculations
            available_credit = float(request.user.get_available_credit_limit())  # Ensure it's a float

            # Store application details
            application.credit_score_at_time_of_application = request.user.internal_credit_score
            application.requested_loan_amount = phone.price  # Keep original Decimal for storage
            installment_count = int(form.cleaned_data.get('installment_count', 12))
            application.requested_installment_count = installment_count

            # Progressive approval logic - much more accessible!
            debt_to_income = (float(monthly_expenses) / float(monthly_income)) * 100 if monthly_income > 0 else 100

            # Check multiple approval criteria (user-friendly)
            approval_reasons = []
            decline_reasons = []

            # Guarantor validation check (new requirement)
            if application.guarantor_validated:
                approval_reasons.append("Valid guarantor provided and verified")
            else:
                decline_reasons.append(f"Guarantor validation failed: {application.guarantor_validation_notes}")

            # Basic eligibility check (now includes guarantor check)
            if request.user.is_verified and request.user.profile_completion_percentage() >= 70 and request.user.internal_credit_score >= 50:
                approval_reasons.append("Account verified and profile complete")
            else:
                decline_reasons.append("Complete your profile and verify your account first")

            # Credit limit check
            if available_credit >= phone_price:
                approval_reasons.append(f"Phone price (₵{phone_price}) within your credit limit (₵{available_credit} available)")
            else:
                decline_reasons.append(f"Phone price (₵{phone_price}) exceeds your available credit limit (₵{available_credit})")

            # Income check (more lenient) - Fix the division by ensuring proper types
            monthly_payment = float(phone_price) / installment_count
            if monthly_income >= monthly_payment * 2:  # Payment should be max 50% of income
                approval_reasons.append("Sufficient income for monthly payments")
            else:
                decline_reasons.append(f"Monthly payment (₵{monthly_payment:.2f}) too high for income (₵{monthly_income})")

            # Debt-to-income check (more lenient)
            if debt_to_income <= 70:  # Increased from 50% to 70%
                approval_reasons.append("Acceptable debt-to-income ratio")
            else:
                decline_reasons.append(f"Debt-to-income ratio too high ({debt_to_income:.1f}%)")

            # Make decision
            if len(decline_reasons) == 0:
                application.status = CreditApplication.Status.APPROVED
                application.decision_reason = "Approved: " + "; ".join(approval_reasons)
            else:
                application.status = CreditApplication.Status.DECLINED
                application.decision_reason = "Declined: " + "; ".join(decline_reasons)

            application.save()

            if application.status == CreditApplication.Status.APPROVED:
                messages.success(
                    request, "Credit application approved! Your application is now pending verification before you can proceed with payments. You'll be notified when verification is complete.")
                return redirect('accounts:dashboard')
            else:
                messages.error(
                    request, f"Credit application declined. Reason: {application.decision_reason}")
                return redirect('accounts:dashboard')
    else:
        form = CreditApplicationForm()
        form.set_user(request.user)  # Set user for guarantor validation

    context = {
        'form': form,
        'phone': phone,
        'monthly_payment_12': phone.monthly_payment_12_months,
        'monthly_payment_6': phone.monthly_payment_6_months,
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

    # Block payments for pending approval plans
    if credit_account.status == CreditAccount.Status.PENDING:
        messages.error(request, "Your plan is pending approval. Payments are not allowed until your plan is approved by our team.")
        return redirect('accounts:dashboard')

    # Block payments for declined plans
    if credit_account.status == CreditAccount.Status.DECLINED:
        messages.error(request, "Your plan has been declined. Please contact support for assistance.")
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
            amount_ghs = float(request.POST.get('amount'))
            amount_usd_cents = ghs_to_usd_cents(amount_ghs)
            print(
                f"Creating payment intent for amount: ₵{amount_ghs} (${amount_usd_cents/100:.2f} USD, {amount_usd_cents} cents)")

            credit_account = request.user.credit_account
            print(
                f"Credit account: {credit_account.id} for user: {request.user.username}")

            # Block payment intent creation for pending or declined plans
            if credit_account.status in [CreditAccount.Status.PENDING, CreditAccount.Status.DECLINED]:
                return JsonResponse({'error': 'Payment not allowed for plans with pending or declined status'}, status=400)

            payment_intent = stripe.PaymentIntent.create(
                amount=amount_usd_cents,
                currency=settings.STRIPE_CURRENCY,
                metadata={
                    'credit_account_id': credit_account.id,
                    'user_id': request.user.id,
                    'original_amount_ghs': str(amount_ghs)  # Store original GHS amount
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
                # Process payment and redirect to dashboard
                process_payment_success(request, payment_intent)
                return redirect('accounts:dashboard')
            else:
                print(
                    f"Payment intent not succeeded, status: {payment_intent.status}")
                messages.warning(
                    request, f"Payment not completed. Status: {payment_intent.status}")
        except stripe.error.StripeError as e:
            print(f"Stripe error: {str(e)}")
            messages.warning(request, f"Stripe error: {str(e)}")
        except Exception as e:
            print(f"Error processing payment: {str(e)}")
            messages.warning(request, f"Error processing payment: {str(e)}")
    else:
        print("No payment_intent_id provided")
        messages.warning(request, "No payment information found.")

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

        # Get the original GHS amount from metadata, or convert from USD
        original_ghs = payment_intent.metadata.get('original_amount_ghs')
        if original_ghs:
            amount_paid = Decimal(str(original_ghs))
        else:
            # Fallback: convert USD cents back to GHS
            amount_paid = usd_cents_to_ghs(payment_intent.amount)

        print(f"Amount paid: ₵{amount_paid}")

        # Record payment success and update credit metrics
        old_balance = account.balance
        upgrade_result = account.record_payment_success(amount_paid)
        print(f"Updated balance from ₵{old_balance} to ₵{account.balance}")

        # Create transaction record
        phone_name = account.phone.name if account.phone else "Unknown Phone"
        transaction = Transaction.objects.create(
            account=account,
            amount=amount_paid,
            transaction_type=Transaction.TransactionType.PAYMENT,
            transaction_id=payment_intent.id,
            stripe_payment_intent=payment_intent.id,
            description=f"Payment for {phone_name}"
        )
        print(f"Created transaction: {transaction.id}")

        # Notify user of credit tier upgrade if it happened
        if upgrade_result.get('upgraded'):
            old_tier = upgrade_result['old_tier']
            new_tier = upgrade_result['new_tier']
            new_limit = upgrade_result['new_limit']
            print(f"User {account.user.username} upgraded from {old_tier} to {new_tier}")
            # We'll show this message in the dashboard
        
        # Prepare result data
        phone_name = account.phone.name if account.phone else "Unknown Phone"
        phone_price = account.phone.price if account.phone else 0
        result = {
            'amount_paid': amount_paid,
            'remaining_balance': max(0, phone_price - account.balance),
            'product_name': phone_name,
            'plan_completed': False
        }

        # Check if account is eligible for completion
        if account.is_eligible_for_completion():
            # Mark as completed (admin will later mark as available for pickup)
            if account.mark_as_completed():
                print(f"Account {account.id} marked as completed")
                result['plan_completed'] = True

                # Send plan completion notification (not pickup notification yet)
                subject = f"🎉 Congratulations! Your {phone_name} plan is complete!"
                send_html_email(
                    subject=subject,
                    template_name='plan_completed',
                    context={
                        'user': account.user,
                        'account': account,
                    },
                    recipient_list=[account.user.email],
                    fail_silently=True,
                )

                # Send SMS notification for plan completion
                try:
                    from .sms_service import send_plan_completed_sms
                    sms_result = send_plan_completed_sms(account)
                    if sms_result['success']:
                        print(f"Plan completion SMS sent to {account.user.username}")
                    else:
                        print(f"Failed to send plan completion SMS: {sms_result.get('error')}")
                except Exception as e:
                    print(f"Error sending plan completion SMS: {str(e)}")

        account.save()
        print(f"Account saved successfully")
        
        # Enhanced success message with more details
        if account.status == CreditAccount.Status.COMPLETED:
            phone_name = account.phone.name if account.phone else "Unknown Phone"
            messages.success(
                request, f"Congratulations! Your payment of ₵{amount_paid} has been processed successfully. You have completed your payment plan for the {phone_name}!")
        else:
            remaining = account.remaining_balance
            messages.success(
                request, f"Payment of ₵{amount_paid} processed successfully! Remaining balance: ₵{remaining:.2f}")

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
            amount_ghs = float(request.POST.get('amount'))
            # Convert to USD cents for Stripe
            amount_usd_cents = ghs_to_usd_cents(amount_ghs)
            phone_name = credit_account.phone.name if credit_account.phone else "Unknown Phone"

            print(
                f"Creating checkout session for account {credit_account.id}, amount: ₵{amount_ghs} (${amount_usd_cents/100:.2f} USD)")

            # Create a new Checkout Session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[
                    {
                        'price_data': {
                            'currency': settings.STRIPE_CURRENCY,
                            'product_data': {
                                'name': f"Deposit for {phone_name}",
                                'description': f"FlexiFone payment (₵{amount_ghs} GHS equivalent)",
                            },
                            'unit_amount': amount_usd_cents,
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
                    'credit_account_id': credit_account.id,
                    'original_amount_ghs': str(amount_ghs)  # Store original GHS amount
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

            # Get the original GHS amount from metadata, or convert from USD
            original_ghs = session.get('metadata', {}).get('original_amount_ghs')
            if original_ghs:
                amount_paid = Decimal(str(original_ghs))
            else:
                # Fallback: convert USD cents back to GHS
                amount_paid = usd_cents_to_ghs(session.get('amount_total', 0))

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
                description=f"Payment for {account.phone.name if account.phone else 'Unknown Phone'}"
            )

            # 3. Check if account is eligible for completion
            if account.is_eligible_for_completion():
                # Mark as completed (admin will later mark as available for pickup)
                if account.mark_as_completed():
                    print(f"Account {account.id} marked as completed")

                    # Send completion and pickup notification email
                    phone_name = account.phone.name if account.phone else "Unknown Phone"
                subject = f"Congratulations! Your plan for the {phone_name} is complete!"
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
def bnpl_checkout_view(request, phone_id):
    # SECURITY: Only verified users can use BNPL
    if not request.user.is_verified:
        messages.error(
            request, "Your account must be verified to use this feature.")
        return redirect('accounts:dashboard')

    if hasattr(request.user, 'credit_account'):
        messages.error(request, "You already have an active credit account.")
        return redirect('accounts:dashboard')

    phone = get_object_or_404(Phone, id=phone_id)

    # Check if user has an approved and verified credit application
    credit_app = CreditApplication.objects.filter(
        user=request.user,
        phone=phone,
        status__in=[CreditApplication.Status.APPROVED, CreditApplication.Status.VERIFIED]
    ).first()

    if not credit_app:
        messages.error(request, "You need to apply for credit first.")
        return redirect('accounts:credit_application', phone_id=phone_id)

    # Check if the application is verified for payment
    if not credit_app.can_make_payments():
        if credit_app.status == CreditApplication.Status.APPROVED:
            messages.warning(request, "Your credit application is approved but pending verification. You'll be notified when you can proceed with payments.")
        else:
            messages.error(request, "Your credit application is not yet verified for payments.")
        return redirect('accounts:dashboard')

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
        phone=phone,
        account_type=CreditAccount.AccountType.CREDIT,
        status=CreditAccount.Status.ACTIVE,  # Still 'Active' until card is saved
        loan_amount=phone.price,
        installment_count=credit_app.requested_installment_count,
        installment_amount=round(
            phone.price / credit_app.requested_installment_count, 2),
        interest_rate=phone.interest_rate,
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

    # Send success message
    phone_name = account.phone.name if account.phone else "Unknown Phone"
    messages.success(
        request, f"Your credit plan for the {phone_name} has been set up successfully! Your first payment is due on {account.next_payment_due_date.strftime('%B %d, %Y')}.")

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


@staff_member_required
def business_dashboard_view(request):
    from django.db.models import Sum, Avg, Count, Q
    from django.utils import timezone
    from datetime import timedelta

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

    # Financial Analytics
    total_loan_value = CreditAccount.objects.filter(
        account_type='CREDIT',
        loan_amount__isnull=False
    ).aggregate(total=Sum('loan_amount'))['total'] or 0

    total_payments_received = Transaction.objects.filter(
        transaction_type='PAYMENT'
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Calculate outstanding balance correctly
    credit_accounts = CreditAccount.objects.filter(
        status__in=['REPAYING', 'OVERDUE'],
        loan_amount__isnull=False
    )
    outstanding_balance = 0
    for account in credit_accounts:
        if account.loan_amount and account.balance:
            remaining = account.loan_amount - account.balance
            outstanding_balance += max(0, remaining)

    # Calculate total amount paid (balance represents amount paid, not remaining)
    total_amount_paid = CreditAccount.objects.filter(
        account_type='CREDIT',
        balance__isnull=False
    ).aggregate(total=Sum('balance'))['total'] or 0

    # Credit Building Analytics
    credit_tier_distribution = User.objects.values('credit_tier').annotate(
        count=Count('id')
    ).order_by('credit_tier')

    avg_credit_score = User.objects.filter(
        internal_credit_score__gt=0
    ).aggregate(avg=Avg('internal_credit_score'))['avg'] or 0

    # Time-based Analytics (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    new_users_30d = User.objects.filter(date_joined__gte=thirty_days_ago).count()
    new_applications_30d = CreditApplication.objects.filter(
        created_at__gte=thirty_days_ago
    ).count()

    # Phone Analytics
    popular_phones = CreditAccount.objects.filter(
        phone__isnull=False
    ).values('phone__brand').annotate(
        count=Count('id')
    ).order_by('-count')[:5]

    context = {
        # Basic Metrics
        'total_users': User.objects.count(),
        'verified_users': User.objects.filter(is_verified=True).count(),
        'active_savings_plans': active_savings_count,
        'active_bnpl_plans': active_bnpl_count,
        'overdue_plans': overdue_count,
        'default_rate': f"{default_rate:.2f}%",
        'total_paid_off': paid_off_count + completed_count,

        # Financial Metrics
        'total_loan_value': total_loan_value,
        'total_payments_received': total_amount_paid,  # Use actual payments made
        'outstanding_balance': outstanding_balance,
        'collection_rate': f"{(float(total_amount_paid) / float(total_loan_value) * 100) if total_loan_value > 0 else 0:.1f}%",

        # Credit Building Metrics
        'avg_credit_score': f"{avg_credit_score:.0f}",
        'credit_tier_distribution': credit_tier_distribution,

        # Growth Metrics
        'new_users_30d': new_users_30d,
        'new_applications_30d': new_applications_30d,
        'popular_phones': popular_phones,

        # --- Data specifically for Chart.js ---
        'chart_data': {
            'plan_status_labels': ['Active Savings', 'Active BNPL', 'Paid Off/Completed'],
            'plan_status_data': [active_savings_count, active_bnpl_count, paid_off_count + completed_count],

            'bnpl_health_labels': ['Currently Repaying', 'Overdue'],
            'bnpl_health_data': [repaying_count, overdue_count],

            # Credit Tier Distribution
            'credit_tier_labels': [tier['credit_tier'] for tier in credit_tier_distribution],
            'credit_tier_data': [tier['count'] for tier in credit_tier_distribution],

            # Popular Phone Brands
            'phone_brand_labels': [phone['phone__brand'] for phone in popular_phones],
            'phone_brand_data': [phone['count'] for phone in popular_phones],
        }
    }
    
    # Show welcome message for analytics dashboard
    messages.success(request, "Welcome to the Business Analytics Dashboard!")
    
    return render(request, 'business_dashboard.html', context)


@staff_member_required
def mark_available_for_pickup_view(request, account_id):
    """Admin view to mark a single account as available for pickup"""
    account = get_object_or_404(CreditAccount, id=account_id)

    if account.status != CreditAccount.Status.COMPLETED:
        messages.error(request, f"Account {account.id} is not in completed status.")
        return redirect('accounts:customer_management')

    if account.mark_available_for_pickup(admin_user=request.user):
        messages.success(request, f"Device for {account.user.username} marked as available for pickup.")

        # Send pickup ready notifications
        try:
            # Send email notification
            subject = f"📱 Your {account.phone.name} is ready for pickup!"
            message = render_to_string('emails/pickup_ready.txt', {
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
            account.email_sent_at = timezone.now()

            # Send SMS notification
            from .sms_service import send_pickup_ready_sms
            sms_result = send_pickup_ready_sms(account)
            if sms_result['success']:
                print(f"Pickup ready SMS sent to {account.user.username}")
            else:
                print(f"Failed to send pickup ready SMS: {sms_result.get('error')}")

            account.save()

        except Exception as e:
            print(f"Error sending pickup notifications: {str(e)}")
            messages.warning(request, "Device marked ready but notification sending failed.")
    else:
        messages.error(request, "Failed to mark device as available for pickup.")

    return redirect('accounts:customer_management')

@staff_member_required
def bulk_mark_available_for_pickup_view(request):
    """Admin view to mark multiple accounts as available for pickup"""
    if request.method == 'POST':
        account_ids = request.POST.getlist('account_ids')
        if not account_ids:
            messages.error(request, "No accounts selected.")
            return redirect('accounts:customer_management')

        success_count = 0
        error_count = 0

        for account_id in account_ids:
            try:
                account = CreditAccount.objects.get(id=account_id, status=CreditAccount.Status.COMPLETED)
                if account.mark_available_for_pickup(admin_user=request.user):
                    success_count += 1

                    # Send notifications
                    try:
                        # Send email
                        subject = f"📱 Your {account.phone.name} is ready for pickup!"
                        message = render_to_string('emails/pickup_ready.txt', {
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
                        account.email_sent_at = timezone.now()

                        # Send SMS
                        from .sms_service import send_pickup_ready_sms
                        sms_result = send_pickup_ready_sms(account)
                        account.save()

                    except Exception as e:
                        print(f"Error sending notifications for account {account_id}: {str(e)}")
                else:
                    error_count += 1
            except CreditAccount.DoesNotExist:
                error_count += 1

        if success_count > 0:
            messages.success(request, f"Successfully marked {success_count} devices as available for pickup.")
        if error_count > 0:
            messages.error(request, f"Failed to process {error_count} accounts.")

    return redirect('accounts:customer_management')

@login_required
def confirm_pickup_view(request, account_id):
    """User view to confirm device pickup"""
    account = get_object_or_404(CreditAccount, id=account_id, user=request.user)

    if account.status != CreditAccount.Status.AVAILABLE_FOR_PICKUP:
        messages.error(request, "Device is not available for pickup confirmation.")
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        if account.confirm_pickup(confirmation_method='dashboard'):
            messages.success(request, f"Thank you! You've confirmed pickup of your {account.phone.name}. You can now select a new phone plan.")
        else:
            messages.error(request, "Failed to confirm pickup. Please try again.")

    return redirect('accounts:dashboard')

@staff_member_required
def customer_management_view(request):
    """View for managing customers, credit accounts, and account types"""
    # Get pending credit accounts
    pending_accounts = CreditAccount.objects.filter(status='PENDING')

    # Get completed accounts awaiting admin action
    completed_accounts = CreditAccount.objects.filter(status='COMPLETED').order_by('-completed_at')

    # Get accounts available for pickup
    available_for_pickup = CreditAccount.objects.filter(status='AVAILABLE_FOR_PICKUP').order_by('-admin_marked_ready_at')

    # Get picked up accounts
    picked_up_accounts = CreditAccount.objects.filter(status='PICKED_UP').order_by('-user_confirmed_pickup_at')

    # Get all credit accounts
    all_accounts = CreditAccount.objects.all().order_by('-created_at')

    # Get unverified users
    unverified_users = User.objects.filter(is_verified=False)
    
    # Get account type settings (placeholder for now)
    credit_settings = {
        'interest_rate': 15.00,
        'max_installments': 12,
        'min_credit_score': 600
    }
    
    savings_settings = {
        'min_deposit_percent': 10.00,
        'max_duration': 24,
        'bonus_rate': 0.00
    }
    
    context = {
        'pending_accounts': pending_accounts,
        'completed_accounts': completed_accounts,
        'available_for_pickup': available_for_pickup,
        'picked_up_accounts': picked_up_accounts,
        'all_accounts': all_accounts,
        'unverified_users': unverified_users,
        'credit_settings': credit_settings,
        'savings_settings': savings_settings
    }
    
    return render(request, 'customer_management.html', context)


@staff_member_required
def approve_account_view(request, account_id):
    """Approve a pending credit account"""
    if request.method == 'POST':
        account = get_object_or_404(CreditAccount, id=account_id)
        
        # Update account status
        account.status = CreditAccount.Status.ACTIVE
        account.save()
        
        messages.success(request, f"Credit account for {account.user.username} has been approved.")
    
    return redirect('accounts:customer_management')


@staff_member_required
def decline_account_view(request, account_id):
    """Decline a pending credit account"""
    if request.method == 'POST':
        account = get_object_or_404(CreditAccount, id=account_id)
        
        # Update account status
        account.status = CreditAccount.Status.DECLINED
        account.save()
        
        messages.success(request, f"Credit account for {account.user.username} has been declined.")
    
    return redirect('accounts:customer_management')


@staff_member_required
def verify_user_view(request, user_id):
    """Verify a user's identity"""
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        
        # Update user verification status
        user.is_verified = True
        user.save()
        
        messages.success(request, f"User {user.username} has been verified.")
    
    return redirect('accounts:customer_management')


@staff_member_required
def account_detail_view(request, account_id):
    """View details of a specific credit account"""
    account = get_object_or_404(CreditAccount, id=account_id)
    transactions = account.transactions.all().order_by('-timestamp')
    
    context = {
        'account': account,
        'transactions': transactions
    }
    
    return render(request, 'account_detail.html', context)


@staff_member_required
def update_account_settings_view(request):
    """Update account type settings"""
    if request.method == 'POST':
        account_type = request.POST.get('account_type')
        
        if account_type == 'CREDIT':
            # Update BNPL settings
            interest_rate = request.POST.get('interest_rate')
            max_installments = request.POST.get('max_installments')
            min_credit_score = request.POST.get('min_credit_score')
            
            # Here you would save these settings to your database
            # For now, just show a success message
            messages.success(request, "BNPL settings updated successfully.")
            
        elif account_type == 'SAVINGS':
            # Update Savings settings
            min_deposit_percent = request.POST.get('min_deposit_percent')
            max_duration = request.POST.get('max_duration')
            bonus_rate = request.POST.get('bonus_rate')
            
            # Here you would save these settings to your database
            # For now, just show a success message
            messages.success(request, "Savings settings updated successfully.")
    
    return redirect('accounts:customer_management')


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


@login_required
def cancel_plan_view(request):
    """View for cancelling a credit or savings plan"""
    try:
        credit_account = request.user.credit_account
    except CreditAccount.DoesNotExist:
        messages.error(request, "You don't have an active plan to cancel.")
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        # Store the phone for later use
        phone = credit_account.phone
        phone_name = phone.name if phone else "Unknown Phone"

        # Create a record of transactions for accounting purposes
        if credit_account.balance > 0:
            # If there's a balance, create a refund transaction
            Transaction.objects.create(
                account=credit_account,
                amount=credit_account.balance,
                transaction_type=Transaction.TransactionType.REFUND,
                transaction_id=f"refund_{uuid.uuid4()}",
                description=f"Refund for cancelled plan: {phone_name}"
            )

        # Delete the credit account
        credit_account.delete()

        messages.success(request, f"Your plan for the {phone_name} has been cancelled successfully. You can now choose a different plan.")
        return redirect('accounts:dashboard')
    
    return render(request, 'cancel_plan.html', {'credit_account': credit_account})


@staff_member_required
def credit_applications_view(request):
    """View for managing credit applications and verification"""
    # Get applications that need verification
    approved_applications = CreditApplication.objects.filter(
        status=CreditApplication.Status.APPROVED
    ).select_related('user', 'phone').order_by('-created_at')

    # Get verified applications
    verified_applications = CreditApplication.objects.filter(
        status=CreditApplication.Status.VERIFIED
    ).select_related('user', 'phone', 'verified_by').order_by('-verified_at')

    context = {
        'approved_applications': approved_applications,
        'verified_applications': verified_applications,
    }

    return render(request, 'admin/credit_applications.html', context)


@staff_member_required
def verify_credit_application_view(request, application_id):
    """Verify a credit application for payment processing"""
    if request.method == 'POST':
        application = get_object_or_404(CreditApplication, id=application_id)
        verification_notes = request.POST.get('verification_notes', '')

        if application.verify_for_payment(request.user, verification_notes):
            messages.success(request, f"Credit application for {application.user.username} has been verified for payment processing.")

            # Send notification email to user
            phone_name = application.phone.name if application.phone else "your selected phone"
            subject = f"Your credit application for {phone_name} is verified!"
            send_html_email(
                subject=subject,
                template_name='credit_verified',
                context={
                    'user': application.user,
                    'application': application,
                },
                recipient_list=[application.user.email],
                fail_silently=True,
            )
        else:
            messages.error(request, "Failed to verify the credit application.")

    return redirect('accounts:credit_applications')


@staff_member_required
def test_email_view(request):
    """Test email sending functionality"""
    if request.method == 'POST':
        test_email = request.POST.get('test_email', 'test@example.com')

        # Send test email
        success = send_html_email(
            subject="FlexiFone Email Test",
            template_name='credit_verified',  # Using existing template
            context={
                'user': request.user,
                'application': {
                    'phone': {'name': 'Test Phone', 'price': '1000'},
                    'requested_loan_amount': '800',
                    'requested_installment_count': 12
                }
            },
            recipient_list=[test_email],
            fail_silently=False
        )

        if success:
            messages.success(request, f"Test email sent successfully to {test_email}")
        else:
            messages.error(request, f"Failed to send test email to {test_email}")

    return render(request, 'admin/test_email.html')


# Profile Views
@login_required
def profile_view(request):
    """Display user profile information"""
    context = {
        'user': request.user,
        'profile_completion': request.user.profile_completion_percentage(),
        'age': request.user.get_age(),
        'full_address': request.user.get_full_address(),
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def profile_edit_view(request):
    """Edit user profile information"""
    if request.method == 'POST':
        profile_form = UserProfileForm(request.POST, instance=request.user)
        address_form = UserAddressForm(request.POST, instance=request.user)
        preferences_form = UserPreferencesForm(request.POST, instance=request.user)

        if profile_form.is_valid() and address_form.is_valid() and preferences_form.is_valid():
            profile_form.save()
            address_form.save()
            preferences_form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('accounts:profile')
    else:
        profile_form = UserProfileForm(instance=request.user)
        address_form = UserAddressForm(instance=request.user)
        preferences_form = UserPreferencesForm(instance=request.user)

    context = {
        'profile_form': profile_form,
        'address_form': address_form,
        'preferences_form': preferences_form,
        'profile_completion': request.user.profile_completion_percentage(),
    }
    return render(request, 'accounts/profile_edit.html', context)


@login_required
def profile_picture_view(request):
    """Upload or update profile picture"""
    if request.method == 'POST':
        # Check if user wants to remove the picture
        if request.POST.get('remove_picture'):
            if request.user.profile_picture:
                request.user.profile_picture.delete()
                request.user.profile_picture = None
                request.user.save()
                messages.success(request, 'Your profile picture has been removed successfully!')
            return redirect('accounts:profile')

        # Handle picture upload
        form = ProfilePictureForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile picture has been updated successfully!')
            return redirect('accounts:profile')
    else:
        form = ProfilePictureForm(instance=request.user)

    context = {
        'form': form,
    }
    return render(request, 'accounts/profile_picture.html', context)


@login_required
def change_password_view(request):
    """Change user password"""
    from django.contrib.auth.forms import PasswordChangeForm
    from django.contrib.auth import update_session_auth_hash

    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Your password has been changed successfully!')
            return redirect('accounts:profile')
    else:
        form = PasswordChangeForm(request.user)

    context = {
        'form': form,
    }
    return render(request, 'accounts/change_password.html', context)


@login_required
def credit_building_dashboard_view(request):
    """Display user's credit building progress and tier information"""
    user = request.user

    # Update internal credit score
    user.update_internal_credit_score()

    # Get credit progress information
    credit_progress = user.get_credit_progress()
    tier_info = user.get_credit_tier_info()

    # Get available phones based on credit limit
    from phones.models import Phone
    available_phones = Phone.objects.filter(
        price__lte=user.get_available_credit_limit(),
        is_available=True
    ).order_by('price')

    # Get phones in next tier (aspirational)
    next_tier_phones = []
    if credit_progress.get('next_tier'):
        next_tier_info = {
            user.CreditTier.BRONZE: {'min_limit': 1000, 'max_limit': 2500},
            user.CreditTier.SILVER: {'min_limit': 2500, 'max_limit': 5000},
            user.CreditTier.GOLD: {'min_limit': 5000, 'max_limit': 10000},
            user.CreditTier.PLATINUM: {'min_limit': 10000, 'max_limit': 50000},
        }.get(credit_progress['next_tier'], {'min_limit': 0, 'max_limit': 0})

        next_tier_phones = Phone.objects.filter(
            price__gt=user.get_available_credit_limit(),
            price__lte=next_tier_info['max_limit'],
            is_available=True
        ).order_by('price')[:3]  # Show top 3 aspirational phones

    # Calculate credit utilization
    try:
        current_usage = user.credit_account.remaining_balance if hasattr(user, 'credit_account') else 0
        credit_utilization = (current_usage / user.credit_limit * 100) if user.credit_limit > 0 else 0
    except:
        current_usage = 0
        credit_utilization = 0

    # Get recent payment history
    recent_payments = []
    if hasattr(user, 'credit_account'):
        recent_payments = user.credit_account.transactions.filter(
            transaction_type='PAYMENT'
        ).order_by('-timestamp')[:5]

    context = {
        'user': user,
        'credit_progress': credit_progress,
        'tier_info': tier_info,
        'available_phones': available_phones,
        'next_tier_phones': next_tier_phones,
        'current_usage': current_usage,
        'credit_utilization': credit_utilization,
        'recent_payments': recent_payments,
        'available_credit': user.get_available_credit_limit(),
    }

    return render(request, 'accounts/credit_building_dashboard.html', context)
