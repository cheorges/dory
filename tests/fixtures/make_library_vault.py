"""Writes `library-vault/`, the vault that measures link proposals (Record 009, Story 3).

Run `uv run python tests/fixtures/make_library_vault.py` after changing it; the vault is
committed, so the tests do not depend on this script. The files the requests in
`library-requests.json` are about are written by hand below; the rest is filler from short
templates, so that the vault has the size of a vault after a few months (about 150 files).
"""

import shutil
from pathlib import Path

VAULT = Path(__file__).parent / "library-vault"


def knowledge(domain: str, summary: str, body: str = "") -> str:
    return f"---\ntype: knowledge\ndomain: {domain}\nsummary: {summary}\nupdated: 2026-10-20\n---\n{body}"


def note(text: str, **properties: str) -> str:
    head = "".join(f"{key}: {value}\n" for key, value in properties.items())
    return f"---\ntype: note\ncreated: 2026-10-01\n{head}---\n{text}"


def topic(text: str, **properties: str) -> str:
    head = "".join(f"{key}: {value}\n" for key, value in properties.items())
    return f"---\ntype: topic\nupdated: 2026-10-15\n{head}---\n{text}"


def entry(text: str, **properties: str) -> str:
    head = "".join(f"{key}: {value}\n" for key, value in properties.items())
    return f"---\ntype: library\ncreated: 2026-09-01\nupdated: 2026-09-01\n{head}---\n{text}"


