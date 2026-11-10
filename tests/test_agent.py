from src.agent import WhatsAppOperator
from src.contacts import Contact


def test_validate_accepts_matching_phone_and_name():
    operator = WhatsAppOperator()
    contact = Contact(name="João Silva", phone="5511999999999")

    result = operator.validate(contact, displayed_phone="5511999999999", displayed_name="João Silva")

    assert result.ok
    assert result.warning is None


def test_validate_rejects_mismatched_phone():
    operator = WhatsAppOperator()
    contact = Contact(name="João Silva", phone="5511999999999")

    result = operator.validate(contact, displayed_phone="5511988888888", displayed_name="Alguém")

    assert not result.ok
    assert "expected phone" in result.warning


def test_validate_warns_on_unrelated_name_but_still_ok():
    operator = WhatsAppOperator()
    contact = Contact(name="João Silva", phone="5511999999999")

    result = operator.validate(contact, displayed_phone="5511999999999", displayed_name="xyz123")

    assert result.ok
    assert result.warning is not None
    assert "unrelated" in result.warning


def test_validate_no_warning_when_whatsapp_has_no_display_name():
    operator = WhatsAppOperator()
    contact = Contact(name="João Silva", phone="5511999999999")

    result = operator.validate(contact, displayed_phone="5511999999999", displayed_name=None)

    assert result.ok
    assert result.warning is None


def test_validate_rejects_when_phone_could_not_be_read():
    operator = WhatsAppOperator()
    contact = Contact(name="João Silva", phone="5511999999999")

    result = operator.validate(contact, displayed_phone=None, displayed_name="João Silva")

    assert not result.ok
    assert "could not read" in result.warning
