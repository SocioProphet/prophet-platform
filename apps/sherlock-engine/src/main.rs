// Sherlock engine — sovereign, ontology-driven HYBRID Discovery search (no JVM).
//   lexical: Tantivy (Lucene-in-Rust, BM25)
//   dense:   estate embeddings (nomic-embed-text) → Qdrant (shared platform vector substrate)
//   fusion:  Reciprocal Rank Fusion (RRF) of the two ranked lists
// Dense tier is OPTIONAL: if EMBEDDINGS_URL / QDRANT_URL are unset or unreachable, it degrades to
// BM25-only (never fails the query). Riding the shared mesh-qdrant — not a new vector store.
//
// Corpus durability (KMASS baseline 2026-08-01 found TAB.TEXT.SCALE=12 docs, a static
// in-image fixture with no way to grow it): the tantivy index itself stays in-RAM and is
// rebuilt on every boot -- fast at these scales, and it sidesteps a second store that could
// drift from the doc list. What persists is the DOC LIST: if SHERLOCK_DATA_DIR is set (wired
// to a PVC in deploy/values/sherlock-engine.yaml), documents live in an append-only JSONL file
// there, seeded once from the static corpus on first boot, and grown via POST /ingest. Without
// SHERLOCK_DATA_DIR set, behavior is unchanged from before this fix: static in-image corpus only.
//
// Bounded (2026-08-04, boot-hydration audit / INV-DEP-16): the in-RAM index + doc Vec scale with
// corpus size, so a store grown without limit via /ingest is the compute-gateway OOM class. /ingest
// is therefore capped at SHERLOCK_MAX_DOCS (default 50_000): at capacity it returns {"ok": false}
// instead of growing the resident set until the pod OOMs on the next boot. Unbounded scale is the
// disk-backed (tantivy MmapDirectory) migration — deliberately deferred, since it reintroduces the
// index/doc-list drift the in-RAM rebuild exists to avoid.
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::{BTreeMap, HashMap};
use std::io::Write as _;
use std::path::PathBuf;
use std::time::Duration;
use tantivy::collector::TopDocs;
use tantivy::query::QueryParser;
use tantivy::schema::{OwnedValue, Schema, FAST, STORED, STRING, TEXT};
use tantivy::{doc, Index, TantivyDocument};

#[derive(Deserialize, Serialize, Clone)]
struct Doc {
    id: String,
    title: String,
    doctype: String,
    category: String,
    region: String,
    score: f64,
    body: String,
}

fn docs_store_path() -> Option<PathBuf> {
    std::env::var("SHERLOCK_DATA_DIR")
        .ok()
        .filter(|d| !d.is_empty())
        .map(|d| PathBuf::from(d).join("docs.jsonl"))
}

// Resident-corpus cap. The lexical index is in-RAM (Index::create_in_ram) and rebuilt from the
// full Vec<Doc> on every boot, so BOTH the doc Vec and the index scale with corpus size — the same
// class as the 2026-08-04 compute-gateway OOM, latent because the store grows only via /ingest on
// the 2Gi PVC. Rather than reintroduce a persistent second index (the very drift the in-RAM design
// deliberately avoids — see the module header), bound the resident set: /ingest REFUSES past
// SHERLOCK_MAX_DOCS instead of growing until the pod OOMs mid-boot with no warning. A corpus that
// must exceed this wants the disk-backed (tantivy MmapDirectory) migration, a separate decision.
const DEFAULT_MAX_DOCS: usize = 50_000;

fn parse_cap(raw: Option<String>) -> usize {
    raw.and_then(|v| v.parse::<usize>().ok())
        .filter(|&n| n > 0) // 0/garbage/absent all fall back to the default; a cap of 0 is meaningless
        .unwrap_or(DEFAULT_MAX_DOCS)
}

fn corpus_cap() -> usize {
    parse_cap(std::env::var("SHERLOCK_MAX_DOCS").ok())
}

fn at_capacity(current_docs: usize, cap: usize) -> bool {
    current_docs >= cap
}

