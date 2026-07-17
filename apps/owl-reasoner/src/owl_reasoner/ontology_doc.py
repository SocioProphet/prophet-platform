"""Ontology → browsable HTML documentation (pyLODE / Widoco / LODE class).

The KE audit's gap: we author 202 ontologies as Turtle and can reason + visualize them, but a buyer
can't *read* them — no browsable docs. Incumbents (pyLODE, Widoco, LODE) turn an OWL file into an HTML
page with classes, properties, domains/ranges, and definitions. This does that, dependency-light
(rdflib only), so the ontology estate becomes a sellable, dereferenceable asset instead of a folder of
`.ttl`. Pairs with the hellgraph-service resource endpoint: the same graph, now both queryable AND readable.
"""
from __future__ import annotations

from typing import Any

from rdflib import DCTERMS, OWL, RDF, RDFS, Graph, URIRef
from rdflib.namespace import SKOS


def _local(u: Any) -> str:
    s = str(u)
    for sep in ("#", "/"):
        if sep in s:
            return s.rsplit(sep, 1)[-1]
    return s


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def extract_ontology(turtle: str) -> dict[str, Any]:
    """Structured model of an ontology: header + classes + properties, each with label/comment/relations."""
    g = Graph()
    g.parse(data=turtle, format="turtle")

    def label(u: Any) -> str:
        for pred in (RDFS.label, SKOS.prefLabel, DCTERMS.title):
            v = g.value(u, pred)
            if v:
                return str(v)
        return _local(u)

    def comment(u: Any) -> str:
        for pred in (RDFS.comment, DCTERMS.description, SKOS.definition):
            v = g.value(u, pred)
            if v:
                return str(v)
        return ""

    # Ontology header
    onto_uri = next(iter(g.subjects(RDF.type, OWL.Ontology)), None)
    header = {
        "uri": str(onto_uri) if onto_uri else "",
        "title": label(onto_uri) if onto_uri else "Ontology",
        "description": comment(onto_uri) if onto_uri else "",
        "version": str(g.value(onto_uri, OWL.versionInfo) or "") if onto_uri else "",
    }

    # Classes
    class_uris: set[URIRef] = set()
    for t in (OWL.Class, RDFS.Class):
        class_uris.update(s for s in g.subjects(RDF.type, t) if isinstance(s, URIRef))
    for s, _, o in g.triples((None, RDFS.subClassOf, None)):
        if isinstance(s, URIRef):
            class_uris.add(s)
        if isinstance(o, URIRef):
            class_uris.add(o)
    classes = [{
        "uri": str(c), "label": label(c), "comment": comment(c),
        "superClasses": sorted({str(o) for o in g.objects(c, RDFS.subClassOf) if isinstance(o, URIRef)}),
    } for c in sorted(class_uris, key=lambda x: label(x).lower())]

    # Properties (object + datatype + bare rdf:Property)
    prop_uris: set[URIRef] = set()
    kinds: dict[str, str] = {}
    for t, kind in ((OWL.ObjectProperty, "object"), (OWL.DatatypeProperty, "datatype"), (RDF.Property, "property")):
        for s in g.subjects(RDF.type, t):
            if isinstance(s, URIRef):
                prop_uris.add(s)
                kinds.setdefault(str(s), kind)
    properties = [{
        "uri": str(p), "label": label(p), "comment": comment(p), "kind": kinds.get(str(p), "property"),
        "domain": sorted({str(o) for o in g.objects(p, RDFS.domain) if isinstance(o, URIRef)}),
        "range": sorted({str(o) for o in g.objects(p, RDFS.range) if isinstance(o, URIRef)}),
    } for p in sorted(prop_uris, key=lambda x: label(x).lower())]

    return {"header": header, "classes": classes, "properties": properties,
            "counts": {"classes": len(classes), "properties": len(properties)}}


