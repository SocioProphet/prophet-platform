# Anatomy atlas — vendored system plates

Polished, **open-licensed** medical illustrations for the Digital Health Twin, one per organ system.
Vendored here (sovereign / self-hosted) rather than hot-linked. The surface (`HealthTwin.vue`, via
`src/data/anatomyAtlas.ts`) resolves **vendored → remote CC-BY → placeholder**, so it works before the
files land; drop the approved images in and they take over.

## License
All plates are **CC BY 4.0** — attribution is rendered on the surface (per-plate figcaption + a blanket
credit). Keep sources CC-BY (no share-alike) so the product stays license-clean.

Sources:
- **OpenStax Anatomy & Physiology 2e** — CC BY 4.0 — https://openstax.org/details/books/anatomy-and-physiology-2e
- **Servier Medical Art (SMART)** — CC BY 4.0 — https://smart.servier.com
- Browse/confirm per-figure on **AnatomyTOOL** (license-labeled) — https://anatomytool.org

## Files to vendor (filename → source figure)
Review + approve on AnatomyTOOL, then save the image here at the exact path the manifest expects:

| file | system | source figure (confirm on AnatomyTOOL / Commons) |
|---|---|---|
| `nervous.png` | Nervous | OpenStax A&P — nervous system overview |
| `cardiovascular.png` | Cardiovascular | OpenStax A&P — heart / circulatory system |
| `respiratory.png` | Respiratory | OpenStax A&P fig. 22.2 “Major Respiratory Organs” (Commons: `2301 Major Respiratory Organs.jpg`) |
| `digestive.png` | Digestive (hepatic) | OpenStax A&P — components of the digestive system |
| `urinary.png` | Urinary | OpenStax A&P — the urinary system |

After adding a file, set its `vendored` path is already wired in `anatomyAtlas.ts` — no code change needed.
Attribution string per plate is already in the manifest; update it if you swap the source figure.
