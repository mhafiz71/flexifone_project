from django.urls import path
from django.contrib.auth import views as auth_views
from django.contrib.auth import views as auth_views
from .views import bnpl_checkout_view, bnpl_success_view, business_dashboard_view, cancel_plan_view, create_customer_portal_session, signup_view, login_view, logout_view, dashboard_view, select_phone_view, agreement_view, stripe_config, create_checkout_session, stripe_webhook, credit_application_view, payment_history_view, test_webhook, webhook_test_page, embedded_payment_view, create_payment_intent, payment_success_view, support_view, documents_view, customer_management_view, approve_account_view, decline_account_view, verify_user_view, account_detail_view, update_account_settings_view, credit_eligibility_view, mark_available_for_pickup_view, bulk_mark_available_for_pickup_view, confirm_pickup_view, credit_applications_view, verify_credit_application_view, profile_view, profile_edit_view, profile_picture_view, change_password_view, credit_building_dashboard_view

urlpatterns = [
    path('signup/', signup_view, name='signup'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('select-phone/<int:phone_id>/',
         select_phone_view, name='select_phone'),
    path('choose-plan/<int:phone_id>/',
         select_phone_view, name='choose_plan'),
    path('agreement/<int:account_id>/', agreement_view, name='agreement'),
    path('credit-application/<int:phone_id>/',
         credit_application_view, name='credit_application'),
    path('credit-eligibility/', credit_eligibility_view, name='credit_eligibility'),
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
    path('bnpl-checkout/<int:phone_id>/',
         bnpl_checkout_view, name='bnpl_checkout'),
    path('bnpl-success/<int:account_id>/',
         bnpl_success_view, name='bnpl_success'),
    path('manage-payments/', create_customer_portal_session, name='manage_payments'),
    path('payment-history/', payment_history_view, name='payment_history'),
    path('business-dashboard/', business_dashboard_view, name='business_dashboard'),
    path('customer-management/', customer_management_view, name='customer_management'),
    path('account-detail/<int:account_id>/', account_detail_view, name='account_detail'),
    path('approve-account/<int:account_id>/', approve_account_view, name='approve_account'),
    path('decline-account/<int:account_id>/', decline_account_view, name='decline_account'),
    path('verify-user/<int:user_id>/', verify_user_view, name='verify_user'),
    path('mark-available-for-pickup/<int:account_id>/', mark_available_for_pickup_view, name='mark_available_for_pickup'),
    path('bulk-mark-available-for-pickup/', bulk_mark_available_for_pickup_view, name='bulk_mark_available_for_pickup'),
    path('confirm-pickup/<int:account_id>/', confirm_pickup_view, name='confirm_pickup'),
    path('update-account-settings/', update_account_settings_view, name='update_account_settings'),
    path('support/', support_view, name='support'),
    path('documents/', documents_view, name='documents'),
    path('cancel-plan/', cancel_plan_view, name='cancel_plan'),
    path('credit-applications/', credit_applications_view, name='credit_applications'),
    path('verify-credit-application/<int:application_id>/', verify_credit_application_view, name='verify_credit_application'),

    # Profile URLs
    path('profile/', profile_view, name='profile'),
    path('profile/edit/', profile_edit_view, name='profile_edit'),
    path('profile/picture/', profile_picture_view, name='profile_picture'),
    path('profile/change-password/', change_password_view, name='change_password'),

    # Credit Building URLs
    path('credit-building/', credit_building_dashboard_view, name='credit_building_dashboard'),

    # Password Reset URLs
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.html',
        html_email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
        success_url='/accounts/password-reset/done/'
    ), name='password_reset'),

    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),

    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url='/accounts/password-reset-complete/'
    ), name='password_reset_confirm'),

    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),
]
