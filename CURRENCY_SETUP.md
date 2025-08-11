# Currency Conversion Setup Guide

## Overview

FlexiFone now supports **dual-currency operation**:
- **Display Currency**: Ghana Cedis (₵ GHS) - What users see
- **Processing Currency**: US Dollars ($ USD) - What Stripe processes

This allows you to maintain the local currency experience while using Stripe's supported currencies.

## 🔧 Configuration

### 1. Environment Variables

Add this to your `.env` file:

```env
# Currency Configuration
USD_TO_GHS_RATE=12.0
```

**Important**: Update the exchange rate regularly! You can:
- Check current rates at [xe.com](https://xe.com) or [Bank of Ghana](https://bog.gov.gh)
- Use a currency API service for automatic updates
- Update manually based on your business needs

### 2. Settings Configuration

The following settings are automatically configured in `settings.py`:

```python
# Display currency (what users see)
DISPLAY_CURRENCY = 'GHS'
DISPLAY_CURRENCY_SYMBOL = '₵'

# Payment processing currency (what Stripe uses)
STRIPE_CURRENCY = 'usd'
STRIPE_CURRENCY_SYMBOL = '$'

# Exchange rate: 1 USD = X GHS
USD_TO_GHS_RATE = config('USD_TO_GHS_RATE', default=12.0, cast=float)
```

## 💰 How It Works

### User Experience
1. **Users see prices in Cedis (₵)** throughout the application
2. **Payment forms show Cedis amounts**
3. **Account balances display in Cedis**
4. **Transaction history shows Cedis**

### Payment Processing
1. **User enters amount in Cedis** (e.g., ₵100)
2. **System converts to USD** (e.g., $8.33 at rate 12.0)
3. **Stripe processes in USD** (833 cents)
4. **System converts back to Cedis** for storage and display

### Conversion Examples

With exchange rate of 1 USD = 12.0 GHS:

| GHS Amount | USD Amount | Stripe (cents) |
|------------|------------|----------------|
| ₵100       | $8.33      | 833 cents      |
| ₵500       | $41.67     | 4,167 cents    |
| ₵1,000     | $83.33     | 8,333 cents    |
| ₵4,000     | $333.33    | 33,333 cents   |
| ₵6,500     | $541.67    | 54,167 cents   |

## 🛠️ Technical Implementation

### Currency Utility Functions

Located in `accounts/currency_utils.py`:

- `ghs_to_usd(amount)` - Convert GHS to USD
- `usd_to_ghs(amount)` - Convert USD to GHS  
- `ghs_to_usd_cents(amount)` - Convert GHS to USD cents for Stripe
- `usd_cents_to_ghs(cents)` - Convert USD cents back to GHS
- `format_ghs_amount(amount)` - Format for display (₵100.00)
- `format_usd_amount(amount)` - Format for display ($8.33)

### Updated Payment Flows

1. **Embedded Payments**: Uses USD for Stripe, stores original GHS amount in metadata
2. **Checkout Sessions**: Converts GHS to USD, includes description showing GHS equivalent
3. **Webhooks**: Retrieves original GHS amount from metadata or converts back from USD
4. **BNPL Installments**: Converts installment amounts to USD for processing

## 🔄 Updating Exchange Rates

### Manual Update
Update the `USD_TO_GHS_RATE` in your `.env` file:

```env
USD_TO_GHS_RATE=12.5  # New rate
```

### Automatic Updates (Recommended for Production)

Consider integrating with a currency API service:

```python
# Example: Using a currency API
import requests

def update_exchange_rate():
    response = requests.get('https://api.exchangerate-api.com/v4/latest/USD')
    data = response.json()
    new_rate = data['rates']['GHS']
    
    # Update your settings or database
    # This is just an example - implement according to your needs
```

## 🧪 Testing

The system includes comprehensive currency conversion testing. All conversions maintain accuracy within 1 pesewa (₵0.01).

## 🚨 Important Notes

1. **Exchange Rate Management**: 
   - Update rates regularly to reflect market conditions
   - Consider your business margins when setting rates
   - Monitor for significant currency fluctuations

2. **Rounding**: 
   - Small rounding differences (₵0.01-0.04) are normal
   - All amounts are rounded to 2 decimal places
   - Stripe processes in the smallest currency unit (cents)

3. **Stripe Account**: 
   - Ensure your Stripe account supports USD processing
   - Update your Stripe dashboard currency settings if needed
   - Test with small amounts first

4. **User Communication**:
   - Users only see Cedis amounts
   - Stripe receipts will show USD amounts
   - Consider adding a note about currency conversion in your terms

## 🔍 Troubleshooting

### Common Issues

1. **"Invalid currency: ghs" error**:
   - ✅ Fixed! System now uses USD for Stripe processing

2. **Conversion inaccuracies**:
   - Small differences (₵0.01-0.04) are normal due to rounding
   - Larger differences indicate exchange rate issues

3. **Stripe dashboard shows USD**:
   - This is expected - Stripe processes in USD
   - Your application displays and stores amounts in GHS

### Testing Payments

1. Use Stripe test cards: `4242 4242 4242 4242`
2. Test with various amounts to verify conversion
3. Check both your database and Stripe dashboard
4. Verify user sees correct Cedis amounts

## 📞 Support

If you encounter issues:
1. Check the exchange rate setting
2. Verify Stripe account supports USD
3. Test with small amounts first
4. Check server logs for conversion details
