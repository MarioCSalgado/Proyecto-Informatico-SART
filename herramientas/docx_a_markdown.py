"""Convierte secciones del informe SRS (.docx) a Markdown para usarlas como especificación del código.

Uso:  python herramientas/docx_a_markdown.py informe.docx "3." "5." > docs/especificacion/x.md
Exporta desde el título de nivel 1 que empieza con el primer prefijo hasta antes del que empieza con el segundo.
"""
import re, sys
import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

def bloques(doc):
    for hijo in doc.element.body.iterchildren():
        if hijo.tag == qn('w:p'):
            yield Paragraph(hijo, doc)
        elif hijo.tag == qn('w:tbl'):
            yield Table(hijo, doc)

def celdas(fila):
    vistas, salida = set(), []
    for c in fila.cells:              # celdas combinadas aparecen repetidas
        if id(c._tc) in vistas: continue
        vistas.add(id(c._tc)); salida.append(c)
    return salida

def texto(c):
    return "\n".join(p.text.strip() for p in c.paragraphs if p.text.strip())

def tabla_md(t):
    filas = [[texto(c) for c in celdas(f)] for f in t.rows]
    if not filas: return ""
    # ficha de requisito (2 columnas, primera fila "RF-x · título | Prioridad")
    if len(filas[0]) == 2 and re.match(r'^RF-\d+ ·', filas[0][0]):
        out = [f"### {filas[0][0]} — {filas[0][1]}", ""]
        for k, v in filas[1:]:
            if k.startswith("Criterios de aceptación"):
                out += ["", f"**{k}:**", "", "```gherkin", v, "```", ""]
            elif k.startswith("Flujo"):
                out += ["", f"**{k}:**", ""] + [f"{l}" for l in v.split("\n")] + [""]
            else:
                out += [f"- **{k}:** " + v.replace("\n", " ")]
        return "\n".join(out) + "\n"
    # tabla clave-valor (2 columnas sin encabezado)
    if all(len(f) == 2 for f in filas) and len(filas) > 1 and not filas[0][0].isupper():
        return "\n".join(f"- **{k}:** " + v.replace("\n", " ") for k, v in filas) + "\n"
    ancho = max(len(f) for f in filas)
    filas = [f + [""] * (ancho - len(f)) for f in filas]
    esc = lambda s: s.replace("|", "\\|").replace("\n", "<br>")
    out = ["| " + " | ".join(esc(x) for x in filas[0]) + " |",
           "|" + "---|" * ancho]
    out += ["| " + " | ".join(esc(x) for x in f) + " |" for f in filas[1:]]
    return "\n".join(out) + "\n"

def exportar(ruta, desde, hasta):
    d = docx.Document(ruta)
    dentro, out = False, []
    for b in bloques(d):
        if isinstance(b, Paragraph):
            t = b.text.strip(); est = b.style.name if b.style is not None else ""
            nivel = int(est[-1]) if est.startswith("Heading") and est[-1].isdigit() else 0
            if nivel == 1 and t.startswith(desde): dentro = True
            elif nivel == 1 and hasta and t.startswith(hasta): dentro = False
            if not dentro or not t: continue
            if nivel and len(t) < 90: out.append("#" * nivel + " " + t + "\n")
            else: out.append(t + "\n")
        elif dentro:
            out.append(tabla_md(b))
    return "\n".join(out)

if __name__ == "__main__":
    print(exportar(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None))
