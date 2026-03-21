from django.core.exceptions import ValidationError

from kyc.models import KycQuestion


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
    answer.selected_options.set(refs)


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
    KycQuestion.AnswerTypeEnum.NUMBER: handle_number,
    KycQuestion.AnswerTypeEnum.TEXT: handle_text,
    KycQuestion.AnswerTypeEnum.BOOL: handle_bool,
    KycQuestion.AnswerTypeEnum.SINGLE: handle_single,
    KycQuestion.AnswerTypeEnum.MULTI: handle_multi,
    KycQuestion.AnswerTypeEnum.DATE: handle_date,
    KycQuestion.AnswerTypeEnum.RANGE: handle_range,
    KycQuestion.AnswerTypeEnum.PHONE: handle_phone,
    KycQuestion.AnswerTypeEnum.EMAIL: handle_email,
}