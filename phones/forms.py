from django import forms
from .models import Phone

class PhoneForm(forms.ModelForm):
    class Meta:
        model = Phone
        fields = ['name', 'brand', 'price', 'description', 'specifications', 'image', 'stock', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input rounded-md w-full'}),
            'brand': forms.Select(attrs={'class': 'form-select rounded-md w-full'}),
            'price': forms.NumberInput(attrs={'class': 'form-input rounded-md w-full', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea rounded-md w-full', 'rows': 4}),
            'specifications': forms.Textarea(attrs={'class': 'form-textarea rounded-md w-full', 'rows': 4, 'placeholder': '{"processor": "A15 Bionic", "storage": "128GB", "ram": "6GB"}'}),
            'stock': forms.NumberInput(attrs={'class': 'form-input rounded-md w-full'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox rounded'}),
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