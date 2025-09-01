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
    # Basic Profile Information
    national_id = models.CharField(
        max_length=20, unique=True, help_text="National ID or Passport Number")
    is_verified = models.BooleanField(
        default=False, help_text="Set to true if user's ID has been manually verified by an admin.")

    # Contact Information
    phone_number = models.CharField(
        max_length=15, blank=True, null=True, help_text="Primary phone number")
    alternate_phone = models.CharField(
        max_length=15, blank=True, null=True, help_text="Alternate phone number")

    # Address Information
    address_line_1 = models.CharField(
        max_length=255, blank=True, null=True, help_text="Street address")
    address_line_2 = models.CharField(
        max_length=255, blank=True, null=True, help_text="Apartment, suite, etc.")
    city = models.CharField(
        max_length=100, blank=True, null=True, help_text="City")
    region = models.CharField(
        max_length=100, blank=True, null=True, help_text="Region/State")
    postal_code = models.CharField(
        max_length=20, blank=True, null=True, help_text="Postal/ZIP code")

    # Personal Information
    date_of_birth = models.DateField(
        blank=True, null=True, help_text="Date of birth")
    gender = models.CharField(
        max_length=10,
        choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other'), ('P', 'Prefer not to say')],
        blank=True, null=True, help_text="Gender")
    occupation = models.CharField(
        max_length=100, blank=True, null=True, help_text="Current occupation")
    employer = models.CharField(
        max_length=100, blank=True, null=True, help_text="Current employer")

    # Profile Picture
    profile_picture = models.ImageField(
        upload_to='profile_pictures/', blank=True, null=True,
        help_text="Profile picture")

    # Financial Information
    stripe_customer_id = models.CharField(
        max_length=255, blank=True, null=True)
    credit_score = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(850)],
        help_text="External credit score for reference")
    monthly_income = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Monthly income for credit assessment")

    # Progressive Credit System
    class CreditTier(models.TextChoices):
        STARTER = 'STARTER', 'Starter (₵500-1000)'
        BRONZE = 'BRONZE', 'Bronze (₵1000-2500)'
        SILVER = 'SILVER', 'Silver (₵2500-5000)'
        GOLD = 'GOLD', 'Gold (₵5000-10000)'
        PLATINUM = 'PLATINUM', 'Platinum (₵10000+)'

    credit_tier = models.CharField(
        max_length=20, choices=CreditTier.choices, default=CreditTier.STARTER,
        help_text="Current credit tier in FlexiFone system")
    credit_limit = models.DecimalField(
        max_digits=10, decimal_places=2, default=500.00,
        help_text="Current credit limit in GHS")
    internal_credit_score = models.IntegerField(
        default=100, validators=[MinValueValidator(0), MaxValueValidator(1000)],
        help_text="Internal FlexiFone credit score (0-1000)")
    successful_payments = models.IntegerField(
        default=0, help_text="Number of successful payments made")
    missed_payments = models.IntegerField(
        default=0, help_text="Number of missed payments")
    total_credit_used = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00,
        help_text="Total credit amount used historically")
    last_credit_review = models.DateTimeField(
        auto_now_add=True, help_text="Last time credit tier was reviewed")

    # Profile Settings
    email_notifications = models.BooleanField(
        default=True, help_text="Receive email notifications")
    sms_notifications = models.BooleanField(
        default=True, help_text="Receive SMS notifications")
    marketing_emails = models.BooleanField(
        default=False, help_text="Receive marketing emails")

    # Guarantor Information
    guarantor_username = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Username of the guarantor (must be a verified FlexiFone user)"
    )
    guarantor_national_id = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="National ID of the guarantor"
    )
    guarantor_verified = models.BooleanField(
        default=False,
        help_text="Whether the guarantor information has been verified"
    )
    guarantor_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the guarantor was verified"
    )
    guarantor_verified_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_guarantees',
        help_text="Admin who verified the guarantor"
    )

    # Timestamps
    profile_updated_at = models.DateTimeField(auto_now=True)

    def is_eligible_for_credit(self):
        """Check if user is eligible for credit purchases using progressive system"""
        # Much more accessible requirements
        return (
            self.is_verified and
            self.profile_completion_percentage() >= 70 and
            self.internal_credit_score >= 50 and  # Very low threshold
            self.has_valid_guarantor()  # New guarantor requirement
        )

    def has_valid_guarantor(self):
        """Check if user has a valid guarantor"""
        if not self.guarantor_username or not self.guarantor_national_id:
            return False

        # Check if guarantor exists and is verified
        try:
            guarantor = User.objects.get(username=self.guarantor_username)
            return (
                guarantor.is_verified and
                guarantor.national_id and  # Guarantor must have national ID
                guarantor.internal_credit_score >= 200 and  # Higher requirement for guarantors
                guarantor != self  # Cannot guarantee yourself
            )
        except User.DoesNotExist:
            return False

    def validate_guarantor(self, username, national_id):
        """Validate guarantor information and return validation result"""
        if not username or not national_id:
            return {
                'valid': False,
                'error': 'Both guarantor username and national ID are required'
            }

        if username == self.username:
            return {
                'valid': False,
                'error': 'You cannot be your own guarantor'
            }

        try:
            guarantor = User.objects.get(username=username)
        except User.DoesNotExist:
            return {
                'valid': False,
                'error': f'User with username "{username}" does not exist'
            }

        if not guarantor.is_verified:
            return {
                'valid': False,
                'error': 'Guarantor must be a verified FlexiFone user'
            }

        if not guarantor.national_id:
            return {
                'valid': False,
                'error': 'Guarantor must have a national ID on file'
            }

        if guarantor.national_id != national_id:
            return {
                'valid': False,
                'error': 'Guarantor national ID does not match our records'
            }

        if guarantor.internal_credit_score < 200:
            return {
                'valid': False,
                'error': f'Guarantor must have a credit score of at least 200 (current: {guarantor.internal_credit_score})'
            }

        return {
            'valid': True,
            'guarantor': guarantor,
            'message': f'Guarantor {guarantor.get_full_name() or guarantor.username} is valid'
        }

    def get_available_credit_limit(self):
        """Get available credit limit based on current usage"""
        try:
            current_usage = self.credit_account.remaining_balance if hasattr(self, 'credit_account') else 0
            return max(0, self.credit_limit - current_usage)
        except:
            return self.credit_limit

    def can_afford_phone(self, phone_price):
        """Check if user can afford a phone with their current credit limit"""
        return self.get_available_credit_limit() >= phone_price

    def get_credit_tier_info(self):
        """Get detailed information about current credit tier"""
        tier_info = {
            self.CreditTier.STARTER: {
                'name': 'Starter',
                'limit_range': '₵500 - ₵1,000',
                'min_limit': 500,
                'max_limit': 1000,
                'requirements': 'Complete profile + Account verification',
                'benefits': ['Access to basic phones', 'Build credit history'],
                'next_tier': 'Bronze'
            },
            self.CreditTier.BRONZE: {
                'name': 'Bronze',
                'limit_range': '₵1,000 - ₵2,500',
                'min_limit': 1000,
                'max_limit': 2500,
                'requirements': '3+ successful payments + 200+ internal score',
                'benefits': ['Access to mid-range phones', 'Lower interest rates'],
                'next_tier': 'Silver'
            },
            self.CreditTier.SILVER: {
                'name': 'Silver',
                'limit_range': '₵2,500 - ₵5,000',
                'min_limit': 2500,
                'max_limit': 5000,
                'requirements': '6+ successful payments + 400+ internal score',
                'benefits': ['Access to premium phones', 'Extended payment terms'],
                'next_tier': 'Gold'
            },
            self.CreditTier.GOLD: {
                'name': 'Gold',
                'limit_range': '₵5,000 - ₵10,000',
                'min_limit': 5000,
                'max_limit': 10000,
                'requirements': '12+ successful payments + 600+ internal score',
                'benefits': ['Access to flagship phones', 'Priority support'],
                'next_tier': 'Platinum'
            },
            self.CreditTier.PLATINUM: {
                'name': 'Platinum',
                'limit_range': '₵10,000+',
                'min_limit': 10000,
                'max_limit': 50000,
                'requirements': '24+ successful payments + 800+ internal score',
                'benefits': ['Unlimited phone access', 'VIP treatment', 'Special offers'],
                'next_tier': None
            }
        }
        return tier_info.get(self.credit_tier, tier_info[self.CreditTier.STARTER])

    def calculate_internal_credit_score(self):
        """Calculate internal credit score based on FlexiFone activity"""
        base_score = 100  # Everyone starts with 100

        # Payment history (most important factor - 60% weight)
        if self.successful_payments + self.missed_payments > 0:
            payment_ratio = self.successful_payments / (self.successful_payments + self.missed_payments)
            payment_score = payment_ratio * 600  # Max 600 points
        else:
            payment_score = 0

        # Profile completeness (20% weight)
        profile_score = (self.profile_completion_percentage() / 100) * 200  # Max 200 points

        # Account age and activity (10% weight)
        from django.utils import timezone
        account_age_days = (timezone.now() - self.date_joined).days
        age_score = min(100, account_age_days / 365 * 100)  # Max 100 points for 1+ year

        # Credit usage responsibility (10% weight)
        if self.total_credit_used > 0:
            # Reward users who use credit responsibly
            usage_score = min(100, (float(self.total_credit_used) / 1000) * 20)  # Max 100 points
        else:
            usage_score = 0

        total_score = base_score + payment_score + profile_score + age_score + usage_score
        return min(1000, int(total_score))  # Cap at 1000

    def update_internal_credit_score(self):
        """Update and save the internal credit score"""
        self.internal_credit_score = self.calculate_internal_credit_score()
        self.save(update_fields=['internal_credit_score'])
        return self.internal_credit_score

    def check_tier_upgrade_eligibility(self):
        """Check if user is eligible for credit tier upgrade"""
        current_score = self.internal_credit_score
        successful_payments = self.successful_payments

        upgrade_criteria = {
            self.CreditTier.STARTER: {
                'next_tier': self.CreditTier.BRONZE,
                'min_score': 200,
                'min_payments': 3,
                'new_limit': 1500
            },
            self.CreditTier.BRONZE: {
                'next_tier': self.CreditTier.SILVER,
                'min_score': 400,
                'min_payments': 6,
                'new_limit': 3500
            },
            self.CreditTier.SILVER: {
                'next_tier': self.CreditTier.GOLD,
                'min_score': 600,
                'min_payments': 12,
                'new_limit': 7500
            },
            self.CreditTier.GOLD: {
                'next_tier': self.CreditTier.PLATINUM,
                'min_score': 800,
                'min_payments': 24,
                'new_limit': 15000
            }
        }

        if self.credit_tier in upgrade_criteria:
            criteria = upgrade_criteria[self.credit_tier]
            if (current_score >= criteria['min_score'] and
                successful_payments >= criteria['min_payments']):
                return criteria

        return None

    def upgrade_credit_tier(self):
        """Upgrade user to next credit tier if eligible"""
        upgrade_info = self.check_tier_upgrade_eligibility()
        if upgrade_info:
            old_tier = self.credit_tier
            old_limit = self.credit_limit

            self.credit_tier = upgrade_info['next_tier']
            self.credit_limit = upgrade_info['new_limit']
            self.last_credit_review = timezone.now()
            self.save(update_fields=['credit_tier', 'credit_limit', 'last_credit_review'])

            # Log the upgrade
            print(f"User {self.username} upgraded from {old_tier} to {self.credit_tier}, limit increased from ₵{old_limit} to ₵{self.credit_limit}")

            return {
                'upgraded': True,
                'old_tier': old_tier,
                'new_tier': self.credit_tier,
                'old_limit': old_limit,
                'new_limit': self.credit_limit
            }

        return {'upgraded': False}

    def record_successful_payment(self, amount=None):
        """Record a successful payment and update credit metrics"""
        self.successful_payments += 1
        if amount:
            self.total_credit_used += amount

        # Update internal credit score
        self.update_internal_credit_score()

        # Check for tier upgrade
        upgrade_result = self.upgrade_credit_tier()

        self.save(update_fields=['successful_payments', 'total_credit_used'])

        return upgrade_result

    def record_missed_payment(self):
        """Record a missed payment and update credit metrics"""
        self.missed_payments += 1

        # Update internal credit score (will decrease due to missed payment)
        self.update_internal_credit_score()

        # Check if tier should be downgraded (optional - can be implemented later)

        self.save(update_fields=['missed_payments'])

    def get_credit_progress(self):
        """Get progress towards next credit tier"""
        upgrade_info = self.check_tier_upgrade_eligibility()
        if not upgrade_info:
            # Already at highest tier or no upgrade path
            return {
                'can_upgrade': False,
                'progress_percentage': 100,
                'next_tier': None
            }

        # Calculate progress based on both score and payments
        score_progress = min(100, (self.internal_credit_score / upgrade_info['min_score']) * 100)
        payment_progress = min(100, (self.successful_payments / upgrade_info['min_payments']) * 100)

        # Overall progress is the minimum of both (both criteria must be met)
        overall_progress = min(score_progress, payment_progress)

        return {
            'can_upgrade': overall_progress >= 100,
            'progress_percentage': overall_progress,
            'next_tier': upgrade_info['next_tier'],
            'score_progress': score_progress,
            'payment_progress': payment_progress,
            'needed_score': max(0, upgrade_info['min_score'] - self.internal_credit_score),
            'needed_payments': max(0, upgrade_info['min_payments'] - self.successful_payments)
        }

    def get_full_name(self):
        """Return the user's full name"""
        return f"{self.first_name} {self.last_name}".strip() or self.username

    def get_display_name(self):
        """Return the best display name for the user"""
        if self.first_name:
            return self.first_name
        return self.username

    def get_full_address(self):
        """Return formatted full address"""
        address_parts = []
        if self.address_line_1:
            address_parts.append(self.address_line_1)
        if self.address_line_2:
            address_parts.append(self.address_line_2)
        if self.city:
            address_parts.append(self.city)
        if self.region:
            address_parts.append(self.region)
        if self.postal_code:
            address_parts.append(self.postal_code)
        return ", ".join(address_parts) if address_parts else "No address provided"

    def get_age(self):
        """Calculate and return user's age"""
        if self.date_of_birth:
            from datetime import date
            today = date.today()
            return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None

    def profile_completion_percentage(self):
        """Calculate profile completion percentage"""
        fields_to_check = [
            'first_name', 'last_name', 'email', 'phone_number',
            'address_line_1', 'city', 'region', 'date_of_birth',
            'occupation', 'monthly_income'
        ]
        completed_fields = sum(1 for field in fields_to_check if getattr(self, field))
        return int((completed_fields / len(fields_to_check)) * 100)

