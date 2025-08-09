# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, CreditApplication

class CustomUserCreationForm(UserCreationForm):
    national_id = forms.CharField(
        max_length=20,
        help_text="National ID or Passport Number",
        widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'})
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'})
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'national_id', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to all fields
        for field_name, field in self.fields.items():
            if field_name not in ['national_id', 'email', 'first_name', 'last_name']:
                field.widget.attrs.update({'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'})

class CreditApplicationForm(forms.ModelForm):
    EMPLOYMENT_CHOICES = [
        ('FULL_TIME', 'Full-time Employee'),
        ('PART_TIME', 'Part-time Employee'),
        ('SELF_EMPLOYED', 'Self-employed'),
        ('STUDENT', 'Student'),
        ('UNEMPLOYED', 'Unemployed'),
        ('RETIRED', 'Retired'),
    ]
    
    employment_status = forms.ChoiceField(
        choices=EMPLOYMENT_CHOICES,
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'})
    )
    
    monthly_income = forms.DecimalField(
        max_digits=10, 
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500',
            'placeholder': 'Enter your monthly income'
        })
    )
    
    monthly_expenses = forms.DecimalField(
        max_digits=10, 
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500',
            'placeholder': 'Enter your monthly expenses'
        })
    )
    
    installment_count = forms.ChoiceField(
        choices=[
            (6, '6 months'),
            (12, '12 months'),
            (18, '18 months'),
            (24, '24 months'),
        ],
        initial=12,
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'})
    )
    
    class Meta:
        model = CreditApplication
        fields = ['monthly_income', 'employment_status', 'monthly_expenses', 'installment_count']
    
    def clean(self):
        cleaned_data = super().clean()
        monthly_income = cleaned_data.get('monthly_income')
        monthly_expenses = cleaned_data.get('monthly_expenses')
        
        if monthly_income and monthly_expenses:
            if monthly_expenses >= monthly_income:
                raise forms.ValidationError("Monthly expenses cannot be greater than or equal to monthly income.")
            
            # Calculate debt-to-income ratio
            debt_to_income = (monthly_expenses / monthly_income) * 100
            if debt_to_income > 50:
                raise forms.ValidationError("Your debt-to-income ratio is too high for credit approval.")
        
        return cleaned_data

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'monthly_income']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'}),
            'email': forms.EmailInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'}),
            'monthly_income': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'}),
        }