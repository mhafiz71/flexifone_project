from django import forms
from .models import Phone

class PhoneForm(forms.ModelForm):
    class Meta:
        model = Phone
        fields = ['name', 'brand', 'price', 'description', 'specifications', 'image', 'stock', 'is_active', 'credit_available', 'interest_rate', 'max_installments', 'min_credit_score']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-green-500 focus:border-green-500 sm:text-sm',
                'placeholder': 'e.g., iPhone 14 Pro Max'
            }),
            'brand': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-green-500 focus:border-green-500 sm:text-sm'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-green-500 focus:border-green-500 sm:text-sm',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'description': forms.Textarea(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-green-500 focus:border-green-500 sm:text-sm',
                'rows': 4,
                'placeholder': 'Describe the phone features, specifications, and selling points...'
            }),
            'specifications': forms.Textarea(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-green-500 focus:border-green-500 sm:text-sm font-mono text-xs',
                'rows': 6,
                'placeholder': '{\n  "processor": "A15 Bionic",\n  "storage": "128GB",\n  "ram": "6GB",\n  "display": "6.7-inch Super Retina XDR",\n  "camera": "48MP Main + 12MP Ultra Wide"\n}'
            }),
            'image': forms.ClearableFileInput(attrs={
                'class': 'mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-green-50 file:text-green-700 hover:file:bg-green-100',
                'accept': 'image/*'
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-green-500 focus:border-green-500 sm:text-sm',
                'min': '0',
                'placeholder': '0'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-green-600 focus:ring-green-500 border-gray-300 rounded'
            }),
            'credit_available': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-green-600 focus:ring-green-500 border-gray-300 rounded'
            }),
            'interest_rate': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-green-500 focus:border-green-500 sm:text-sm',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': '15.00'
            }),
            'max_installments': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-green-500 focus:border-green-500 sm:text-sm',
                'min': '1',
                'max': '60',
                'placeholder': '12'
            }),
            'min_credit_score': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-green-500 focus:border-green-500 sm:text-sm',
                'min': '300',
                'max': '850',
                'placeholder': '600'
            }),
        }

        labels = {
            'name': 'Phone Name',
            'brand': 'Brand',
            'price': 'Price (₵)',
            'description': 'Description',
            'specifications': 'Technical Specifications',
            'image': 'Phone Image',
            'stock': 'Stock Quantity',
            'is_active': 'Active (visible to customers)',
            'credit_available': 'Available for Credit Purchase',
            'interest_rate': 'Annual Interest Rate (%)',
            'max_installments': 'Maximum Installments',
            'min_credit_score': 'Minimum Credit Score Required',
        }

        help_texts = {
            'price': 'Enter the price in Ghana Cedis (₵)',
            'specifications': 'Enter technical specifications as a JSON object',
            'credit_available': 'Check if this phone can be purchased on credit',
            'interest_rate': 'Annual interest rate for credit purchases (0-100%)',
            'max_installments': 'Maximum number of monthly installments allowed (1-60)',
            'min_credit_score': 'Minimum credit score required for credit approval (300-850)',
        }
        
    def clean_specifications(self):
        specs = self.cleaned_data.get('specifications')
        if isinstance(specs, str):
            import json
            try:
                return json.loads(specs)
            except json.JSONDecodeError:
                raise forms.ValidationError("Specifications must be a valid JSON object")
        return specs