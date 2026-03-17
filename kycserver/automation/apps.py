from django.apps import AppConfig


class AutomationConfig(AppConfig):
    name = 'automation'

    def ready(self):
        # Import all actions so they register
        import automation.actions