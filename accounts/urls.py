from django.urls import path
from django.contrib.auth import views as auth_views
from .views import bnpl_checkout_view, bnpl_success_view, business_dashboard_view, create_customer_portal_session, signup_view, login_view, logout_view, dashboard_view, select_product_view, agreement_view, stripe_config, create_checkout_session, stripe_webhook, credit_application_view, payment_history_view, test_webhook, webhook_test_page, embedded_payment_view, create_payment_intent, payment_success_view, support_view, documents_view

urlpatterns = [
    path('signup/', signup_view, name='signup'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('select-product/<int:product_id>/',
         select_product_view, name='select_product'),
    path('agreement/<int:account_id>/', agreement_view, name='agreement'),
    path('credit-application/<int:product_id>/',
         credit_application_view, name='credit_application'),
    path('config/', stripe_config, name='stripe_config'),
    path('create-checkout-session/', create_checkout_session,
         name='create_checkout_session'),
    path('webhook/', stripe_webhook, name='stripe_webhook'),
    path('test-webhook/', test_webhook, name='test_webhook'),
    path('webhook-test-page/', webhook_test_page, name='webhook_test_page'),
    path('embedded-payment/', embedded_payment_view, name='embedded_payment'),
    path('create-payment-intent/', create_payment_intent,
         name='create_payment_intent'),
    path('payment-success/', payment_success_view, name='payment_success'),
    path('bnpl-checkout/<int:product_id>/',
         bnpl_checkout_view, name='bnpl_checkout'),
    path('bnpl-success/<int:account_id>/',
         bnpl_success_view, name='bnpl_success'),
    path('manage-payments/', create_customer_portal_session, name='manage_payments'),
    path('payment-history/', payment_history_view, name='payment_history'),
    path('business-dashboard/', business_dashboard_view, name='business_dashboard'),
    path('support/', support_view, name='support'),
    path('documents/', documents_view, name='documents'),
]