FILES: dict[str, str] = {
    # dory, work, English
    "projects/dory/knowledge.md": knowledge(
        "work",
        "Second brain for Claude Code sessions in an Obsidian vault.",
        "## Pitfalls\n- **Live checks count against the usage limit.** Run them in the background.\n",
    ),
    "projects/dory/notes/Release steps.md": note(
        "# Releasing dory\nBump the version in three files, write the CHANGELOG entry, merge with a "
        "merge commit and tag `vX.Y.Z` on main. Commit messages follow the conventional format "
        "with a scope, e.g. `feat(library): ...`.\n"
    ),
    "projects/dory/notes/Vault location.md": note(
        "The vault lives in iCloud Drive under `Documents/dory`. Obsidian keeps its properties in "
        "the frontmatter; links in a property must be quoted.\n",
        aliases="[Vault path]",
    ),
    "projects/dory/notes/Live checks.md": note(
        "# Live checks\nThey run `claude -p` headless in a throwaway vault. A Bash command on a path "
        "outside the session's working directory is refused there, so the skills must not rely "
        "on `grep` over the vault.\n"
    ),
    "projects/dory/notes/Worker model.md": note(
        "The worker runs with opus on the author's machine, haiku in the live checks.\n"
    ),
    "projects/dory/notes/Hook timing.md": note(
        "The SessionStart hook has about 10 seconds; recall must stay under one second.\n"
    ),
    # ai-assistant-hub, work, English
    "projects/ai-assistant-hub/knowledge.md": knowledge(
        "work",
        "KoliChat platform for the customers' assistants.",
        "## Facts\n- **Grafana takes port 3100, so Loki runs on 3200.** Every VM follows this.\n",
    ),
    "projects/ai-assistant-hub/notes/Loki port.md": note(
        "Loki runs on port 3200 on every customer VM because Grafana holds 3100. Log retention "
        "is set in the Loki config, see [[Loki retention]].\n",
        tags="[loki, logging]",
    ),
    "projects/ai-assistant-hub/notes/Customer VM setup.md": note(
        "# Setting up a customer VM\n1. Terraform apply in two phases.\n2. `deploy-loki.sh`.\n"
        "3. Check the Loki retention and the Grafana data source.\n"
    ),
    "projects/ai-assistant-hub/notes/Grafana data source.md": note(
        "Inside the Grafana container the Loki data source is `http://loki:3100`: containers in "
        "the same Docker Compose network reach each other by service name, never by localhost.\n"
    ),
    "projects/ai-assistant-hub/notes/Quota requests.md": note(
        "# Azure quota requests\nEvery new customer subscription needs eight quota forms for "
        "Azure OpenAI; the approval takes two to five days.\n",
        aliases="[Kontingent]",
    ),
    "projects/ai-assistant-hub/notes/Foundry throttling.md": note(
        "Azure AI Foundry throttles at six parallel calls and answers break off; the quality "
        "tests run through a separate Anthropic workspace.\n"
    ),
    "projects/ai-assistant-hub/notes/SSO setup.md": note(
        "Entra ID app registration per customer, redirect URI on the customer's domain.\n"
    ),
    # webshop, work, German
    "projects/webshop/knowledge.md": knowledge(
        "work",
        "Webshop eines Kunden mit Shopify und Bexio.",
        "## Facts\n- **Bexio ist die Buchhaltung des Kunden.** Rechnungen entstehen dort.\n",
    ),
    "projects/webshop/notes/Rechnungsstellung.md": note(
        "# Rechnungen aus dem Shop\nJede Bestellung wird als Rechnung in Bexio angelegt. Die "
        "Bexio-API verlangt ein Personal Access Token pro Benutzer; Rechnungen werden über "
        "`POST /2.0/kb_invoice` erstellt.\n",
        aliases="[Invoices, Fakturierung]",
    ),
    "projects/webshop/notes/Versandkosten.md": note(
        "Versand innerhalb der Schweiz pauschal 9 CHF, ab 150 CHF gratis.\n"
    ),
    "projects/webshop/notes/Zahlungsanbieter.md": note(
        "Twint und Kreditkarte über Payrexx; die Gebühren liegen bei 1.3 Prozent.\n"
    ),
    "projects/webshop/notes/Produktimport.md": note(
        "Produkte kommen als CSV aus dem ERP; Umlaute nur in UTF-8.\n"
    ),
    # box-cheorges, work, English
    "projects/box-cheorges/knowledge.md": knowledge(
        "work", "The author's server box with Docker Compose services."
    ),
    "projects/box-cheorges/notes/Caddy reverse proxy.md": note(
        "# Caddy in front of every service\nCaddy runs in the same Docker Compose network as the "
        "services and proxies to them by service name (`reverse_proxy app:8080`).\n"
    ),
    "projects/box-cheorges/notes/Backups with restic.md": note(
        "restic backs up the volumes nightly to the NAS; the password lives in the keychain.\n"
    ),
    "projects/box-cheorges/notes/Compose updates.md": note(
        "`docker compose pull && docker compose up -d` per service, never all at once. After an "
        "update the services find each other again, see [[Service names in Docker Compose]].\n"
    ),
    # haushalt, private, German
    "projects/haushalt/knowledge.md": knowledge("private", "Haushalt und Finanzen."),
    "projects/haushalt/notes/Steuern 2025.md": note(
        "# Steuererklärung 2025\nAbzüge: Säule 3a, Berufsauslagen, Weiterbildung. Frist Ende März, "
        "Verlängerung online bis September.\n",
        tags="[steuern]",
    ),
    "projects/haushalt/notes/Versicherungen.md": note(
        "Hausrat bei der Mobiliar, Haftpflicht dabei; Police im Ordner Finanzen.\n"
    ),
    "projects/haushalt/notes/Haushaltsbudget.md": note(
        "# Budget\nFixkosten monatlich, Rückstellung für die Steuern; was abziehbar ist, steht "
        "unter [[Steuerabzüge]].\n"
    ),
    # topic files
    "notes/Python.md": topic(
        "## Pitfalls\n- **pip breaks reproducible installs.** Use [[uv]] with its lock file.\n"
    ),
    "notes/Docker.md": topic(
        "## Facts\n- **Containers in one Compose network reach each other by service name.** "
        "localhost inside a container is the container itself.\n"
    ),
    "notes/Git.md": topic(
        "## How-to\n- **Write commit messages as `type(scope): description`.** The scope is "
        "required.\n",
        aliases="[Commits]",
    ),
    "notes/Obsidian.md": topic(
        "## Pitfalls\n- **Obsidian overwrites its vault list on quit.** Quit it before editing "
        "`obsidian.json`.\n- **Links in a property need quotes**, e.g. `source: \"[[Note]]\"`.\n"
    ),
    "notes/Azure.md": topic(
        "## Facts\n- **Azure OpenAI quota is per subscription and region.** A new subscription "
        "starts with almost none.\n"
    ),
    "notes/Claude Code.md": topic(
        "## Pitfalls\n- **Auto mode refuses deleting tags and branches.** The user runs those with "
        "`!`.\n- **A headless run refuses Bash on paths outside the working directory.**\n"
    ),
    "notes/Bexio.md": topic(
        "## Facts\n- **Bexio's API v2 takes a personal access token per user.**\n"
    ),
    "notes/Notion.md": topic(
        "## Pitfalls\n- **Overwriting a Notion page deletes its embedded databases.**\n"
    ),
    "notes/Markdown.md": topic("## Preferences\n- **Mermaid only when a flow needs one.**\n"),
    "notes/Shopping list.md": "---\ntype: list\nsummary: Shopping list\n---\n- [ ] Milk\n",
    "notes/Invoices.md": "---\ntype: register\nsummary: Invoices\n---\n- 2026-10-01 Hosting 12 CHF\n",
    # library
    "library/Python/Package management.md": entry(
        "Python packages are installed with uv, never pip, because uv locks the versions.\n",
        aliases='\n  - "uv"\n  - "pip replacement"',
    ),
    "library/Python/Testing.md": entry("pytest with fixtures; no mocks of the code under test.\n"),
    "library/Git/Commit messages.md": entry(
        "Commit messages follow `type(scope): description`, in English, with the scope required.\n",
        aliases='\n  - "Conventional commits"',
    ),
    "library/Cloud/Azure quota requests.md": entry(
        "How to file the eight Azure OpenAI quota forms for a new subscription.\n"
    ),
    "library/Finance/Taxes.md": entry(
        "Steuerabzüge: Säule 3a bis 7258 CHF pro Jahr.\n", aliases='\n  - "Steuerabzüge"'
    ),
    "library/Writing/Style.md": entry("No dashes as commas; every sentence carries a fact.\n"),
    "library/Docker/Compose basics.md": entry("A Compose file per service, volumes named.\n"),
}

