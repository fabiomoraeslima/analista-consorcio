from __future__ import annotations

import difflib
from dataclasses import dataclass

from src.contacts import Contact

NAME_SIMILARITY_WARNING_THRESHOLD = 0.4


@dataclass
class ValidationResult:
    phone_matches: bool
    name_similarity: float | None
    warning: str | None

    @property
    def ok(self) -> bool:
        return self.phone_matches


class WhatsAppOperator:
    """Validates that the chat found on WhatsApp Web corresponds to the expected contact.

    Phone number is the authoritative identifier (deterministic string comparison).
    Name comparison is advisory only: WhatsApp Web shows the recipient's own profile
    name, which may differ from the name in the spreadsheet, so a mismatch is logged
    as a warning rather than a block.
    """

    def validate(self, contact: Contact, displayed_phone: str, displayed_name: str | None) -> ValidationResult:
        phone_matches = contact.phone == displayed_phone

        name_similarity = None
        warning = None
        if not phone_matches:
            warning = (
                f"expected phone {contact.phone} but WhatsApp Web resolved to {displayed_phone}"
            )
        elif displayed_name:
            name_similarity = difflib.SequenceMatcher(
                a=contact.name.lower(), b=displayed_name.lower()
            ).ratio()
            if name_similarity < NAME_SIMILARITY_WARNING_THRESHOLD:
                warning = (
                    f"displayed name '{displayed_name}' looks unrelated to "
                    f"expected name '{contact.name}' (similarity={name_similarity:.2f})"
                )

        return ValidationResult(
            phone_matches=phone_matches, name_similarity=name_similarity, warning=warning
        )
