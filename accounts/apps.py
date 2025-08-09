# accounts/apps.py
from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        # This method is called when the app is ready
        from . import jobs
        from django_apscheduler.jobstores import DjangoJobStore
        from apscheduler.schedulers.background import BackgroundScheduler

        # Ensure the job isn't scheduled multiple times if the server reloads
        # This is a simple check; more robust solutions exist for production
        try:
            scheduler = BackgroundScheduler()
            scheduler.add_jobstore(DjangoJobStore(), "default")
            
            # Check if the job already exists
            if not scheduler.get_job('daily_installments'):
                scheduler.add_job(
                    jobs.process_daily_installments,
                    trigger='interval',
                    # days=1 # For production
                    minutes=1, # For easy testing
                    id='daily_installments',
                    replace_existing=True,
                )
                print("Scheduler started and 'daily_installments' job added.")
            
            if not scheduler.running:
                scheduler.start()
        except Exception as e:
            print(f"Error starting scheduler: {e}")