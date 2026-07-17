//! cypher — a real (bounded) openCypher parser in Rust: `MATCH` path patterns → a compiled `Query` the
//! graphdb engine executes, single-node OR across shards. This closes "the Cypher parser only lives in
//! TS": now graph query TEXT drives the distributed engine directly.
//!
//! Supported grammar (a real, useful subset — not all of Cypher):
//!   MATCH (a {id: N})-[:LABEL]->(b)-[:LABEL2]->(c) RETURN c          -- fixed-length path
//!   MATCH (a)-[:LABEL*1..3]->(b) WHERE a = N RETURN b                -- variable-length ⇒ k-hop
//! The start node is bound by an inline `{id: N}` or a `WHERE var = N`. Relationships are outgoing
//! `-[:L]->`. Everything compiles to `Query`, run by `Query::run` (single-node) / `Query::run_dist`.

use crate::graphdb::{NodeId, ShardedGraph, Step, Store};

/// A compiled query. `Fixed` = an exact-length pattern (→ `plan`); `VarHop` = variable-length (→ `k_hop`).
#[derive(Debug, Clone, PartialEq)]
pub enum Query {
    Fixed { start: NodeId, steps: Vec<Step>, ret: String },
    VarHop { start: NodeId, label: Option<String>, min: usize, max: usize, ret: String },
}

impl Query {
    pub fn start(&self) -> NodeId {
        match self {
            Query::Fixed { start, .. } | Query::VarHop { start, .. } => *start,
        }
    }
    pub fn ret(&self) -> &str {
        match self {
            Query::Fixed { ret, .. } | Query::VarHop { ret, .. } => ret,
        }
    }
    /// Execute against a single-node store.
    pub fn run(&self, s: &Store) -> Vec<NodeId> {
        match self {
            Query::Fixed { start, steps, .. } => s.plan(*start, steps),
            Query::VarHop { start, label, max, .. } => s.k_hop(*start, *max, label.as_deref()),
        }
    }
    /// Execute across the distributed sharded engine — same result, no node holds the whole graph.
    pub fn run_dist(&self, g: &ShardedGraph) -> Vec<NodeId> {
        match self {
            Query::Fixed { start, steps, .. } => g.plan(*start, steps),
            Query::VarHop { start, label, max, .. } => g.k_hop(*start, *max, label.as_deref()),
        }
    }

