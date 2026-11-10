import pandas as pd
import pytest
from pydantic import ValidationError

from src.contacts import Contact, deduplicate, load_contacts, load_message


def test_contact_normalizes_phone_digits():
    contact = Contact(name="João Silva", phone="(55) 11 99999-9999")
    assert contact.phone == "5511999999999"


def test_contact_rejects_blank_name():
    with pytest.raises(ValidationError):
        Contact(name="   ", phone="5511999999999")


def test_contact_rejects_too_short_phone():
    with pytest.raises(ValidationError):
        Contact(name="João Silva", phone="123")


def test_load_contacts_reads_csv(tmp_path):
    path = tmp_path / "contacts.csv"
    pd.DataFrame(
        [
            {"name": "João Silva", "phone": "5511999999999"},
            {"name": "Maria Souza", "phone": "5511988888888"},
        ]
    ).to_csv(path, index=False)

    contacts = load_contacts(path)

    assert len(contacts) == 2
    assert contacts[0].name == "João Silva"
    assert contacts[0].phone == "5511999999999"


def test_load_contacts_missing_column_raises(tmp_path):
    path = tmp_path / "contacts.csv"
    pd.DataFrame([{"name": "João Silva"}]).to_csv(path, index=False)

    with pytest.raises(ValueError):
        load_contacts(path)


def test_load_message_strips_whitespace(tmp_path):
    path = tmp_path / "message.txt"
    path.write_text("  Olá!  \n\n", encoding="utf-8")

    assert load_message(path) == "Olá!"


def test_load_message_rejects_empty_file(tmp_path):
    path = tmp_path / "message.txt"
    path.write_text("   \n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_message(path)


def test_deduplicate_keeps_first_occurrence():
    contacts = [
        Contact(name="João Silva", phone="5511999999999"),
        Contact(name="João Duplicado", phone="5511999999999"),
        Contact(name="Maria Souza", phone="5511988888888"),
    ]

    unique, duplicates = deduplicate(contacts)

    assert [c.name for c in unique] == ["João Silva", "Maria Souza"]
    assert [c.name for c in duplicates] == ["João Duplicado"]