def render_html(model: dict[str, Any]) -> str:
    """Render the extracted model as a single self-contained browsable HTML page."""
    h = model["header"]
    labels = {c["uri"]: c["label"] for c in model["classes"]}

    def link(uri: str) -> str:
        name = labels.get(uri, _local(uri))
        return f'<a href="#{_esc(_local(uri))}">{_esc(name)}</a>' if uri in labels else f'<code>{_esc(_local(uri))}</code>'

    def class_section(c: dict[str, Any]) -> str:
        anchor, cid = _esc(_local(c["uri"])), _esc(c["uri"])
        desc = f'<p>{_esc(c["comment"])}</p>' if c["comment"] else ""
        rel = "sub-class of " + ", ".join(link(s) for s in c["superClasses"]) if c["superClasses"] else ""
        return (f'<div class="term" id="{anchor}"><h3>{_esc(c["label"])}<span class="badge">Class</span></h3>'
                f'<p class="uri">{cid}</p>{desc}<p class="rel">{rel}</p></div>')

    def prop_section(p: dict[str, Any]) -> str:
        anchor, pid = _esc(_local(p["uri"])), _esc(p["uri"])
        desc = f'<p>{_esc(p["comment"])}</p>' if p["comment"] else ""
        dom = ", ".join(link(d) for d in p["domain"]) or "—"
        rng = ", ".join(link(r) for r in p["range"]) or "—"
        return (f'<div class="term" id="{anchor}"><h3>{_esc(p["label"])}<span class="badge">{_esc(p["kind"])} property</span></h3>'
                f'<p class="uri">{pid}</p>{desc}<p class="rel">domain: {dom} · range: {rng}</p></div>')

    toc_classes = "".join(f'<li>{link(c["uri"])}</li>' for c in model["classes"])
    toc_props = "".join(f'<li>{link(p["uri"])}</li>' for p in model["properties"])
    classes_html = "".join(class_section(c) for c in model["classes"])
    props_html = "".join(prop_section(p) for p in model["properties"])

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{_esc(h['title'])}</title>
<style>
body{{font:15px/1.6 system-ui,-apple-system,sans-serif;max-width:60rem;margin:0 auto;padding:2rem 1rem;color:#1a1a1a}}
h1{{font-size:1.5rem}}h2{{font-size:1.05rem;border-bottom:2px solid #eee;padding-bottom:.3rem;margin-top:2.5rem}}
h3{{font-size:1rem;margin:0 0 .2rem}}.badge{{font-size:.65rem;font-weight:600;text-transform:uppercase;background:#eef;color:#446;padding:.1rem .4rem;border-radius:.3rem;margin-left:.5rem;vertical-align:middle}}
.term{{border-left:3px solid #e0e4f0;padding:.5rem 0 .5rem 1rem;margin:1rem 0}}
.uri{{font:12px ui-monospace,monospace;color:#888;word-break:break-all;margin:.1rem 0}}
.rel{{color:#555;font-size:.9rem}}.meta{{color:#666}}ul.toc{{columns:2;list-style:none;padding:0}}
ul.toc li{{margin:.1rem 0}}a{{color:#0645ad;text-decoration:none}}a:hover{{text-decoration:underline}}
code{{font:12px ui-monospace,monospace;background:#f4f4f4;padding:.05rem .3rem;border-radius:.2rem}}
@media(prefers-color-scheme:dark){{body{{background:#111;color:#ddd}}h2{{border-color:#333}}.term{{border-color:#334}}
.badge{{background:#223;color:#aac}}.uri,.meta{{color:#999}}.rel{{color:#aaa}}code{{background:#222}}a{{color:#6ab0ff}}}}
</style></head><body>
<h1>{_esc(h['title'])}</h1>
{f'<p class="uri">{_esc(h["uri"])}</p>' if h['uri'] else ''}
{f'<p class="meta">Version {_esc(h["version"])}</p>' if h['version'] else ''}
{f'<p>{_esc(h["description"])}</p>' if h['description'] else ''}
<p class="meta">{model['counts']['classes']} classes · {model['counts']['properties']} properties</p>
{f'<h2>Classes</h2><ul class="toc">{toc_classes}</ul>{classes_html}' if model['classes'] else ''}
{f'<h2>Properties</h2><ul class="toc">{toc_props}</ul>{props_html}' if model['properties'] else ''}
<p class="meta" style="margin-top:3rem">Generated by owl-reasoner — a proof-carrying HellGraph ontology.</p>
</body></html>"""


def ontology_doc(turtle: str) -> str:
    """Turtle → browsable HTML documentation page."""
    return render_html(extract_ontology(turtle))
