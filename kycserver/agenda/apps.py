from django.apps import AppConfig


class AgendaConfig(AppConfig):
    name = 'agenda'

    def ready(self):
        import agenda.signals