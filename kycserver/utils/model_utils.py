from django.apps import apps

def getModelFromName(text: str):
    app_label, model_name = text.split(".")
    return apps.get_model(app_label, model_name)