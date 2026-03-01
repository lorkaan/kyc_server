
class ActionRunner:

    REGISTRY = {}

    @classmethod
    def register(cls, name):
        def deco(fn):
            cls.REGISTRY[name] = fn
            return fn
        return deco

    @classmethod
    def run(cls, action, results, context):

        handler = cls.REGISTRY.get(action.type, None)

        if not handler:
            raise ValueError("Unknown action")
        elif not callable(handler):
            raise TypeError(f"Expected a function, but got: {type(handler)}")

        handler(results, action.config, context)