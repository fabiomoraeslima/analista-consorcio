from __future__ import annotations

import sys
from pathlib import Path

from src.agent import WhatsAppOperator
from src.contacts import deduplicate, load_contacts, load_message
from src.logs import RunLog, Status
from src.whatsapp import WhatsAppClient

CONTACTS_PATH = Path("data/contacts.xlsx")
MESSAGE_PATH = Path("data/message.txt")
LOG_PATH = Path("logs/results.jsonl")


def ask_approval(name: str, phone: str, message: str) -> bool:
    print("\n--- Aprovação necessária ---")
    print(f"Contato: {name} ({phone})")
    print(f"Mensagem:\n{message}")
    answer = input("Enviar esta mensagem? [s/N]: ").strip().lower()
    return answer in {"s", "sim", "y", "yes"}


def run() -> None:
    contacts = load_contacts(CONTACTS_PATH)
    message = load_message(MESSAGE_PATH)
    contacts, duplicates = deduplicate(contacts)

    log = RunLog(LOG_PATH)
    already_processed = log.already_processed_phones()

    for contact in duplicates:
        log.record(contact.name, contact.phone, message, Status.SKIPPED, reason="duplicate phone in contact list")

    operator = WhatsAppOperator()
    client = WhatsAppClient()
    client.start()

    try:
        for contact in contacts:
            if contact.phone in already_processed:
                log.record(contact.name, contact.phone, message, Status.SKIPPED, reason="already processed")
                continue

            log.record(contact.name, contact.phone, message, Status.PENDING)

            try:
                chat = client.open_chat(contact.phone)
            except Exception as exc:  # recoverable per-contact failure
                log.record(contact.name, contact.phone, message, Status.FAILED, reason=str(exc))
                continue

            if not chat.found:
                log.record(contact.name, contact.phone, message, Status.FAILED, reason=chat.error)
                continue

            validation = operator.validate(contact, contact.phone, chat.displayed_name)
            if not validation.ok:
                log.record(contact.name, contact.phone, message, Status.FAILED, reason=validation.warning)
                continue

            log.record(contact.name, contact.phone, message, Status.CONTACT_FOUND, reason=validation.warning)

            try:
                client.type_message(message)
            except Exception as exc:
                log.record(contact.name, contact.phone, message, Status.FAILED, reason=str(exc))
                continue

            log.record(contact.name, contact.phone, message, Status.AWAITING_APPROVAL)

            if not ask_approval(contact.name, contact.phone, message):
                log.record(contact.name, contact.phone, message, Status.SKIPPED, reason="not approved by operator")
                continue

            sent = client.send_message()
            if sent:
                log.record(contact.name, contact.phone, message, Status.SENT)
            else:
                log.record(contact.name, contact.phone, message, Status.FAILED, reason="send confirmation timed out")

    except KeyboardInterrupt:
        print("\nExecução interrompida pelo usuário.", file=sys.stderr)
    finally:
        client.close()


if __name__ == "__main__":
    run()