# 2. The core credit/savings account for each user's goal


class CreditAccount(models.Model):
    class AccountType(models.TextChoices):
        SAVINGS = 'SAVINGS', 'Save-to-Own'
        CREDIT = 'CREDIT', 'Buy Now, Pay Later'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Approval'
        ACTIVE = 'ACTIVE', 'Active'
        COMPLETED = 'COMPLETED', 'Plan Completed'
        AVAILABLE_FOR_PICKUP = 'AVAILABLE_FOR_PICKUP', 'Available for Pickup'
        PICKED_UP = 'PICKED_UP', 'Device Picked Up'
        CLOSED = 'CLOSED', 'Plan Closed'
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
        max_length=25, choices=Status.choices, default=Status.PENDING)

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

    # Admin and user action tracking
    admin_marked_ready_at = models.DateTimeField(null=True, blank=True, help_text="When admin marked device ready for pickup")
    admin_marked_by = models.ForeignKey('User', null=True, blank=True, on_delete=models.SET_NULL, related_name='marked_accounts', help_text="Admin who marked device ready")
    user_confirmed_pickup_at = models.DateTimeField(null=True, blank=True, help_text="When user confirmed device pickup")
    pickup_confirmation_method = models.CharField(max_length=50, blank=True, help_text="How pickup was confirmed: dashboard, phone, in_person")
    sms_sent_at = models.DateTimeField(null=True, blank=True, help_text="When SMS notification was sent")
    email_sent_at = models.DateTimeField(null=True, blank=True, help_text="When email notification was sent")

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
        if self.status in [self.Status.COMPLETED, self.Status.AVAILABLE_FOR_PICKUP, self.Status.PICKED_UP]:
            return False

        if self.account_type == self.AccountType.CREDIT:
            # For credit accounts, check if all installments are paid
            return self.balance >= (self.loan_amount or 0)
        else:
            # For savings accounts, check if full phone price is paid
            phone_price = self.phone.price if self.phone else 0
            return self.balance >= phone_price

    def mark_as_completed(self):
        """Mark the plan as completed (automatic when payment is complete)"""
        from django.utils import timezone

        if self.is_eligible_for_completion():
            self.status = self.Status.COMPLETED
            self.completed_at = timezone.now()
            self.save()
            return True
        return False

    def mark_available_for_pickup(self, admin_user=None):
        """Admin action: Mark device as ready for pickup"""
        from django.utils import timezone

        if self.status == self.Status.COMPLETED:
            self.status = self.Status.AVAILABLE_FOR_PICKUP
            self.admin_marked_ready_at = timezone.now()
            self.admin_marked_by = admin_user
            self.save()
            return True
        return False

    def confirm_pickup(self, confirmation_method='dashboard'):
        """User action: Confirm device pickup"""
        from django.utils import timezone

        if self.status == self.Status.AVAILABLE_FOR_PICKUP:
            self.status = self.Status.PICKED_UP
            self.user_confirmed_pickup_at = timezone.now()
            self.pickup_confirmation_method = confirmation_method
            self.is_active_plan = False  # Plan is now closed
            self.save()
            return True
        return False

    def close_plan(self):
        """Close the plan and allow new plan selection"""
        if self.status == self.Status.PICKED_UP:
            self.status = self.Status.CLOSED
            self.is_active_plan = False
            self.save()
            return True
        return False

    def record_payment_success(self, amount):
        """Record successful payment and update user's credit metrics"""
        # Update account balance
        self.balance += amount
        self.last_payment_date = timezone.now().date()

        # Update next payment due date if still repaying
        if self.status == self.Status.REPAYING and self.next_payment_due_date:
            from dateutil.relativedelta import relativedelta
            self.next_payment_due_date = self.next_payment_due_date + relativedelta(months=1)

        self.save()

        # Update user's credit metrics and check for tier upgrade
        upgrade_result = self.user.record_successful_payment(amount)

        return upgrade_result

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

    def is_plan_active(self):
        """Check if this plan is currently active (user cannot select new phones)"""
        # If is_active_plan field exists and is False, plan is not active
        if hasattr(self, 'is_active_plan') and not self.is_active_plan:
            return False

        # Check status-based logic for inactive statuses
        inactive_statuses = [
            self.Status.PICKED_UP,
            self.Status.CLOSED,
            self.Status.DECLINED
        ]

        if self.status in inactive_statuses:
            return False

        # For completed plans that haven't been picked up yet, consider them inactive
        # so users can start new plans after completion
        if self.status in [self.Status.COMPLETED, self.Status.AVAILABLE_FOR_PICKUP]:
            return False

        # Active statuses: PENDING, ACTIVE, REPAYING, OVERDUE, PAID_OFF
        return True

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
        VERIFIED = 'VERIFIED', 'Verified for Payment'

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='credit_applications')
    phone = models.ForeignKey('phones.Phone', on_delete=models.PROTECT, null=True, blank=True)
    monthly_income = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Applicant's monthly income")
    employment_status = models.CharField(max_length=50, null=True, blank=True)
    monthly_expenses = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Applicant's monthly expenses")
    status = models.CharField(
        max_length=25, choices=Status.choices, default=Status.PENDING)
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

    # Guarantor Information
    guarantor_username = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        help_text="Username of the guarantor provided during application"
    )
    guarantor_national_id = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="National ID of the guarantor provided during application"
    )
    guarantor_validated = models.BooleanField(
        default=False,
        help_text="Whether the guarantor information has been validated"
    )
    guarantor_validation_notes = models.TextField(
        blank=True,
        help_text="Notes from guarantor validation process"
    )

    # Verification fields
    verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='verified_applications', help_text='Admin who verified this application'
    )
    verified_at = models.DateTimeField(null=True, blank=True, help_text='When the application was verified')
    verification_notes = models.TextField(blank=True, help_text='Admin notes during verification')
    payment_allowed = models.BooleanField(default=False, help_text='Whether user can proceed with payments')

    def __str__(self):
        return f"Credit application by {self.user.username} for {self.phone.name}"

    def can_make_payments(self):
        """Check if user can make payments on this application"""
        return self.status == self.Status.VERIFIED and self.payment_allowed

    def verify_for_payment(self, admin_user, notes=""):
        """Admin action: Verify application for payment processing"""
        from django.utils import timezone

        if self.status == self.Status.APPROVED:
            self.status = self.Status.VERIFIED
            self.verified_by = admin_user
            self.verified_at = timezone.now()
            self.verification_notes = notes
            self.payment_allowed = True
            self.save()
            return True
        return False
