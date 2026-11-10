from __future__ import annotations

import sys
from pathlib import Path

from src.agent import WhatsAppOperator
from src.contacts import deduplicate, load_contacts, load_message
from src.logs import RunLog, Status
from src.whatsapp import WhatsAppClient

CONTACTS_PATH = Path("data/contacts.csv")
MESSAGE_PATH = Path("data/message.txt")
LOG_PATH = Path("logs/results.jsonl")


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
    print("Abrindo WhatsApp Web...")
    client.start()
    print("Login confirmado. Iniciando processamento dos contatos.")

    try:
        for contact in contacts:
            print(f"\n[{contact.name} / {contact.phone}] processando...")

            if contact.phone in already_processed:
                print("  -> já processado anteriormente, pulando.")
                log.record(contact.name, contact.phone, message, Status.SKIPPED, reason="already processed")
                continue

            log.record(contact.name, contact.phone, message, Status.PENDING)

            try:
                chat = client.open_chat(contact.phone)
            except Exception as exc:  # recoverable per-contact failure
                print(f"  -> falha ao abrir conversa: {exc}")
                log.record(contact.name, contact.phone, message, Status.FAILED, reason=str(exc))
                continue

            if not chat.found:
                print(f"  -> contato não encontrado: {chat.error}")
                log.record(contact.name, contact.phone, message, Status.FAILED, reason=chat.error)
                continue

            validation = operator.validate(contact, chat.displayed_phone, chat.displayed_name)
            if not validation.ok:
                print(f"  -> validação falhou: {validation.warning}")
                log.record(contact.name, contact.phone, message, Status.FAILED, reason=validation.warning)
                continue

            print(f"  -> conversa encontrada (nome exibido: {chat.displayed_name!r}).")
            log.record(contact.name, contact.phone, message, Status.CONTACT_FOUND, reason=validation.warning)

            try:
                client.type_message(message)
            except Exception as exc:
                print(f"  -> falha ao digitar mensagem: {exc}")
                log.record(contact.name, contact.phone, message, Status.FAILED, reason=str(exc))
                continue

            log.record(contact.name, contact.phone, message, Status.AWAITING_APPROVAL)

            sent = client.send_message()
            if sent:
                print("  -> mensagem enviada.")
                log.record(contact.name, contact.phone, message, Status.SENT)
            else:
                print("  -> timeout esperando confirmação de envio.")
                log.record(contact.name, contact.phone, message, Status.FAILED, reason="send confirmation timed out")

    except KeyboardInterrupt:
        print("\nExecução interrompida pelo usuário.", file=sys.stderr)
    finally:
        client.close()


if __name__ == "__main__":
    run()
