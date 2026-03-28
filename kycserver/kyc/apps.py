from django.apps import AppConfig


class KycConfig(AppConfig):
    name = 'kyc'

    def ready(self):
        import kyc.signals