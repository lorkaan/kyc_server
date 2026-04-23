from django.core.exceptions import ValidationError

from kyc.models import KycAnswer, KycAnswerOption, KycQuestion, ReferenceValue
import logging

from encrypt.cipherpol import CipherPol, CipherPolAgent
from encrypt.handlers import DekHandler
from encrypt.models import EncryptionValue
from kyc.data_types import AnswerTypeEnum

def handle_number(answer, value, question):
    try:
        answer.value_number = value
    except Exception:
        raise ValidationError("Invalid number")


def handle_text(answer, value, question):
    answer.value_text = str(value) if value is not None else None


def handle_bool(answer, value, question):
    if isinstance(value, bool):
        answer.value_bool = value
        return

    val = str(value).lower()
    if val in ["true", "1", "yes"]:
        answer.value_bool = True
    elif val in ["false", "0", "no"]:
        answer.value_bool = False
    else:
        raise ValidationError("Invalid boolean")


def handle_single(answer, value, question):
    if isinstance(value, ReferenceValue):
        ref = value
    else:
        ref = ReferenceValue.objects.get(pk=value)

    if question.reference_set and ref.reference_set_id != question.reference_set_id:
        raise ValidationError("Invalid reference value")

    answer.value_reference = ref


def handle_multi(answer, value, question):
    if not isinstance(value, (list, tuple)):
        import logging
        logger = logging.getLogger()
        logger.error(f"Value: {type(value)} -> {value}")
        raise ValidationError("Multi choice requires a list")

    if question.required and not value:
        raise ValidationError("At least one option must be selected")

    refs = []
    for v in value:
        if isinstance(v, ReferenceValue):
            refs.append(v)
        else:
            refs.append(ReferenceValue.objects.get(pk=v))

    # Validate reference set
    if question.reference_set:
        invalid = [
            r for r in refs
            if r.reference_set_id != question.reference_set_id
        ]
        if invalid:
            raise ValidationError("Invalid reference values")

    # MUST save before setting M2M
    answer.save()
    KycAnswerOption.objects.bulk_create([
        KycAnswerOption(answer=answer, reference_value=ref)
        for ref in refs
    ])


def handle_date(answer, value, question):
    answer.value_date = value


def handle_range(answer, value, question):
    if not isinstance(value, dict):
        raise ValidationError("Range requires {from, to}")

    answer.value_date_from = value.get("from")
    answer.value_date_to = value.get("to")


def handle_phone(answer, value, question):
    answer.value_phone = str(value)


def handle_email(answer, value, question):
    answer.value_email = str(value)

ANSWER_HANDLERS = {
    AnswerTypeEnum.NUMBER: handle_number,
    AnswerTypeEnum.TEXT: handle_text,
    AnswerTypeEnum.TEXT_AREA: handle_text,
    AnswerTypeEnum.BOOL: handle_bool,
    AnswerTypeEnum.SINGLE: handle_single,
    AnswerTypeEnum.MULTI: handle_multi,
    AnswerTypeEnum.DATE: handle_date,
    AnswerTypeEnum.RANGE: handle_range,
    AnswerTypeEnum.PHONE: handle_phone,
    AnswerTypeEnum.EMAIL: handle_email,
}

class AnswerHandler:

    logger = logging.getLogger()

    @classmethod
    def save(cls, answer, value, questionObj):
        if isinstance(questionObj, KycQuestion) and isinstance(answer, KycAnswer) and value != None:
            handler = ANSWER_HANDLERS.get(questionObj.answer_type)
            if not handler or not callable(handler):
                cls.logger.error(f"Handler {handler} -> {questionObj.answer_type}")
                raise ValidationError(f"Unsupported answer type: \n\tQuestion: {questionObj}\n\tType: {questionObj.answer_type}\n\tValue Type: {type(value)}\n\tValue: {value}")
            else:
                if questionObj.encrypt_type == None:
                    handler(answer, value, questionObj)
                else:
                    # Encryption pass
                    algoCls = CipherPol.get(questionObj.encrypt_type.algorithm)
                    if issubclass(algoCls, CipherPolAgent):
                        dek = algoCls.generate_key()
                        ciphertext = algoCls.encrypt(value, dek) # Do more things here
                        cipherdek, key_id = DekHandler.encrypt_dek(dek)
                        encryptedAns = EncryptionValue(encrypt_type=questionObj.encrypt_type, ciphertext=ciphertext, dek=cipherdek, key_id=key_id, data_type=questionObj.answer_type)
                        encryptedAns.save()
                        answer.value_encrypt = encryptedAns
