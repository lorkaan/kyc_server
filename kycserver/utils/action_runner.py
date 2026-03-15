from typing import Callable, Any, Dict
import logging

logger = logging.getLogger(__name__)

class ActionRunner:
    """
    Registry and executor for automation actions.
    Each action type must be registered with a callable handler.
    """

    REGISTRY: Dict[str, Callable[[Any, dict, dict], None]] = {}

    @classmethod
    def register(cls, name: str):
        """
        Decorator to register a function as a handler for an action type.

        Usage:
            @ActionRunner.register("send_email")
            def send_email_action(results, config, context):
                ...
        """
        def decorator(fn: Callable[[Any, dict, dict], None]):
            if not callable(fn):
                raise TypeError(f"Handler must be callable, got {type(fn)}")
            cls.REGISTRY[name] = fn
            logger.debug(f"Registered automation action: {name}")
            return fn
        return decorator

    @classmethod
    def run(cls, action, results: Any, context: dict):
        """
        Execute the registered handler for the given action.

        :param action: AutomationAction instance (must have 'type' and 'config')
        :param results: Results from the query/rule that triggered this action
        :param context: Runtime context (trigger_id, signal_id, task_id, etc.)
        """
        handler = cls.REGISTRY.get(action.type)
        if handler is None:
            raise ValueError(f"Unknown action type: {action.type}")

        if not callable(handler):
            raise TypeError(f"Handler for action {action.type} is not callable")

        try:
            logger.info(f"Running action '{action.type}' for trigger {context.get('trigger_id')}")
            handler(results, action.config, context)
        except Exception as e:
            logger.exception(f"Error running action '{action.type}': {e}")
            raise
