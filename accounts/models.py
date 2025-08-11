# accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import Sum
from decimal import Decimal
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
import uuid

# 1. Extend the default User model


class User(AbstractUser):
    national_id = models.CharField(
        max_length=20, unique=True, help_text="National ID or Passport Number")
    is_verified = models.BooleanField(
        default=False, help_text="Set to true if user's ID has been manually verified by an admin.")
    stripe_customer_id = models.CharField(
        max_length=255, blank=True, null=True)
    credit_score = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(850)],
        help_text="Credit score for BNPL eligibility")
    monthly_income = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Monthly income for credit assessment")

    def is_eligible_for_credit(self):
        """Check if user is eligible for credit purchases"""
        return self.is_verified and self.credit_score >= 600

# 2. The core credit/savings account for each user's goal


class CreditAccount(models.Model):
    class AccountType(models.TextChoices):
        SAVINGS = 'SAVINGS', 'Save-to-Own'
        CREDIT = 'CREDIT', 'Buy Now, Pay Later'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Approval'
        ACTIVE = 'ACTIVE', 'Active'
        COMPLETED = 'COMPLETED', 'Plan Completed'
        DELIVERED = 'DELIVERED', 'Ready for Pickup'
        PICKED_UP = 'PICKED_UP', 'Device Picked Up'
        CLOSED = 'CLOSED', 'Closed'
        REPAYING = 'REPAYING', 'Repaying'
        OVERDUE = 'OVERDUE', 'Overdue'
        PAID_OFF = 'PAID_OFF', 'Paid Off'
        DECLINED = 'DECLINED', 'Declined'

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='credit_account')
    phone = models.ForeignKey('phones.Phone', on_delete=models.PROTECT, null=True, blank=True)
    balance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    account_type = models.CharField(
        max_length=10, choices=AccountType.choices, default=AccountType.CREDIT)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING)

    # Credit-specific fields
    loan_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    installment_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    installment_count = models.IntegerField(
        default=12, help_text="Number of installments")
    interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00)
    next_payment_due_date = models.DateField(null=True, blank=True)
    last_payment_date = models.DateField(null=True, blank=True)

    # Terms and conditions
    accepted_terms = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Plan completion tracking
    completed_at = models.DateTimeField(null=True, blank=True, help_text="When the plan was completed")
    pickup_notified_at = models.DateTimeField(null=True, blank=True, help_text="When pickup notification was sent")
    pickup_location = models.CharField(max_length=255, default="FlexiFone Shop, Tamale, Gumbihini", help_text="Pickup location")
    pickup_instructions = models.TextField(blank=True, help_text="Special pickup instructions")
    is_active_plan = models.BooleanField(default=True, help_text="Whether this is the user's active plan")

    def __str__(self):
        phone_name = self.phone.name if self.phone else "Unknown Phone"
        return f"{self.user.username}'s {self.account_type} account for {phone_name}"

    @property
    def remaining_balance(self):
        if self.account_type == self.AccountType.CREDIT:
            return (self.loan_amount or 0) - self.balance
        elif self.phone:
            return self.phone.price - self.balance
        else:
            return 0 - self.balance  # Fallback for accounts without phone

    @property
    def progress_percentage(self):
        if self.account_type == self.AccountType.CREDIT:
            total = self.loan_amount or 0
        elif self.phone:
            total = self.phone.price
        else:
            total = 0  # Fallback for accounts without phone

        if total > 0:
            return int((self.balance / total) * 100)
        return 0

    def is_eligible_for_completion(self):
        """Check if the plan is eligible for completion"""
        if self.status in [self.Status.COMPLETED, self.Status.DELIVERED, self.Status.PICKED_UP]:
            return False

        if self.account_type == self.AccountType.CREDIT:
            # For credit accounts, check if all installments are paid
            return self.balance >= (self.loan_amount or 0)
        else:
            # For savings accounts, check if full phone price is paid
            phone_price = self.phone.price if self.phone else 0
            return self.balance >= phone_price

    def mark_as_completed(self):
        """Mark the plan as completed and ready for pickup"""
        from django.utils import timezone

        if self.is_eligible_for_completion():
            self.status = self.Status.COMPLETED
            self.completed_at = timezone.now()
            self.save()
            return True
        return False

    def mark_as_delivered(self):
        """Mark the device as ready for pickup"""
        from django.utils import timezone

        if self.status == self.Status.COMPLETED:
            self.status = self.Status.DELIVERED
            self.pickup_notified_at = timezone.now()
            self.save()
            return True
        return False

    def mark_as_picked_up(self):
        """Mark the device as picked up by customer"""
        if self.status == self.Status.DELIVERED:
            self.status = self.Status.PICKED_UP
            self.is_active_plan = False  # No longer active
            self.save()
            return True
        return False

    @property
    def remaining_installments(self):
        """Calculate remaining number of installments"""
        if self.installment_amount and self.installment_amount > 0:
            return int(self.remaining_balance / self.installment_amount)
        return 0

    @property
    def is_overdue(self):
        """Check if payment is overdue"""
        if self.next_payment_due_date and self.status == self.Status.REPAYING:
            return timezone.now().date() > self.next_payment_due_date
        return False

# 3. A log for every payment transaction


class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        PAYMENT = 'PAYMENT', 'Payment'
        REFUND = 'REFUND', 'Refund'
        FEE = 'FEE', 'Fee'
        LATE_FEE = 'LATE_FEE', 'Late Fee'

    account = models.ForeignKey(
        CreditAccount, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(
        max_length=10, choices=TransactionType.choices, default=TransactionType.PAYMENT)
    timestamp = models.DateTimeField(auto_now_add=True)
    transaction_id = models.CharField(
        max_length=100, unique=True)  # From payment gateway
    description = models.CharField(max_length=255, blank=True)
    stripe_payment_intent = models.CharField(
        max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.transaction_type} of ₵{self.amount} for {self.account.user.username}"

# 4. Credit Application model


class CreditApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        APPROVED = 'APPROVED', 'Approved'
        DECLINED = 'DECLINED', 'Declined'
        EXPIRED = 'EXPIRED', 'Expired'

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='credit_applications')
    phone = models.ForeignKey('phones.Phone', on_delete=models.PROTECT, null=True, blank=True)
    monthly_income = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Applicant's monthly income")
    employment_status = models.CharField(max_length=50, null=True, blank=True)
    monthly_expenses = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Applicant's monthly expenses")
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING)
    decision_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Fields added in migration 0006
    admin_notes = models.TextField(blank=True, help_text='Notes for internal use')
    credit_score_at_time_of_application = models.IntegerField(
        default=0, 
        help_text="Applicant's credit score when application was submitted",
        validators=[MinValueValidator(0), MaxValueValidator(850)]
    )
    employer_name = models.CharField(max_length=100, null=True, blank=True)
    employment_duration = models.IntegerField(null=True, blank=True, help_text='Employment duration in months')
    requested_installment_count = models.IntegerField(default=12)
    requested_loan_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Credit application by {self.user.username} for {self.phone.name}"
