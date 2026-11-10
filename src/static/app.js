const IMAGE_EXTENSIONS = new Set(["jpg", "jpeg", "png", "gif", "webp", "bmp", "heic"]);

function extensionOf(filename) {
  const parts = filename.split(".");
  return parts.length > 1 ? parts.pop().toLowerCase() : "";
}

async function loadContacts() {
  const res = await fetch("/api/contacts");
  const contacts = await res.json();
  const body = document.getElementById("contacts-body");
  body.innerHTML = "";
  contacts.forEach((c) => addContactRow(c.name, c.phone));
}

function addContactRow(name = "", phone = "") {
  const body = document.getElementById("contacts-body");
  const row = document.createElement("tr");

  const nameCell = document.createElement("td");
  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.value = name;
  nameInput.className = "contact-name";
  nameCell.appendChild(nameInput);

  const phoneCell = document.createElement("td");
  const phoneInput = document.createElement("input");
  phoneInput.type = "text";
  phoneInput.value = phone;
  phoneInput.className = "contact-phone";
  phoneCell.appendChild(phoneInput);

  const removeCell = document.createElement("td");
  const removeButton = document.createElement("button");
  removeButton.textContent = "Remover";
  removeButton.onclick = () => row.remove();
  removeCell.appendChild(removeButton);

  row.appendChild(nameCell);
  row.appendChild(phoneCell);
  row.appendChild(removeCell);
  body.appendChild(row);
}

async function saveContacts() {
  const rows = [...document.querySelectorAll("#contacts-body tr")].map((row) => ({
    name: row.querySelector(".contact-name").value,
    phone: row.querySelector(".contact-phone").value,
  }));

  const res = await fetch("/api/contacts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(rows),
  });
  const data = await res.json();
  const status = document.getElementById("contacts-status");
  if (res.ok) {
    status.textContent = `Salvo (${data.count} contatos).`;
  } else {
    status.textContent = "Erro: " + data.errors.map((e) => `linha ${e.row + 1}: ${e.error}`).join("; ");
  }
}

async function loadMessage() {
  const res = await fetch("/api/message");
  const data = await res.json();
  document.getElementById("message-text").value = data.message;
}

async function saveMessage() {
  const message = document.getElementById("message-text").value;
  await fetch("/api/message", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  document.getElementById("message-status").textContent = "Salvo.";
}

async function loadAttachments() {
  const res = await fetch("/api/attachments");
  const files = await res.json();
  const list = document.getElementById("attachments-list");
  list.innerHTML = "";
  files.forEach((f) => {
    const item = document.createElement("div");
    item.className = "attachment-item";

    if (IMAGE_EXTENSIONS.has(extensionOf(f.name))) {
      const img = document.createElement("img");
      img.src = `/data-attachments/${encodeURIComponent(f.name)}`;
      img.alt = f.name;
      img.className = "attachment-thumb";
      item.appendChild(img);
    }

    const label = document.createElement("span");
    label.textContent = `${f.name} (${(f.size / 1024).toFixed(1)} KB)`;
    item.appendChild(label);

    const removeButton = document.createElement("button");
    removeButton.textContent = "Remover";
    removeButton.onclick = async () => {
      await fetch(`/api/attachments/${encodeURIComponent(f.name)}`, { method: "DELETE" });
      loadAttachments();
    };
    item.appendChild(removeButton);

    list.appendChild(item);
  });
}

async function uploadAttachments() {
  const input = document.getElementById("attachments-input");
  if (!input.files.length) return;

  const formData = new FormData();
  for (const file of input.files) {
    formData.append("files", file);
  }
  await fetch("/api/attachments", { method: "POST", body: formData });
  input.value = "";
  document.getElementById("attachments-status").textContent = "Enviado.";
  loadAttachments();
}

let pollTimer = null;
let linesSeen = 0;

async function pollRunStatus() {
  const res = await fetch(`/api/run/status?since=${linesSeen}`);
  const data = await res.json();
  const log = document.getElementById("run-log");
  for (const line of data.lines) {
    log.textContent += line + "\n";
  }
  linesSeen = data.total;
  log.scrollTop = log.scrollHeight;

  if (!data.running) {
    clearInterval(pollTimer);
    pollTimer = null;
    document.getElementById("run-button").disabled = false;
  }
}

async function startRun() {
  const button = document.getElementById("run-button");
  const log = document.getElementById("run-log");
  log.textContent = "";
  linesSeen = 0;

  const res = await fetch("/api/run", { method: "POST" });
  if (!res.ok) {
    log.textContent = "Já existe uma execução em andamento.";
    return;
  }
  button.disabled = true;
  pollTimer = setInterval(pollRunStatus, 1000);
}

document.getElementById("add-contact").onclick = () => addContactRow();
document.getElementById("save-contacts").onclick = saveContacts;
document.getElementById("save-message").onclick = saveMessage;
document.getElementById("upload-attachments").onclick = uploadAttachments;
document.getElementById("run-button").onclick = startRun;

loadContacts();
loadMessage();
loadAttachments();