/// Loads the working doc set and, when SHERLOCK_DATA_DIR is configured, the path an
/// ingested document must be appended to for it to survive a restart. On first boot
/// against an empty/absent store, seeds it from the static corpus so the persistent
/// copy becomes the source of truth going forward -- the image's corpus file is only
/// ever read once per volume's lifetime.
fn load_docs(corpus_path: &str) -> (Vec<Doc>, Option<PathBuf>) {
    let seed = || -> Vec<Doc> {
        let data = std::fs::read_to_string(corpus_path).expect("read corpus");
        serde_json::from_str(&data).expect("parse corpus")
    };

    let Some(store_path) = docs_store_path() else {
        return (seed(), None);
    };

    if let Ok(data) = std::fs::read_to_string(&store_path) {
        let docs: Vec<Doc> = data
            .lines()
            .filter(|l| !l.trim().is_empty())
            .filter_map(|l| serde_json::from_str(l).ok())
            .collect();
        if !docs.is_empty() {
            eprintln!("loaded {} doc(s) from persistent store {store_path:?}", docs.len());
            return (docs, Some(store_path));
        }
    }

    let docs = seed();
    if let Some(parent) = store_path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    // Copilot review on #1207: the previous version returned Some(store_path)
    // regardless of whether this write actually succeeded, so /healthz could
    // report persistent:true for a corpus that would NOT survive a restart --
    // exactly the claimed-durability-that-isn't-real bug this fix exists to
    // stop. Track every fallible step (create, and each line write) and only
    // report a persistent store if the whole bootstrap actually landed on disk.
    let bootstrap_ok = (|| -> std::io::Result<()> {
        let mut f = std::fs::File::create(&store_path)?;
        for d in &docs {
            writeln!(f, "{}", serde_json::to_string(d).unwrap())?;
        }
        Ok(())
    })();
    match bootstrap_ok {
        Ok(()) => {
            eprintln!("bootstrapped {} seed doc(s) into persistent store {store_path:?}", docs.len());
            (docs, Some(store_path))
        }
        Err(e) => {
            eprintln!("WARN: could not bootstrap persistent store {store_path:?}: {e} -- corpus will not survive a restart");
            (docs, None)
        }
    }
}

fn append_doc(store_path: &PathBuf, d: &Doc) -> std::io::Result<()> {
    let mut f = std::fs::OpenOptions::new().create(true).append(true).open(store_path)?;
    writeln!(f, "{}", serde_json::to_string(d).unwrap())
}

fn qparam(url: &str, key: &str) -> Option<String> {
    let q = url.split_once('?')?.1;
    for pair in q.split('&') {
        if let Some((k, v)) = pair.split_once('=') {
            if k == key {
                return Some(urldecode(v));
            }
        }
    }
    None
}
fn urldecode(s: &str) -> String {
    let s = s.replace('+', " ");
    let bytes = s.as_bytes();
    let mut out = Vec::new();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'%' && i + 2 < bytes.len() {
            if let Ok(b) = u8::from_str_radix(&s[i + 1..i + 3], 16) {
                out.push(b);
                i += 3;
                continue;
            }
        }
        out.push(bytes[i]);
        i += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}
fn sanitize(q: &str) -> String {
    q.chars()
        .map(|c| if c.is_alphanumeric() || c.is_whitespace() { c } else { ' ' })
        .collect()
}
fn floor_boundary(s: &str, mut i: usize) -> usize {
    if i >= s.len() {
        return s.len();
    }
    while i > 0 && !s.is_char_boundary(i) {
        i -= 1;
    }
    i
}
// window snippet with <b> term highlights (ASCII corpus; case-insensitive)
fn highlight(body: &str, query: &str) -> String {
    let terms: Vec<String> = query
        .to_lowercase()
        .split_whitespace()
        .filter(|w| w.len() >= 4)
        .map(str::to_string)
        .collect();
    if terms.is_empty() {
        return body.chars().take(200).collect();
    }
    let lower = body.to_lowercase();
    let pos = terms.iter().filter_map(|t| lower.find(t.as_str())).min().unwrap_or(0);
    let start = floor_boundary(body, pos.saturating_sub(60));
    let end = floor_boundary(body, (start + 240).min(body.len()));
    let window = &body[start..end];
    let wl = window.to_lowercase();
    let mut out = String::new();
    let mut i = 0;
    while i < window.len() {
        let mut matched = false;
        for t in &terms {
            if i + t.len() <= wl.len() && wl[i..].starts_with(t.as_str()) {
                out.push_str("<b>");
                out.push_str(&window[i..i + t.len()]);
                out.push_str("</b>");
                i += t.len();
                matched = true;
                break;
            }
        }
        if !matched {
            let ch_len = window[i..].chars().next().map(|c| c.len_utf8()).unwrap_or(1);
            out.push_str(&window[i..i + ch_len]);
            i += ch_len;
        }
    }
    format!("{}{}{}", if start > 0 { "…" } else { "" }, out, if end < body.len() { "…" } else { "" })
}

