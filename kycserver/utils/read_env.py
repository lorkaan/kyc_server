from dotenv import find_dotenv, load_dotenv
import os

class EnvironVarLoader:

    @classmethod
    def isEnvKey(cls, key):
        return type(key) == str and len(key) > 0

    def __init__(self):
        path = find_dotenv()
        if type(path) == str and len(path) > 0 and os.path.exists(path):
            load_dotenv(path)

    def get(self, key, defaultVal="", errorVal=None):
        if self.__class__.isEnvKey(key):
            val = os.getenv(key, default=defaultVal)
            if val == errorVal:
                raise KeyError(f"Can not find a value for the given key: {key}")
            else:
                return val
        else:
            raise TypeError(f"The Environment Key: {key} can not be used as a key")
        
class EnvConfigurable:

    envloader = EnvironVarLoader()
