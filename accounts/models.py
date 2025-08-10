# accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import Sum
from decimal import Decimal
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

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

# 2. Model for the phones we are selling


class Product(models.Model):
    BRAND_CHOICES = [
        ('APPLE', 'Apple'),
        ('SAMSUNG', 'Samsung'),
        ('GOOGLE', 'Google'),
        ('ONEPLUS', 'OnePlus'),
        ('XIAOMI', 'Xiaomi'),
        ('OTHER', 'Other'),
    ]

    name = models.CharField(max_length=100)
    brand = models.CharField(
        max_length=20, choices=BRAND_CHOICES, default='OTHER')
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    stock_quantity = models.IntegerField(default=0)
    credit_available = models.BooleanField(
        default=True, help_text="Whether this product is available for credit purchase")
    min_credit_score = models.IntegerField(
        default=600, help_text="Minimum credit score required for this product")

    # Credit terms
    max_installments = models.IntegerField(
        default=12, help_text="Maximum number of installments allowed")
    interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00, help_text="Annual interest rate (%)")

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True )

    def __str__(self):
        return f"{self.brand} {self.name}"

    @property
    def monthly_payment_12_months(self):
        """Calculate monthly payment for 12-month term"""
        if self.interest_rate > 0:
            # Simple interest calculation
            total_interest = (self.price * self.interest_rate / 100)
            total_amount = self.price + total_interest
            return total_amount / 12
        return self.price / 12

    @property
    def monthly_payment_6_months(self):
        """Calculate monthly payment for 6-month term"""
        if self.interest_rate > 0:
            total_interest = (self.price * self.interest_rate / 100)
            total_amount = self.price + total_interest
            return total_amount / 6
        return self.price / 6

# 3. The core credit/savings account for each user's goal


class CreditAccount(models.Model):
    class AccountType(models.TextChoices):
        SAVINGS = 'SAVINGS', 'Save-to-Own'
        CREDIT = 'CREDIT', 'Buy Now, Pay Later'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Approval'
        ACTIVE = 'ACTIVE', 'Active'
        COMPLETED = 'COMPLETED', 'Completed'
        CLOSED = 'CLOSED', 'Closed'
        REPAYING = 'REPAYING', 'Repaying'
        OVERDUE = 'OVERDUE', 'Overdue'
        PAID_OFF = 'PAID_OFF', 'Paid Off'
        DECLINED = 'DECLINED', 'Declined'

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='credit_account')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
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

    def __str__(self):
        return f"{self.user.username}'s {self.account_type} account for {self.product.name}"

    @property
    def remaining_balance(self):
        if self.account_type == self.AccountType.CREDIT:
            return (self.loan_amount or 0) - self.balance
        return self.product.price - self.balance

    @property
    def progress_percentage(self):
        if self.account_type == self.AccountType.CREDIT:
            total = self.loan_amount or 0
        else:
            total = self.product.price
        if total > 0:
            return int((self.balance / total) * 100)
        return 0

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

# 4. A log for every payment transaction


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

# 5. Credit Application model


class CreditApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        APPROVED = 'APPROVED', 'Approved'
        DECLINED = 'DECLINED', 'Declined'
        EXPIRED = 'EXPIRED', 'Expired'

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='credit_applications')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    requested_amount = models.DecimalField(max_digits=10, decimal_places=2)
    installment_count = models.IntegerField(default=12)
    monthly_income = models.DecimalField(max_digits=10, decimal_places=2)
    employment_status = models.CharField(max_length=50)
    monthly_expenses = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING)
    credit_score = models.IntegerField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Credit application by {self.user.username} for {self.product.name}"