fn embed(agent: &ureq::Agent, url: &str, model: &str, text: &str) -> Option<Vec<f32>> {
    let mut resp = agent.post(url).send_json(json!({ "input": text, "model": model })).ok()?;
    let v: serde_json::Value = resp.body_mut().read_json().ok()?;
    let arr = v.get("data")?.get(0)?.get("embedding")?.as_array()?;
    Some(arr.iter().filter_map(|x| x.as_f64().map(|f| f as f32)).collect())
}

fn main() {
    // Install aws-lc-rs as the process-default rustls crypto provider (FIPS-capable; the non-FIPS
    // `ring` provider is not compiled in). ureq's rustls-no-provider TLS uses this default.
    let _ = rustls::crypto::aws_lc_rs::default_provider().install_default();

    let mut sb = Schema::builder();
    let f_id = sb.add_text_field("id", STRING | STORED);
    let f_idx = sb.add_u64_field("idx", STORED | FAST);
    let f_title = sb.add_text_field("title", TEXT | STORED);
    let f_body = sb.add_text_field("body", TEXT | STORED);
    let schema = sb.build();
    let index = Index::create_in_ram(schema);
    let mut writer: tantivy::IndexWriter = index.writer(50_000_000).unwrap();

    let corpus_path =
        std::env::var("SHERLOCK_CORPUS").unwrap_or_else(|_| "corpus/frontier-labs.json".into());
    let (mut docs, store_path) = load_docs(&corpus_path);
    let cap = corpus_cap();
    // Normally /ingest keeps the store at or under the cap; a store that already exceeds it (a
    // lowered cap, or docs added out of band) is loaded in full — dropping docs silently would be
    // worse than the memory it costs — but says so loudly so the over-budget condition is visible.
    if docs.len() > cap {
        eprintln!(
            "WARN: corpus has {} doc(s), over SHERLOCK_MAX_DOCS={} — the in-RAM index is over budget; \
             scale via the disk-backed index migration",
            docs.len(), cap
        );
    }
    for (i, d) in docs.iter().enumerate() {
        writer
            .add_document(doc!(
                f_id => d.id.clone(),
                f_idx => i as u64,
                f_title => d.title.clone(),
                f_body => d.body.clone()
            ))
            .unwrap();
    }
    writer.commit().unwrap();
    let reader = index.reader().unwrap();
    let qp = QueryParser::for_index(&index, vec![f_title, f_body]);

    // ── dense tier (optional): embed corpus → Qdrant (shared substrate) ─────────
    let agent: ureq::Agent = ureq::Agent::config_builder()
        .timeout_global(Some(Duration::from_secs(12)))
        .build()
        .into();
    let emb_url = std::env::var("EMBEDDINGS_URL").unwrap_or_default();
    let emb_model = std::env::var("EMBEDDINGS_MODEL").unwrap_or_else(|_| "nomic-embed-text".into());
    let qdrant_url = std::env::var("QDRANT_URL").unwrap_or_default().trim_end_matches('/').to_string();
    let coll = std::env::var("QDRANT_COLLECTION").unwrap_or_else(|_| "sherlock-corpus".into());
    let mut dense = false;
    if !emb_url.is_empty() && !qdrant_url.is_empty() {
        let mut vecs: Vec<(usize, Vec<f32>)> = Vec::new();
        let mut dim = 0usize;
        for (i, d) in docs.iter().enumerate() {
            if let Some(v) = embed(&agent, &emb_url, &emb_model, &format!("{}. {}", d.title, d.body)) {
                if dim == 0 {
                    dim = v.len();
                }
                if v.len() == dim {
                    vecs.push((i, v));
                }
            }
        }
        if !vecs.is_empty() {
            let _ = agent
                .put(&format!("{}/collections/{}", qdrant_url, coll))
                .send_json(json!({ "vectors": { "size": dim, "distance": "Cosine" } }));
            let points: Vec<serde_json::Value> = vecs
                .iter()
                .map(|(i, v)| json!({ "id": i, "vector": v, "payload": { "idx": i } }))
                .collect();
            if agent
                .put(&format!("{}/collections/{}/points?wait=true", qdrant_url, coll))
                .send_json(json!({ "points": points }))
                .is_ok()
            {
                dense = true;
                eprintln!("dense: embedded + upserted {} docs → qdrant '{}' (dim {})", vecs.len(), coll, dim);
            }
        }
        if !dense {
            eprintln!("dense disabled — embeddings/qdrant unreachable; BM25-only");
        }
    }

    // Takes docs explicitly rather than capturing it, so ingest (below) can mutably
    // borrow docs to push a new document without fighting a live capture of it here.
    let facet = |docs: &[Doc], key: &dyn Fn(&Doc) -> String| -> BTreeMap<String, usize> {
        let mut m: BTreeMap<String, usize> = BTreeMap::new();
        for d in docs {
            *m.entry(key(d)).or_insert(0) += 1;
        }
        m
    };

    let port = std::env::var("PORT").unwrap_or_else(|_| "8093".into());
    // Bind 0.0.0.0, not 127.0.0.1: in-cluster the kubelet liveness/readiness probe hits the POD IP,
    // so a localhost-only bind returns "connection refused" → failed liveness → SIGKILL (137) → CrashLoop
    // (385 restarts observed). 0.0.0.0 lets the probe on :8093/healthz reach the server.
    let server = tiny_http::Server::http(format!("0.0.0.0:{}", port)).unwrap();
    eprintln!("sherlock-engine on :{} — {} docs, mode={}", port, docs.len(), if dense { "hybrid (tantivy+qdrant/RRF)" } else { "tantivy BM25" });

    for mut request in server.incoming_requests() {
        let url = request.url().to_string();
        let path = url.split('?').next().unwrap_or("/").to_string();
        let method = request.method().clone();
        let body_str: String = if path == "/healthz" {
            json!({"ok": true, "service": "sherlock-engine", "engine": "tantivy", "dense": dense, "docs": docs.len(), "persistent": store_path.is_some()}).to_string()
        } else if path == "/facets" {
            json!({
                "doctype": serde_json::to_value(facet(&docs, &|d| d.doctype.clone())).unwrap(),
                "category": serde_json::to_value(facet(&docs, &|d| d.category.clone())).unwrap(),
                "region": serde_json::to_value(facet(&docs, &|d| d.region.clone())).unwrap()
            })
            .to_string()
        } else if path == "/ingest" && method == tiny_http::Method::Post {
            let mut raw_body = String::new();
            let read_ok = request.as_reader().read_to_string(&mut raw_body).is_ok();
            if !read_ok {
                json!({"ok": false, "error": "could not read request body"}).to_string()
            } else {
                match serde_json::from_str::<Doc>(&raw_body) {
                    Err(e) => json!({"ok": false, "error": format!("invalid document: {e}")}).to_string(),
                    // Bound the resident set: reject at capacity rather than grow the in-RAM index
                    // until the pod OOMs. Fail loud + stay up (the compute-gateway lesson), same
                    // {"ok": false} shape as the parse-error arm above so clients handle it uniformly.
                    Ok(_) if at_capacity(docs.len(), cap) => json!({
                        "ok": false,
                        "error": format!(
                            "corpus at capacity ({cap} docs, SHERLOCK_MAX_DOCS); the in-RAM index is \
                             bounded — migrate to the disk-backed index to grow further"
                        )
                    }).to_string(),
                    Ok(d) => {
                        let idx = docs.len();
                        // Persist first: if this fails, the doc must not become searchable
                        // and silently vanish on the next restart (fail closed, not quiet).
                        // Named doc_persisted, not persisted/persistent, to stay unambiguous
                        // next to /healthz's "persistent" (Copilot review on #1207): that one
                        // reports whether the persistence subsystem is configured and working
                        // at all; this one reports whether THIS document survived the write.
                        let doc_persisted = match &store_path {
                            Some(p) => match append_doc(p, &d) {
                                Ok(()) => true,
                                Err(e) => {
                                    eprintln!("WARN: ingest not persisted: {e}");
                                    false
                                }
                            },
                            None => false, // no SHERLOCK_DATA_DIR configured -- in-memory only, by design
                        };
                        writer
                            .add_document(doc!(
                                f_id => d.id.clone(),
                                f_idx => idx as u64,
                                f_title => d.title.clone(),
                                f_body => d.body.clone()
                            ))
                            .unwrap();
                        writer.commit().unwrap();
                        let _ = reader.reload();
                        docs.push(d);
                        json!({"ok": true, "idx": idx, "docs": docs.len(), "doc_persisted": doc_persisted}).to_string()
                    }
                }
            }
        } else if path == "/search" {
            let raw = qparam(&url, "q").unwrap_or_default();
            let q = sanitize(&raw);
            let limit: usize = qparam(&url, "limit").and_then(|s| s.parse().ok()).unwrap_or(10);
            if q.trim().is_empty() {
                json!({"query": raw, "hits": [], "total": 0}).to_string()
            } else {
                let searcher = reader.searcher();
                // lexical
                let mut bm25_ranked: Vec<usize> = Vec::new();
                let mut bm25_score: HashMap<usize, f32> = HashMap::new();
                if let Ok(query) = qp.parse_query(q.trim()) {
                    if let Ok(top) = searcher.search(&query, &TopDocs::with_limit(limit * 2)) {
                        for (score, addr) in top {
                            if let Ok(d) = searcher.doc::<TantivyDocument>(addr) {
                                if let Some(OwnedValue::U64(n)) = d.get_first(f_idx) {
                                    let idx = *n as usize;
                                    bm25_ranked.push(idx);
                                    bm25_score.insert(idx, score);
                                }
                            }
                        }
                    }
                }
                // dense
                let mut dense_ranked: Vec<usize> = Vec::new();
                let mut dense_score: HashMap<usize, f32> = HashMap::new();
                if dense {
                    if let Some(qv) = embed(&agent, &emb_url, &emb_model, q.trim()) {
                        if let Ok(mut resp) = agent
                            .post(&format!("{}/collections/{}/points/search", qdrant_url, coll))
                            .send_json(json!({ "vector": qv, "limit": limit * 2, "with_payload": false }))
                        {
                            if let Ok(jv) = resp.body_mut().read_json::<serde_json::Value>() {
                                if let Some(res) = jv.get("result").and_then(|r| r.as_array()) {
                                    for item in res {
                                        if let Some(id) = item.get("id").and_then(|x| x.as_u64()) {
                                            let idx = id as usize;
                                            dense_ranked.push(idx);
                                            if let Some(s) = item.get("score").and_then(|x| x.as_f64()) {
                                                dense_score.insert(idx, s as f32);
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                // RRF fusion (k=60)
                let mut rrf: HashMap<usize, f64> = HashMap::new();
                for (rank, idx) in bm25_ranked.iter().enumerate() {
                    *rrf.entry(*idx).or_insert(0.0) += 1.0 / (60.0 + rank as f64 + 1.0);
                }
                for (rank, idx) in dense_ranked.iter().enumerate() {
                    *rrf.entry(*idx).or_insert(0.0) += 1.0 / (60.0 + rank as f64 + 1.0);
                }
                let mut fused: Vec<(usize, f64)> = rrf.into_iter().collect();
                fused.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
                fused.truncate(limit);
                let hits: Vec<serde_json::Value> = fused
                    .iter()
                    .map(|(idx, rrfscore)| {
                        let d = &docs[*idx];
                        json!({
                            "id": d.id, "title": d.title, "doctype": d.doctype, "category": d.category,
                            "region": d.region, "score": d.score,
                            "bm25": bm25_score.get(idx), "dense": dense_score.get(idx), "rrf": rrfscore,
                            "snippet": highlight(&d.body, q.trim())
                        })
                    })
                    .collect();
                json!({"query": raw, "engine": if dense {"tantivy+qdrant(rrf)"} else {"tantivy"}, "total": hits.len(), "hits": hits}).to_string()
            }
        } else {
            json!({"error": "not found"}).to_string()
        };
        let mut resp = tiny_http::Response::from_string(body_str);
        resp.add_header(
            tiny_http::Header::from_bytes(&b"Content-Type"[..], &b"application/json"[..]).unwrap(),
        );
        resp.add_header(
            tiny_http::Header::from_bytes(&b"Access-Control-Allow-Origin"[..], &b"*"[..]).unwrap(),
        );
        let _ = request.respond(resp);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // The Rust-side equivalent of the boot-memory-invariance gate (INV-DEP-16): the resident set is
    // bounded because /ingest stops accepting at the cap, so the in-RAM index cannot grow without
    // limit. These pin the two pure seams the ingest guard is built on.

    #[test]
    fn at_capacity_rejects_only_once_full() {
        assert!(!at_capacity(0, 3)); // empty: accept
        assert!(!at_capacity(2, 3)); // room for one more: accept
        assert!(at_capacity(3, 3)); // exactly full: the next ingest is refused
        assert!(at_capacity(4, 3)); // over (e.g. cap lowered): still refused
    }

    #[test]
    fn parse_cap_defaults_on_absent_zero_or_garbage() {
        assert_eq!(parse_cap(None), DEFAULT_MAX_DOCS);
        assert_eq!(parse_cap(Some("0".into())), DEFAULT_MAX_DOCS); // a cap of 0 is meaningless
        assert_eq!(parse_cap(Some("not-a-number".into())), DEFAULT_MAX_DOCS);
        assert_eq!(parse_cap(Some("100".into())), 100);
    }
}
