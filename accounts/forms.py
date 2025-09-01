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

    # Guarantor fields
    guarantor_username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500',
            'placeholder': 'Enter guarantor\'s FlexiFone username'
        }),
        help_text="Username of a verified FlexiFone user who will guarantee your loan"
    )

    guarantor_national_id = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500',
            'placeholder': 'Enter guarantor\'s national ID'
        }),
        help_text="National ID of your guarantor (must match their FlexiFone profile)"
    )

    class Meta:
        model = CreditApplication
        fields = ['monthly_income', 'employment_status', 'monthly_expenses', 'installment_count', 'guarantor_username', 'guarantor_national_id']
    
    def clean(self):
        cleaned_data = super().clean()
        monthly_income = cleaned_data.get('monthly_income')
        monthly_expenses = cleaned_data.get('monthly_expenses')
        guarantor_username = cleaned_data.get('guarantor_username')
        guarantor_national_id = cleaned_data.get('guarantor_national_id')

        # Validate income vs expenses
        if monthly_income and monthly_expenses:
            if monthly_expenses >= monthly_income:
                raise forms.ValidationError("Monthly expenses cannot be greater than or equal to monthly income.")

            # Calculate debt-to-income ratio
            # Convert Decimal to float for calculation
            debt_to_income = (float(monthly_expenses) / float(monthly_income)) * 100
            if debt_to_income > 70:  # Updated to match new progressive system
                raise forms.ValidationError("Your debt-to-income ratio is too high for credit approval.")

        # Validate guarantor information
        if guarantor_username and guarantor_national_id:
            from accounts.models import User

            # Get the current user from the form's instance or request
            current_user = getattr(self, '_user', None)
            if current_user:
                validation_result = current_user.validate_guarantor(guarantor_username, guarantor_national_id)
                if not validation_result['valid']:
                    raise forms.ValidationError(f"Guarantor validation failed: {validation_result['error']}")

        return cleaned_data

    def set_user(self, user):
        """Set the current user for guarantor validation"""
        self._user = user

class UserProfileForm(forms.ModelForm):
    """Form for editing basic user profile information"""
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'phone_number', 'alternate_phone',
            'date_of_birth', 'gender', 'occupation', 'employer', 'monthly_income'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500',
                'placeholder': 'Enter your first name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500',
                'placeholder': 'Enter your last name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500',
                'placeholder': 'Enter your email address'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500',
                'placeholder': 'Enter your phone number'
            }),
            'alternate_phone': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500',
                'placeholder': 'Enter alternate phone number'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500',
                'type': 'date'
            }),
            'gender': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500'
            }),
            'occupation': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500',
                'placeholder': 'Enter your occupation'
            }),
            'employer': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500',
                'placeholder': 'Enter your employer'
            }),
            'monthly_income': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500',
                'placeholder': 'Enter your monthly income',
                'step': '0.01'
            }),
        }
        labels = {
            'phone_number': 'Primary Phone Number',
            'alternate_phone': 'Alternate Phone Number',
            'date_of_birth': 'Date of Birth',
            'monthly_income': 'Monthly Income (₵)',
        }


class UserAddressForm(forms.ModelForm):
    """Form for editing user address information"""
    class Meta:
        model = User
        fields = ['address_line_1', 'address_line_2', 'city', 'region', 'postal_code']
        widgets = {
            'address_line_1': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500',
                'placeholder': 'Enter street address'
            }),
            'address_line_2': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500',
                'placeholder': 'Apartment, suite, etc. (optional)'
            }),
            'city': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500',
                'placeholder': 'Enter city'
            }),
            'region': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500',
                'placeholder': 'Enter region/state'
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500',
                'placeholder': 'Enter postal code'
            }),
        }
        labels = {
            'address_line_1': 'Street Address',
            'address_line_2': 'Address Line 2',
            'postal_code': 'Postal Code',
        }


class UserPreferencesForm(forms.ModelForm):
    """Form for editing user notification preferences"""
    class Meta:
        model = User
        fields = ['email_notifications', 'sms_notifications', 'marketing_emails']
        widgets = {
            'email_notifications': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-green-600 focus:ring-green-500 border-gray-300 rounded'
            }),
            'sms_notifications': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-green-600 focus:ring-green-500 border-gray-300 rounded'
            }),
            'marketing_emails': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-green-600 focus:ring-green-500 border-gray-300 rounded'
            }),
        }
        labels = {
            'email_notifications': 'Email Notifications',
            'sms_notifications': 'SMS Notifications',
            'marketing_emails': 'Marketing Emails',
        }


class ProfilePictureForm(forms.ModelForm):
    """Form for uploading profile picture"""
    class Meta:
        model = User
        fields = ['profile_picture']
        widgets = {
            'profile_picture': forms.FileInput(attrs={
                'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-green-50 file:text-green-700 hover:file:bg-green-100',
                'accept': 'image/*'
            }),
        }