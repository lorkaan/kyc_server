
from globalparams.models import GlobalParameter
from utils.type_utils import isString


def getGlobalParamByName(param_name):
    if isString(param_name):
        try:
            qs = GlobalParameter.objects.get(name=param_name)
            return qs.get_value()
        except GlobalParameter.DoesNotExist:
            return None
    else:
        return None