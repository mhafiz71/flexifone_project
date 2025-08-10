# accounts/jobs.py
import stripe
from django.conf import settings
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from .models import CreditAccount, Transaction
from django.core.mail import send_mail
from django.template.loader import render_to_string

stripe.api_key = settings.STRIPE_SECRET_KEY

def process_daily_installments():
    """
    This job runs daily, finds all BNPL accounts with a due payment,
    and attempts to charge the customer's saved card.
    """
    print("--- Running Daily Installment Job ---")
    today = timezone.now().date()
    
    # Find accounts that are due for payment
    due_accounts = CreditAccount.objects.filter(
        account_type=CreditAccount.AccountType.CREDIT,
        status=CreditAccount.Status.REPAYING,
        next_payment_due_date__lte=today
    )

    for account in due_accounts:
        print(f"Processing payment for account {account.id} for user {account.user.username}")
        
        try:
            # Create a PaymentIntent to charge the customer off-session
            payment_intent = stripe.PaymentIntent.create(
                amount=int(account.installment_amount * 100), # Amount in pesewas
                currency='ghs',
                customer=account.user.stripe_customer_id,
                # This is crucial: it finds the default payment method saved to the customer
                payment_method=stripe.Customer.retrieve(account.user.stripe_customer_id)['invoice_settings']['default_payment_method'],
                off_session=True, # Indicates the customer is not present
                confirm=True, # Attempts to charge immediately
            )

            # If we reach here, the payment succeeded
            account.balance += account.installment_amount
            Transaction.objects.create(
                account=account,
                amount=account.installment_amount,
                transaction_id=payment_intent.id
            )

            # Check if the loan is fully paid off
            if account.balance >= account.loan_amount:
                account.status = CreditAccount.Status.PAID_OFF
                account.next_payment_due_date = None
                print(f"Account {account.id} is now fully paid off.")
            else:
                # Schedule the next payment
                account.next_payment_due_date = today + relativedelta(months=1)
                print(f"Account {account.id} payment successful. Next payment due {account.next_payment_due_date}")

            account.save()

        except stripe.error.CardError as e:
            # The card has been declined
            print(f"ERROR: Card declined for account {account.id}. Error: {e.error.message}")
            account.status = CreditAccount.Status.OVERDUE
            account.save()
            
            subject = f"Action Required: Your FlexiFone Payment Failed"
            message = render_to_string('emails/payment_failed.txt', {
                'user': account.user,
                'account': account,
                'error_message': e.error.message, # Pass the specific error from Stripe
            })
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[account.user.email],
                fail_silently=False,
            )
            
        except Exception as e:
            print(f"ERROR: An unexpected error occurred for account {account.id}: {e}")
            # Potentially retry later or flag for manual review