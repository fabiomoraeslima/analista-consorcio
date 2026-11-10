from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, field_validator


class Contact(BaseModel):
    name: str
    phone: str

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("phone")
    @classmethod
    def phone_must_be_digits_only(cls, value: str) -> str:
        digits = re.sub(r"\D", "", str(value))
        if not (8 <= len(digits) <= 15):
            raise ValueError(f"phone '{value}' must have between 8 and 15 digits")
        return digits


def load_contacts(csv_path: str | Path) -> list[Contact]:
    """Load contacts from a CSV file with 'name' and 'phone' columns."""
    df = pd.read_csv(csv_path, dtype={"phone": str})
    df.columns = [str(c).strip().lower() for c in df.columns]

    missing = {"name", "phone"} - set(df.columns)
    if missing:
        raise ValueError(f"contacts file is missing required columns: {sorted(missing)}")

    contacts = []
    for row in df.to_dict(orient="records"):
        contacts.append(Contact(name=row["name"], phone=row["phone"]))
    return contacts


def load_message(message_path: str | Path) -> str:
    """Load the message body to be sent, stripped of trailing whitespace."""
    text = Path(message_path).read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("message file is empty")
    return text


def deduplicate(contacts: list[Contact]) -> tuple[list[Contact], list[Contact]]:
    """Split contacts into (unique, duplicates) keeping the first occurrence per phone."""
    seen: set[str] = set()
    unique: list[Contact] = []
    duplicates: list[Contact] = []
    for contact in contacts:
        if contact.phone in seen:
            duplicates.append(contact)
        else:
            seen.add(contact.phone)
            unique.append(contact)
    return unique, duplicates