    /// Execute against any ingest-prepared index (owned `GraphIndex` or mmap-backed `MmapGraphIndex`) — the
    /// fast read path (dense CSR, labelled sub-slices).
    pub fn run_index<G: crate::index::GraphCore>(&self, idx: &G) -> Vec<NodeId> {
        match self {
            Query::Fixed { start, steps, .. } => idx.plan(*start, steps),
            Query::VarHop { start, label, max, .. } => idx.k_hop(*start, *max, label.as_deref()),
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
enum Tok {
    LParen,
    RParen,
    LBrace,
    RBrace,
    LBrack,
    RBrack,
    Colon,
    Dot,
    DotDot,
    Comma,
    Eq,
    Star,
    Dash,
    Gt,
    Lt,
    Ident(String),
    Num(u64),
    Kw(String), // match / return / where (lowercased)
}

fn tokenize(src: &str) -> Result<Vec<Tok>, String> {
    let ch: Vec<char> = src.chars().collect();
    let mut i = 0;
    let mut out = Vec::new();
    while i < ch.len() {
        let c = ch[i];
        match c {
            c if c.is_whitespace() => i += 1,
            '(' => { out.push(Tok::LParen); i += 1; }
            ')' => { out.push(Tok::RParen); i += 1; }
            '{' => { out.push(Tok::LBrace); i += 1; }
            '}' => { out.push(Tok::RBrace); i += 1; }
            '[' => { out.push(Tok::LBrack); i += 1; }
            ']' => { out.push(Tok::RBrack); i += 1; }
            ':' => { out.push(Tok::Colon); i += 1; }
            ',' => { out.push(Tok::Comma); i += 1; }
            '=' => { out.push(Tok::Eq); i += 1; }
            '*' => { out.push(Tok::Star); i += 1; }
            '-' => { out.push(Tok::Dash); i += 1; }
            '>' => { out.push(Tok::Gt); i += 1; }
            '<' => { out.push(Tok::Lt); i += 1; }
            '.' => {
                if i + 1 < ch.len() && ch[i + 1] == '.' {
                    out.push(Tok::DotDot);
                    i += 2;
                } else {
                    out.push(Tok::Dot);
                    i += 1;
                }
            }
            c if c.is_ascii_digit() => {
                let start = i;
                while i < ch.len() && ch[i].is_ascii_digit() {
                    i += 1;
                }
                let s: String = ch[start..i].iter().collect();
                out.push(Tok::Num(s.parse().map_err(|_| format!("bad number: {s}"))?));
            }
            c if c.is_alphabetic() || c == '_' => {
                let start = i;
                while i < ch.len() && (ch[i].is_alphanumeric() || ch[i] == '_') {
                    i += 1;
                }
                let s: String = ch[start..i].iter().collect();
                let low = s.to_lowercase();
                if matches!(low.as_str(), "match" | "return" | "where") {
                    out.push(Tok::Kw(low));
                } else {
                    out.push(Tok::Ident(s));
                }
            }
            other => return Err(format!("unexpected character: {other:?}")),
        }
    }
    Ok(out)
}

struct Parser {
    t: Vec<Tok>,
    p: usize,
}
impl Parser {
    fn peek(&self) -> Option<&Tok> {
        self.t.get(self.p)
    }
    fn next(&mut self) -> Option<Tok> {
        let t = self.t.get(self.p).cloned();
        self.p += 1;
        t
    }
    fn expect(&mut self, want: &Tok) -> Result<(), String> {
        match self.next() {
            Some(ref t) if t == want => Ok(()),
            other => Err(format!("expected {want:?}, found {other:?}")),
        }
    }
    fn ident(&mut self) -> Result<String, String> {
        match self.next() {
            Some(Tok::Ident(s)) => Ok(s),
            other => Err(format!("expected identifier, found {other:?}")),
        }
    }
    fn num(&mut self) -> Result<u64, String> {
        match self.next() {
            Some(Tok::Num(n)) => Ok(n),
            other => Err(format!("expected number, found {other:?}")),
        }
    }
    fn is_kw(&self, k: &str) -> bool {
        matches!(self.peek(), Some(Tok::Kw(w)) if w == k)
    }

    // (var [{ id: N }])  — `var` may be omitted for an anonymous node `()`
    fn node(&mut self) -> Result<(String, Option<u64>), String> {
        self.expect(&Tok::LParen)?;
        let var = if matches!(self.peek(), Some(Tok::Ident(_))) {
            self.ident()?
        } else {
            String::new()
        };
        let mut id = None;
        if matches!(self.peek(), Some(Tok::LBrace)) {
            self.next();
            let key = self.ident()?;
            self.expect(&Tok::Colon)?;
            let n = self.num()?;
            self.expect(&Tok::RBrace)?;
            if key == "id" {
                id = Some(n);
            } else {
                return Err(format!("only {{id: N}} is supported, got {{{key}: ...}}"));
            }
        }
        self.expect(&Tok::RParen)?;
        Ok((var, id))
    }

    // -[:LABEL [*min..max]]->
    fn rel(&mut self) -> Result<(Option<String>, Option<(usize, usize)>), String> {
        self.expect(&Tok::Dash)?;
        self.expect(&Tok::LBrack)?;
        self.expect(&Tok::Colon)?;
        let label = self.ident()?;
        let mut varlen = None;
        if matches!(self.peek(), Some(Tok::Star)) {
            self.next();
            let min = self.num()? as usize;
            self.expect(&Tok::DotDot)?;
            let max = self.num()? as usize;
            varlen = Some((min, max));
        }
        self.expect(&Tok::RBrack)?;
        self.expect(&Tok::Dash)?;
        self.expect(&Tok::Gt)?;
        Ok((Some(label), varlen))
    }
}

/// Parse a Cypher query string into a compiled `Query`.
pub fn parse(src: &str) -> Result<Query, String> {
    let mut ps = Parser { t: tokenize(src)?, p: 0 };
    if !ps.is_kw("match") {
        return Err("query must start with MATCH".into());
    }
    ps.next();

    let (v0, id0) = ps.node()?;
    let mut hops: Vec<(Option<String>, Option<(usize, usize)>)> = Vec::new();
    let mut last_var = v0.clone();
    while matches!(ps.peek(), Some(Tok::Dash)) {
        let rel = ps.rel()?;
        let (v, _id) = ps.node()?;
        hops.push(rel);
        last_var = v;
    }
    if hops.is_empty() {
        return Err("query needs at least one relationship, e.g. (a)-[:L]->(b)".into());
    }

    // Bind the start id: inline {id:N} on the first node, or WHERE v0 = N.
    let mut start_id = id0;
    if ps.is_kw("where") {
        ps.next();
        let var = ps.ident()?;
        if matches!(ps.peek(), Some(Tok::Dot)) {
            self_skip_prop(&mut ps)?; // WHERE a.id = N  → skip `.id`
        }
        ps.expect(&Tok::Eq)?;
        let n = ps.num()?;
        if var == v0 {
            start_id = Some(n);
        } else {
            return Err(format!("WHERE binds `{var}`, but the start node is `{v0}`"));
        }
    }

    let mut ret = last_var.clone();
    if ps.is_kw("return") {
        ps.next();
        ret = ps.ident()?;
    }
    if ps.peek().is_some() {
        return Err(format!("unexpected trailing tokens after the query: {:?}", ps.peek()));
    }

    let start = start_id.ok_or_else(|| {
        "no start id bound — use MATCH (a {id: N})-... or a WHERE a = N clause".to_string()
    })?;

    if hops.iter().any(|(_, vl)| vl.is_some()) {
        if hops.len() != 1 {
            return Err("variable-length (*min..max) is supported for a single relationship only".into());
        }
        let (label, vl) = hops[0].clone();
        let (min, max) = vl.unwrap();
        if min == 0 || min > max {
            return Err(format!("bad variable-length bounds *{min}..{max}"));
        }
        Ok(Query::VarHop { start, label, min, max, ret })
    } else {
        let steps = hops.into_iter().map(|(label, _)| Step { label }).collect();
        Ok(Query::Fixed { start, steps, ret })
    }
}

// WHERE a.id = N : consume the `.id` property access (we only key on node id).
fn self_skip_prop(ps: &mut Parser) -> Result<(), String> {
    ps.expect(&Tok::Dot)?;
    let prop = ps.ident()?;
    if prop != "id" {
        return Err(format!("WHERE supports only `.id`, got `.{prop}`"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::graphdb::ShardedGraph;

    fn sample() -> Store {
        let mut s = Store::memory(1);
        for id in 0..6 {
            s.add_node(id).unwrap();
        }
        s.add_edge(0, 1, "KNOWS").unwrap();
        s.add_edge(1, 2, "KNOWS").unwrap();
        s.add_edge(2, 3, "KNOWS").unwrap();
        s.add_edge(0, 4, "WORKS").unwrap();
        s.add_edge(4, 5, "KNOWS").unwrap();
        s
    }

    #[test]
    fn parses_fixed_path_inline_id() {
        let q = parse("MATCH (a {id: 0})-[:KNOWS]->(b)-[:KNOWS]->(c) RETURN c").unwrap();
        assert_eq!(
            q,
            Query::Fixed {
                start: 0,
                steps: vec![
                    Step { label: Some("KNOWS".into()) },
                    Step { label: Some("KNOWS".into()) }
                ],
                ret: "c".into()
            }
        );
    }

    #[test]
    fn parses_varhop_with_where() {
        let q = parse("MATCH (a)-[:KNOWS*1..3]->(b) WHERE a = 0 RETURN b").unwrap();
        assert_eq!(
            q,
            Query::VarHop { start: 0, label: Some("KNOWS".into()), min: 1, max: 3, ret: "b".into() }
        );
    }

    #[test]
    fn where_dot_id_form() {
        let q = parse("MATCH (a)-[:KNOWS]->(b) WHERE a.id = 2 RETURN b").unwrap();
        assert_eq!(q.start(), 2);
    }

    #[test]
    fn execution_matches_engine_single_and_distributed() {
        let s = sample();
        // fixed 2-hop KNOWS from 0 ⇒ {2}
        let q = parse("MATCH (a {id: 0})-[:KNOWS]->()-[:KNOWS]->(c) RETURN c").unwrap();
        assert_eq!(q.run(&s), vec![2]);
        // varhop up to 3 KNOWS hops from 0 ⇒ {1,2,3}
        let q2 = parse("MATCH (a)-[:KNOWS*1..3]->(b) WHERE a = 0 RETURN b").unwrap();
        assert_eq!(q2.run(&s), vec![1, 2, 3]);
        // distributed execution equals single-node for both, at several shard counts
        for k in [1usize, 2, 3, 5] {
            let g = ShardedGraph::from_store(&s, k);
            assert_eq!(q.run_dist(&g), q.run(&s), "fixed dist==single (k={k})");
            assert_eq!(q2.run_dist(&g), q2.run(&s), "varhop dist==single (k={k})");
        }
    }

    #[test]
    fn parse_errors_are_friendly() {
        assert!(parse("SELECT * FROM x").is_err(), "non-MATCH must error");
        let e = parse("MATCH (a)-[:L]->(b)").unwrap_err();
        assert!(e.contains("no start id"), "unbound start must say so, got: {e}");
    }
}