FILLER: dict[str, list[str]] = {
    "dory": [
        "Session note format", "Summary limits", "Catalog size", "Queue retries", "Snapshot clones",
        "Language setting", "Search ranking", "Topic file naming", "Library guard", "Config sources",
        "Status output", "Transcript condensing", "Baseline checks", "Recall order",
        "Stale flags", "Trace section", "Bundle layout", "Repository documents", "Plugin cache",
        "Marketplace update", "Spawn guard", "Notes lock", "Entry keys",
    ],
    "ai-assistant-hub": [
        "KoliChat upgrade", "Knowledgebase indexing", "Customer DNS", "Key Vault secrets",
        "TLS renewal", "Usage billing", "Voice gateway", "Brave search key", "Moonshot fallback",
        "Run IDs in logs", "Tunnel script", "Customer offboarding", "Terraform state",
        "Mail relay", "Image studio", "Complaint tool", "Document comparison", "Embedding model",
        "Rate limits per customer", "Backup of the knowledgebase", "Customer tags",
        "Subscription budget", "Container images", "Compose profiles", "Health checks",
    ],
    "webshop": [
        "Lagerbestand", "Retouren", "Gutscheine", "Newsletter", "Produktbilder", "Mehrwertsteuer",
        "Kundenkonten", "Shopify-Themes", "Bestellbestätigung", "Lieferanten", "Preislisten",
        "Datenschutz", "Cookie-Banner", "Suchfunktion",
    ],
    "box-cheorges": [
        "Nextcloud", "Paperless", "Home Assistant", "Uptime Kuma", "Vaultwarden", "DNS at Infomaniak",
        "SSH keys", "Disk health", "Log rotation", "Firewall rules", "Tailscale", "Watchtower",
    ],
    "haushalt": [
        "Krankenkasse", "Hypothek", "Ferien 2026", "Auto Service", "Abos", "Haushaltsbudget",
        "Garten", "Elektriker", "Möbel",
    ],
}

TOPIC_FILLER = [
    "Shell", "Make", "Postgres", "Redis", "Terraform", "Caddy", "Tailscale", "macOS", "iCloud",
    "Outlook connector", "Slack", "Trello", "PowerPoint", "Word templates", "Swiss holidays",
    "Homebrew", "SSH", "YAML", "JSON", "Regex", "Excel", "Teams", "Zoom", "1Password", "Raycast",
]


# Words that real notes of each project mention in passing, so that a search for a term finds
# far more than the files that should link an entry.
CONTEXT = {
    "dory": "Checked with the live checks; the commit history has the details; runs with uv.",
    "ai-assistant-hub": "Runs on the customer's Azure subscription; logs go to Loki as usual.",
    "webshop": "Abgleich mit Bexio jeden Monat; die Rechnung geht per Mail.",
    "box-cheorges": "Runs as a Docker Compose service behind Caddy; restic backs it up.",
    "haushalt": "Beleg im Ordner Finanzen abgelegt.",
}


def filler_note(project: str, title: str) -> str:
    german = project in ("webshop", "haushalt")
    text = (
        f"Notizen zu {title}: Stand Oktober 2026, nichts Ungewöhnliches."
        if german
        else f"Notes on {title}: state of October 2026, nothing unusual."
    )
    return note(f"# {title}\n{text} {CONTEXT[project]}\n")


def main(out: Path = VAULT) -> None:
    shutil.rmtree(out, ignore_errors=True)
    files = dict(FILES)
    for project, titles in FILLER.items():
        for title in titles:
            files.setdefault(f"projects/{project}/notes/{title}.md", filler_note(project, title))
    for title in TOPIC_FILLER:
        files.setdefault(
            f"notes/{title}.md",
            topic(f"## Facts\n- **{title} works as documented.** Nothing to note yet.\n"),
        )
    for relative, text in files.items():
        path = out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(f"{len(files)} files in {out}")


if __name__ == "__main__":
    main()
