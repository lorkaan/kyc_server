
from kyc.models import KycRuleConstant
from .bool_logic_eval import BooleanLogicEngine


"""
This is to be used by the display system for determining what KYC questions to show.
"""
class KycConditionalEvaluator:

    constant_keyword = "$const"

    @classmethod
    def resolve_constants(cls,rule):
        if isinstance(rule, dict):

            if cls.constant_keyword in rule:
                key = rule[cls.constant_keyword]

                c = KycRuleConstant.objects.get(
                    key=key,
                    is_active=True
                )

                return c.get_value()

            return {
                k: cls.resolve_constants(v)
                for k, v in rule.items()
            }

        if isinstance(rule, list):
            return [cls.resolve_constants(v) for v in rule]

        return rule
    
    @classmethod
    def evaluate(cls, rule, context):
        rule = cls.resolve_constants(rule)
        return BooleanLogicEngine.eval(rule, context)