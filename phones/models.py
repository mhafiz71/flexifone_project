from django.db import models
from django.utils.text import slugify

class Phone(models.Model):
    BRAND_CHOICES = [
        ('apple', 'Apple'),
        ('samsung', 'Samsung'),
        ('google', 'Google'),
        ('xiaomi', 'Xiaomi'),
        ('huawei', 'Huawei'),
        ('other', 'Other'),
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
