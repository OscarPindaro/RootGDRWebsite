"""Genera il rendering lato server del documento di prova.

Usa la stessa configurazione dell'applicazione (src/backend/jinja.py):

    MarkdownIt("commonmark", {"html": False})

piu' un plugin per le reference @[Nome], che e' il pezzo da aggiungere al
backend. L'output e' puro HTML semantico: niente stile, niente icone.

    uv run python prototypes/devin-prototype/tools/render_server_side.py

Scrive server-render.html accanto alle pagine del prototipo.
"""

from __future__ import annotations

import html
import io
import pathlib

from markdown_it import MarkdownIt

# Nel prodotto questi arrivano dal database, filtrati per i permessi di chi
# legge: e' esattamente il motivo per cui la risoluzione sta qui e non nel
# browser. Nel prototipo sono scritti a mano.
ENTITIES = {
    "Il Guado Spezzato": {"kind": "luogo", "tint": "p8", "href": "luogo.html"},
    "Barone Talpa": {"kind": "personaggio", "tint": "p8", "href": "personaggio.html"},
    "Le regole della Casa": {"kind": "pagina", "tint": "p3", "href": "pagina.html"},
    "Rugginosa": {"kind": "personaggio", "tint": "p1", "href": "personaggio.html"},
    "Madre Civetta": {"kind": "npc", "tint": "p7", "href": "npc.html"},
    "L'inverno dei corvi": {"kind": "sessione", "tint": "p8", "href": "sessione.html"},
}


def mention_plugin(md: MarkdownIt) -> None:
    """Trasforma @[Nome] in un link con tipo e tinta del contenuto citato."""

    def mention(state, silent: bool) -> bool:
        src = state.src
        pos = state.pos
        if src[pos] != "@" or src[pos + 1 : pos + 2] != "[":
            return False
        end = src.find("]", pos + 2)
        if end < 0:
            return False
        label = src[pos + 2 : end]
        if not silent:
            token = state.push("mention", "", 0)
            token.meta = {"label": label, "entry": ENTITIES.get(label)}
        state.pos = end + 1
        return True

    def render(self, tokens, idx, options, env) -> str:
        token = tokens[idx]
        label = html.escape(token.meta["label"], quote=True)
        entry = token.meta.get("entry")
        if entry is None:
            return (
                '<span class="mention mention--missing" '
                'title="Nessun contenuto con questo nome">@'
                f"{label}</span>"
            )
        kind = html.escape(entry["kind"], quote=True)
        return (
            f'<a class="mention" href="{html.escape(entry["href"], quote=True)}" '
            f'data-kind="{kind}" data-color="{entry["tint"]}" title="{kind}">'
            f"{label}</a>"
        )

    md.inline.ruler.before("link", "mention", mention)
    md.add_render_rule("mention", render)


SAMPLE = """Roccianera non si vede da fuori. L'ingresso è una fenditura a mezza costa sopra @[Il Guado Spezzato], e da lì si scende per tre livelli senza incontrare una sola finestra.

## I tre livelli

Il primo è il mercato: banchi di pietra, turni di lampade ogni sei ore. Il secondo è la corte, dove @[Barone Talpa] riceve chi ha qualcosa da offrire.

> «Chi scende al terzo livello non torna a raccontarlo. Chi torna, non era al terzo livello.»

- Il pozzo centrale scende più in basso del terzo livello.
- Le porte del secondo livello si chiudono dall'interno, mai dall'esterno.
- Nessuno paga in moneta: si paga secondo @[Le regole della Casa], in favori registrati.

## Aperto

La porta che i giocatori non hanno ancora aperto è al secondo livello, dietro la corte. @[Madre Civetta] sostiene di sapere cosa c'è dietro; non lo dirà gratis. E @[Nessuno Sa Chi Sono] resta un nome che non esiste.
"""


def main() -> None:
    md = MarkdownIt("commonmark", {"html": False})
    mention_plugin(md)

    body = md.render(SAMPLE)
    out = pathlib.Path(__file__).resolve().parent.parent / "server-render.html"
    io.open(out, "w", encoding="utf-8").write(body + "\n")
    print(f"scritto {out.name}: {len(body)} byte")


if __name__ == "__main__":
    main()
