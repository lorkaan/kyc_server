from django.apps import AppConfig


class WatchdogConfig(AppConfig):
    name = 'watchdog'

    def ready(self):
        import watchdog.signals 
