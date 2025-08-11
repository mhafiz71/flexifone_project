from django.db import models
from django.utils.text import slugify
from django.db.models import Q

class Phone(models.Model):
    BRAND_CHOICES = [
        ('APPLE', 'Apple'),
        ('SAMSUNG', 'Samsung'),
        ('HUAWEI', 'Huawei'),
        ('TECNO', 'Tecno'),
        ('INFINIX', 'Infinix'),
        ('ITEL', 'Itel'),
        ('NOKIA', 'Nokia'),
        ('OTHER', 'Other'),
    ]
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    brand = models.CharField(max_length=20, choices=BRAND_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    specifications = models.JSONField(default=dict, blank=True)
    image = models.ImageField(upload_to='phones/', blank=True, null=True)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    # Credit-specific fields (moved from Product model)
    credit_available = models.BooleanField(
        default=True, help_text="Whether this phone is available for credit purchase")
    min_credit_score = models.IntegerField(
        default=600, help_text="Minimum credit score required for this phone")
    max_installments = models.IntegerField(
        default=12, help_text="Maximum number of installments allowed")
    interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00, help_text="Annual interest rate (%)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Phone'
        verbose_name_plural = 'Phones'
    
    def __str__(self):
        return f"{self.brand} {self.name}"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.brand}-{self.name}")
        super().save(*args, **kwargs)

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
