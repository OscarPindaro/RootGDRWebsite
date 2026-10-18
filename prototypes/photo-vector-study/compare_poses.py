# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow==12.0.0"]
# ///
"""Assemble the saved model outputs; does not rerun or correct pose inference."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent / "output"
CHARACTERS = [("altus", "Altus"), ("luciano", "Luciano"), ("wolf", "Tacito")]
MODELS = [
    ("humanart", "HumanArt", "isolated-crop-assisted"),
    ("dwpose", "dghs-imgutils / DWPose", "crop-assisted"),
    ("bizarre", "Bizarre · feat_match+data", "crop-assisted"),
]


def main() -> None:
    output = ROOT / "pose-comparison"
    output.mkdir(parents=True, exist_ok=True)
    font = "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"
    title, small = ImageFont.truetype(font, 30), ImageFont.truetype(font, 18)
    board = Image.new("RGB", (1650, 2240), "#f4f0e5")
    ink = ImageDraw.Draw(board)
    ink.text(
        (30, 25), "Tre modelli sullo stesso ritaglio OpenCV", font=title, fill="#302d2b"
    )
    ink.text(
        (30, 75),
        "Pose richieste sul ritaglio · nessuna correzione manuale delle articolazioni",
        font=small,
        fill="#786e61",
    )
    for column, (_, label, _) in enumerate(MODELS):
        ink.text((30 + column * 540, 115), label, font=small, fill="#302d2b")
    rows = []
    for row, (slug, label) in enumerate(CHARACTERS):
        figures = []
        for column, (folder, model, suffix) in enumerate(MODELS):
            name = f"{slug}-{suffix}.png"
            image = ImageOps.contain(Image.open(ROOT / folder / name), (490, 590))
            board.paste(
                image,
                (
                    30 + column * 540 + (490 - image.width) // 2,
                    160 + row * 680 + (590 - image.height) // 2,
                ),
            )
            figures.append(
                f'<figure><a href="../{folder}/{name}" target="_blank">'
                f'<img src="../{folder}/{name}" alt="{label} — {model}"></a>'
                f"<figcaption>{model}</figcaption></figure>"
            )
        ink.text((30, 160 + row * 680 + 610), label, font=title, fill="#302d2b")
        rows.append(
            f"<article><h2>{label}</h2><div class='figures'>{''.join(figures)}</div></article>"
        )
    board.save(output / "comparison.png")
    (output / "index.html").write_text(
        """<!doctype html><html lang="it"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Confronto dei modelli di posa</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f0e5;color:#302d2b;font:16px/1.6 system-ui}
main{max-width:1500px;margin:auto;padding:30px}h1{font:42px Georgia,serif}h2{font:28px Georgia,serif}
p{max-width:950px}article{border-top:1px solid #c9bfac;margin-top:28px}
.figures{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}figure{margin:0}
img{width:100%;height:560px;object-fit:contain}figcaption{text-align:center}
a{color:#365b70;display:inline-flex;align-items:center;min-height:44px}figure a{display:block}
@media(max-width:650px){main{padding:20px 14px}.figures{gap:8px}img{height:320px}figcaption{font-size:12px}}
</style><main><h1>Tre modelli, le stesse figure.</h1>
<p>Tutti ricevono lo stesso ritaglio prodotto da OpenCV. HumanArt resta il risultato
più plausibile per Tacito. DWPose recupera parte delle gambe; Bizarre confonde
diverse articolazioni e include la spada nella posa.</p>
<p>HumanArt e DWPose mostrano i punti con punteggio ≥ 0,3. Bizarre mostra tutte
le proposte, come nella visualizzazione originale. I valori dei tre modelli
non sono probabilità direttamente confrontabili.</p>
<p>Nei test separati di rilevamento automatico, HumanArt trova Luciano e Tacito;
DWPose non trova nessuno dei tre. Bizarre è stato provato sul ritaglio, senza
il suo segmentatore originale. Nessuna articolazione è stata spostata a mano.</p>
<p><a href="comparison.png" target="_blank">Confronto PNG completo</a> ·
<a href="../shapes/">Nuova rappresentazione a forme</a> ·
<a href="../study.zip" download>Scarica risultati e codice</a></p>
ROWS
<article><h2>Controlli</h2><p>Bizarre riconosce una posa plausibile nel campione anime
fornito dagli autori; DWPose riconosce la fotografia umana di controllo.</p>
<div class="figures"><figure><img src="../bizarre/anime-control-crop-assisted.png"
alt="Controllo anime di Bizarre"><figcaption>Campione originale Bizarre · © Disco Brando</figcaption></figure>
<figure><img src="../dwpose/control-detected.png" alt="Controllo umano DWPose">
<figcaption>Fotografia di controllo</figcaption></figure></div></article>
</main></html>""".replace("ROWS", "".join(rows))
    )


if __name__ == "__main__":
    main()
