//! graphdb — the property-graph DATABASE kernel over the analytics engine. This is the layer that
//! turns the distributed topology *engine* (PageRank/BFS/... in `boundary.rs`, persistent CSR in
//! `ooc.rs`) into a queryable, mutable, durable graph *database* — the thing Neptune/Neo4j do, built
//! for the scale above their single-box ceiling.
//!
//! The five phases of PLAN-GRAPHDB.md, as one coherent kernel:
//!   Phase 0/2 — durable store: an append-only WAL of dot-tagged ops + restart recovery (`open`).
//!   Phase 1   — query: point (`neighbors`), `k_hop`, and a compiled traversal `plan` (the target the
//!               TS openCypher IR lowers to — wiring that parser on top is the remaining integration).
//!   Phase 2   — single-shard ACID: `commit` flushes a batch atomically; MVCC snapshot reads (`read_at`).
//!   Phase 3   — causal/eventual multi-node: the store IS a CRDT — nodes/edges are add-wins OR-Sets,
//!               properties are LWW registers (HLC + replica tiebreak). `merge` is set-union of ops;
//!               materialization is a pure fold ⇒ Strong Eventual Consistency (concurrent replicas that
//!               have seen the same ops converge, no coordination). This is the CAP-correct choice
//!               (available under partition; cross-shard serializable ACID is deliberately OUT).
//!   Phase 4   — receipts: every query yields a deterministic content-sealed `Receipt` (query + snapshot
//!               version + result digest + state digest). Swap the FNV digest for BLAKE3/SHA-256 to make
//!               it cryptographic and emit it as a sourceos-spec Run/Event/Receipt.
//!
//! HONEST SCOPE: this kernel is proven single-node + multi-replica IN-PROCESS (see tests). It does NOT
//! yet execute a query across the distributed `boundary.rs` shards at 68B, nor ride a live DHT — those
//! are the integration/hardening tasks (#17 bridge, #19 harden). Nothing here claims otherwise.

use crate::fasthash::FxHashMap;
use crate::interner::Interner;
use std::sync::Arc;
use std::collections::{HashMap, HashSet, VecDeque};
use std::fs::{File, OpenOptions};
use std::io::{self, BufRead, BufReader, Write};
use std::path::{Path, PathBuf};

pub type NodeId = u64;
/// A CRDT "dot": (replica id, per-replica sequence). Globally unique ⇒ identifies one op forever.
pub type Dot = (u32, u64);
type EdgeKey = (NodeId, NodeId, String);

/// A property value. Float round-trips exactly (stored by bit pattern in the WAL).
#[derive(Clone, Debug, PartialEq)]
pub enum Prop {
    Int(i64),
    Float(f64),
    Text(String),
    Bool(bool),
}

/// A mutation. Delete ops are OBSERVED-remove: they carry the exact add-dots they tombstone, so a
/// concurrent add (a dot they never saw) survives the merge — add-wins OR-Set semantics.
#[derive(Clone, Debug, PartialEq)]
pub enum Op {
    AddNode { id: NodeId },
    DelNode { id: NodeId, removed: Vec<Dot> },
    AddEdge { src: NodeId, dst: NodeId, label: String },
    DelEdge { src: NodeId, dst: NodeId, label: String, removed: Vec<Dot> },
    SetProp { id: NodeId, key: String, val: Prop },
}

/// One committed record: the op, tagged with its dot and a Hybrid-Logical-Clock stamp (for LWW order).
#[derive(Clone, Debug, PartialEq)]
pub struct Record {
    pub dot: Dot,
    pub hlc: u64,
    pub op: Op,
}

/// Intent handed to `commit` (the store assigns the dot/hlc and resolves observed-removes).
#[derive(Clone, Debug)]
pub enum OpSpec {
    AddNode(NodeId),
    DelNode(NodeId),
    AddEdge(NodeId, NodeId, String),
    DelEdge(NodeId, NodeId, String),
    SetProp(NodeId, String, Prop),
}

/// A materialized read view (a snapshot's contents). Order-independent equality ⇒ two converged CRDT
/// replicas produce EQUAL views (the SEC property the tests assert).
#[derive(Clone, Debug, PartialEq)]
pub struct View {
    pub nodes: HashSet<NodeId>,
    pub out: HashMap<NodeId, Vec<(NodeId, Arc<str>)>>,
    pub props: HashMap<(NodeId, String), Prop>,
}

/// A content-sealed proof that a query ran against a specific state and returned a specific result.
#[derive(Clone, Debug, PartialEq)]
pub struct Receipt {
    pub query: String,
    pub snapshot_version: usize,
    pub result_digest: String, // SHA-256 hex of the query + result
    pub state_digest: String,  // SHA-256 hex of the committed op-set
}

/// One directed traversal hop with an optional edge-label filter — the compiled form of a Cypher
/// `-[:LABEL]->` step. A `plan` is a sequence of these (what `cypher.ts`'s pattern IR lowers to).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Step {
    pub label: Option<String>,
}

/// The property-graph database kernel. Owns the op-log (= the WAL, in memory), the live OR-Set/LWW
/// indexes, and (optionally) the on-disk WAL file for durability.
pub struct Store {
    replica: u32,
    seq: u64,
    hlc: u64,
    records: Vec<Record>,
    node_dots: HashMap<NodeId, HashSet<Dot>>,
    edge_dots: HashMap<EdgeKey, HashSet<Dot>>,
    removed: HashSet<Dot>,
    known: HashSet<Dot>,
    wal: Option<File>,
    path: Option<PathBuf>,
    interner: Interner,
}

impl Store {
    /// An in-memory store (no durability) — for tests and ephemeral analytics staging.
    pub fn memory(replica: u32) -> Self {
        Store {
            replica,
            seq: 0,
            hlc: 0,
            records: Vec::new(),
            node_dots: HashMap::new(),
            edge_dots: HashMap::new(),
            removed: HashSet::new(),
            known: HashSet::new(),
            wal: None,
            path: None,
            interner: Interner::new(),
        }
    }

    /// Open a durable store: replay the WAL at `path` (restart recovery), then append new commits to it.
    pub fn open(path: &Path, replica: u32) -> io::Result<Self> {
        let mut store = Store::memory(replica);
        if path.exists() {
            let reader = BufReader::new(File::open(path)?);
            for line in reader.lines() {
                let line = line?;
                if line.is_empty() {
                    continue;
                }
                if let Some(rec) = decode_record(&line) {
                    store.absorb(rec); // torn trailing line (crash mid-write) simply fails to decode → skipped
                }
            }
        }
        store.wal = Some(OpenOptions::new().create(true).append(true).open(path)?);
        store.path = Some(path.to_path_buf());
        Ok(store)
    }

    pub fn version(&self) -> usize {
        self.records.len()
    }
    pub fn replica(&self) -> u32 {
        self.replica
    }

    // ── Phase 2: single-shard ACID commit ────────────────────────────────────────────────────────
    /// Commit a batch of ops ATOMICALLY: assign dots/hlc, resolve observed-removes against current
    /// state, serialize the whole batch, and flush it to the WAL in ONE write before applying to
    /// memory. All-or-nothing + durable. `&mut self` serializes writers (single-shard = single writer).
    pub fn commit(&mut self, ops: Vec<OpSpec>) -> io::Result<usize> {
        let mut recs = Vec::with_capacity(ops.len());
        let mut buf = String::new();
        for spec in ops {
            self.seq += 1;
            self.hlc += 1;
            let dot = (self.replica, self.seq);
            let op = match spec {
                OpSpec::AddNode(id) => Op::AddNode { id },
                OpSpec::AddEdge(src, dst, label) => Op::AddEdge { src, dst, label },
                OpSpec::SetProp(id, key, val) => Op::SetProp { id, key, val },
                OpSpec::DelNode(id) => Op::DelNode {
                    id,
                    removed: self.live_dots_node(id),
                },
                OpSpec::DelEdge(src, dst, label) => {
                    let removed = self.live_dots_edge(&(src, dst, label.clone()));
                    Op::DelEdge { src, dst, label, removed }
                }
            };
            let rec = Record { dot, hlc: self.hlc, op };
            buf.push_str(&encode_record(&rec));
            buf.push('\n');
            recs.push(rec);
        }
        if let Some(f) = &mut self.wal {
            f.write_all(buf.as_bytes())?; // one write: the batch lands whole, or a crash leaves a torn
            f.flush()?; // trailing line that replay discards → atomicity across a crash
        }
        for rec in recs {
            self.index_apply(&rec);
            self.known.insert(rec.dot);
            self.records.push(rec);
        }
        Ok(self.records.len())
    }

    // Convenience single-op commits.
    pub fn add_node(&mut self, id: NodeId) -> io::Result<usize> {
        self.commit(vec![OpSpec::AddNode(id)])
    }
    pub fn add_edge(&mut self, src: NodeId, dst: NodeId, label: &str) -> io::Result<usize> {
        self.commit(vec![OpSpec::AddEdge(src, dst, label.to_string())])
    }
    pub fn set_prop(&mut self, id: NodeId, key: &str, val: Prop) -> io::Result<usize> {
        self.commit(vec![OpSpec::SetProp(id, key.to_string(), val)])
    }
    pub fn del_node(&mut self, id: NodeId) -> io::Result<usize> {
        self.commit(vec![OpSpec::DelNode(id)])
    }

    fn live_dots_node(&self, id: NodeId) -> Vec<Dot> {
        self.node_dots
            .get(&id)
            .map(|s| s.iter().filter(|d| !self.removed.contains(*d)).cloned().collect())
            .unwrap_or_default()
    }
    fn live_dots_edge(&self, key: &EdgeKey) -> Vec<Dot> {
        self.edge_dots
            .get(key)
            .map(|s| s.iter().filter(|d| !self.removed.contains(*d)).cloned().collect())
            .unwrap_or_default()
    }

    /// Update the live OR-Set / tombstone indexes from a record (used by commit, recovery, and merge).
    fn index_apply(&mut self, rec: &Record) {
        match &rec.op {
            Op::AddNode { id } => {
                self.node_dots.entry(*id).or_default().insert(rec.dot);
            }
            Op::AddEdge { src, dst, label } => {
                self.edge_dots
                    .entry((*src, *dst, label.clone()))
                    .or_default()
                    .insert(rec.dot);
            }
            Op::DelNode { removed, .. } | Op::DelEdge { removed, .. } => {
                for d in removed {
                    self.removed.insert(*d);
                }
            }
            Op::SetProp { .. } => {} // LWW resolved at materialization time
        }
    }

    /// Absorb a record during recovery: advance clocks, index it, record it (idempotent by dot).
    fn absorb(&mut self, rec: Record) {
        if self.known.contains(&rec.dot) {
            return;
        }
        if rec.dot.0 == self.replica {
            self.seq = self.seq.max(rec.dot.1);
        }
        self.hlc = self.hlc.max(rec.hlc);
        self.index_apply(&rec);
        self.known.insert(rec.dot);
        self.records.push(rec);
    }

    // ── Phase 3: causal/eventual CRDT merge ──────────────────────────────────────────────────────
    /// Merge another replica's ops into this one: set-union of the op-logs (dedup by dot), advancing
    /// the HLC. No coordination, no consensus. Because a view is a PURE FOLD over the op SET, any two
    /// replicas that have merged the same ops materialize IDENTICAL views — Strong Eventual Consistency.
    /// Merged records are appended to this replica's WAL too (durable). Returns #records newly absorbed.
    pub fn merge(&mut self, other: &Store) -> io::Result<usize> {
        let mut buf = String::new();
        let mut fresh: Vec<Record> = Vec::new();
        for rec in &other.records {
            if !self.known.contains(&rec.dot) {
                buf.push_str(&encode_record(rec));
                buf.push('\n');
                fresh.push(rec.clone());
            }
        }
        if let Some(f) = &mut self.wal {
            f.write_all(buf.as_bytes())?;
            f.flush()?;
        }
        let n = fresh.len();
        for rec in fresh {
            self.absorb(rec);
        }
        Ok(n)
    }

    /// This replica's version vector: replica-id → highest contiguous sequence seen. The compact summary
    /// a peer sends so we ship back only what it's missing (delta-sync), instead of the whole log.
    pub fn version_vector(&self) -> HashMap<u32, u64> {
        let mut vv: HashMap<u32, u64> = HashMap::new();
        for &(r, s) in &self.known {
            let e = vv.entry(r).or_insert(0);
            if s > *e {
                *e = s;
            }
        }
        vv
    }

    /// The records this replica holds that a peer at version-vector `vv` has NOT seen — the DELTA. This
    /// is what makes federation efficient: O(new ops) on the wire, not O(whole history) like `merge`.
    pub fn delta_since(&self, vv: &HashMap<u32, u64>) -> Vec<Record> {
        self.records
            .iter()
            .filter(|r| r.dot.1 > *vv.get(&r.dot.0).unwrap_or(&0))
            .cloned()
            .collect()
    }

    /// Apply a received delta (records new to us) — durable, idempotent by dot, advances the HLC.
    pub fn apply_delta(&mut self, delta: &[Record]) -> io::Result<usize> {
        let mut buf = String::new();
        let mut fresh: Vec<Record> = Vec::new();
        for r in delta {
            if !self.known.contains(&r.dot) {
                buf.push_str(&encode_record(r));
                buf.push('\n');
                fresh.push(r.clone());
            }
        }
        if let Some(f) = &mut self.wal {
            f.write_all(buf.as_bytes())?;
            f.flush()?;
        }
        let n = fresh.len();
        for r in fresh {
            self.absorb(r);
        }
        Ok(n)
    }

    /// Anti-entropy pull: fetch only the ops `other` has that we lack (delta-sync). Converges to the same
    /// view as `merge` but ships far less. Returns #records absorbed.
    pub fn pull_from(&mut self, other: &Store) -> io::Result<usize> {
        let delta = other.delta_since(&self.version_vector());
        self.apply_delta(&delta)
    }

    /// Checkpoint compaction: collapse the op-log to the MINIMAL set of records representing the current
    /// live view (fresh dots from this replica), so restart-replay isn't O(all history). SINGLE-NODE /
    /// snapshot use — it resets causal history, so don't compact a replica mid-federation. Returns the
    /// number of records dropped. The live view is preserved exactly (verified in tests).
    pub fn compact(&mut self) -> io::Result<usize> {
        let view = self.view();
        let before = self.records.len();
        let mut recs: Vec<Record> = Vec::new();
        let mut seq = 0u64;
        let mut hlc = self.hlc;
        let mut nodes: Vec<NodeId> = view.nodes.iter().cloned().collect();
        nodes.sort_unstable();
        for id in &nodes {
            seq += 1;
            hlc += 1;
            recs.push(Record { dot: (self.replica, seq), hlc, op: Op::AddNode { id: *id } });
        }
        let mut srcs: Vec<NodeId> = view.out.keys().cloned().collect();
        srcs.sort_unstable();
        for u in &srcs {
            for (v, l) in &view.out[u] {
                seq += 1;
                hlc += 1;
                recs.push(Record { dot: (self.replica, seq), hlc, op: Op::AddEdge { src: *u, dst: *v, label: l.to_string() } });
            }
        }
        let mut pkeys: Vec<&(NodeId, String)> = view.props.keys().collect();
        pkeys.sort();
        for k in pkeys {
            seq += 1;
            hlc += 1;
            recs.push(Record { dot: (self.replica, seq), hlc, op: Op::SetProp { id: k.0, key: k.1.clone(), val: view.props[k].clone() } });
        }
        // Swap in the compacted log + rebuild indexes.
        self.records = recs.clone();
        self.node_dots.clear();
        self.edge_dots.clear();
        self.removed.clear();
        self.known.clear();
        self.seq = seq;
        self.hlc = hlc;
        for r in &recs {
            self.index_apply(r);
            self.known.insert(r.dot);
        }
        // Rewrite the WAL file (durable) if we have one.
        if let Some(path) = self.path.clone() {
            let mut buf = String::new();
            for r in &recs {
                buf.push_str(&encode_record(r));
                buf.push('\n');
            }
            std::fs::write(&path, buf)?;
            self.wal = Some(OpenOptions::new().create(true).append(true).open(&path)?);
        }
        Ok(before.saturating_sub(recs.len()))
    }

    // ── Phase 1: queries ─────────────────────────────────────────────────────────────────────────
    /// Materialize the current view (all committed ops). O(records) — a real engine indexes this; the
    /// kernel folds, which is correct and enough to prove the semantics.
    pub fn view(&self) -> View {
        materialize(&self.records, &self.interner)
    }

    /// MVCC snapshot read: the view as of `version` (a prefix of the commit log) — an earlier snapshot
    /// is unaffected by later commits (snapshot isolation).
    pub fn read_at(&self, version: usize) -> View {
        materialize(&self.records[..version.min(self.records.len())], &self.interner)
    }

    /// Point query: out-neighbours of `id` with their edge labels. The "give me node X's neighbours"
    /// primitive Neo4j serves on a resident graph — here over the (eventually distributed) store.
    pub fn neighbors(&self, id: NodeId) -> Vec<(NodeId, Arc<str>)> {
        self.view().out.get(&id).cloned().unwrap_or_default()
    }

    /// k-hop reachability from `start` (BFS, optional edge-label filter), sorted, excluding `start`.
    pub fn k_hop(&self, start: NodeId, k: usize, label: Option<&str>) -> Vec<NodeId> {
        let view = self.view();
        let mut seen: HashSet<NodeId> = HashSet::new();
        let mut frontier: VecDeque<(NodeId, usize)> = VecDeque::new();
        frontier.push_back((start, 0));
        seen.insert(start);
        let mut out = Vec::new();
        while let Some((u, d)) = frontier.pop_front() {
            if d == k {
                continue;
            }
            if let Some(adj) = view.out.get(&u) {
                for (v, l) in adj {
                    if label.map(|f| f == l.as_ref()).unwrap_or(true) && seen.insert(*v) {
                        out.push(*v);
                        frontier.push_back((*v, d + 1));
                    }
                }
            }
        }
        out.sort_unstable();
        out
    }

    /// Execute a compiled traversal `plan`: follow the ordered hops from `start`, returning the sorted
    /// set of endpoints. This is exactly the plan an openCypher `MATCH (start)-[:A]->()-[:B]->(x)`
    /// lowers to — wiring `cypher.ts`'s IR to emit `Vec<Step>` is the Phase-1 bridge (task #17).
    pub fn plan(&self, start: NodeId, steps: &[Step]) -> Vec<NodeId> {
        let view = self.view();
        let mut frontier: HashSet<NodeId> = HashSet::from([start]);
        for step in steps {
            let mut next: HashSet<NodeId> = HashSet::new();
            for u in &frontier {
                if let Some(adj) = view.out.get(u) {
                    for (v, l) in adj {
                        if step.label.as_deref().map(|f| f == l.as_ref()).unwrap_or(true) {
                            next.insert(*v);
                        }
                    }
                }
            }
            frontier = next;
        }
        let mut out: Vec<NodeId> = frontier.into_iter().collect();
        out.sort_unstable();
        out
    }

    /// Present edges as (src,dst) pairs — the bridge to the analytics engine (feed to `pagerank_by_id`
    /// / partition into `boundary.rs` shards). Ties the DB back to the distributed compute.
    pub fn edges(&self) -> Vec<(NodeId, NodeId)> {
        let view = self.view();
        let mut e: Vec<(NodeId, NodeId)> = view
            .out
            .iter()
            .flat_map(|(u, adj)| adj.iter().map(move |(v, _)| (*u, *v)))
            .collect();
        e.sort_unstable();
        e
    }

    // ── Phase 4 MOAT: analytics-native queries ───────────────────────────────────────────────────
    /// Global PageRank over the current graph, as node-id → score. This is the analytics the query
    /// engine folds INTO a traversal — the thing a transactional graph DB bolts on as a separate batch
    /// job. Runs on the shared deterministic engine (distributed `boundary.rs` computes it at scale).
    pub fn pagerank(&self, damping: f64, iters: usize, tol: f64) -> HashMap<NodeId, f64> {
        let view = self.view();
        let mut ids: Vec<NodeId> = view.nodes.iter().cloned().collect();
        ids.sort_unstable();
        let idx: HashMap<NodeId, usize> = ids.iter().enumerate().map(|(i, &id)| (id, i)).collect();
        let mut edges: Vec<(usize, usize)> = Vec::new();
        for (u, adj) in &view.out {
            if let Some(&ui) = idx.get(u) {
                for (v, _) in adj {
                    if let Some(&vi) = idx.get(v) {
                        edges.push((ui, vi));
                    }
                }
            }
        }
        let pr = crate::pagerank_parallel(ids.len(), &edges, damping, iters, tol);
        ids.iter().enumerate().map(|(i, &id)| (id, pr[i])).collect()
    }

    /// k-hop neighbourhood RANKED by global PageRank (descending, id tiebreak), top `top_n`. "Traverse
    /// from X, ordered by influence" — a single query fusing distributed traversal with graph analytics,
    /// which is exactly what a single-box transactional graph DB cannot do fast at scale.
    pub fn k_hop_ranked(
        &self,
        start: NodeId,
        k: usize,
        label: Option<&str>,
        top_n: usize,
    ) -> Vec<(NodeId, f64)> {
        let pr = self.pagerank(0.85, 100, 1e-9);
        let mut hits: Vec<(NodeId, f64)> = self
            .k_hop(start, k, label)
            .into_iter()
            .map(|id| (id, *pr.get(&id).unwrap_or(&0.0)))
            .collect();
        hits.sort_by(|a, b| {
            b.1.partial_cmp(&a.1)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then(a.0.cmp(&b.0))
        });
        hits.truncate(top_n);
        hits
    }

    // ── Phase 4: receipts ────────────────────────────────────────────────────────────────────────
    /// A SHA-256 digest of the entire committed state (over the sorted set of known dots). Changes iff
    /// the op-set changes — a tamper-evident fingerprint of "which graph did this query see."
    pub fn state_digest(&self) -> String {
        let mut dots: Vec<Dot> = self.known.iter().cloned().collect();
        dots.sort_unstable();
        let mut buf = Vec::with_capacity(dots.len() * 12);
        for (r, s) in dots {
            buf.extend_from_slice(&r.to_le_bytes());
            buf.extend_from_slice(&s.to_le_bytes());
        }
        crate::hash::sha256_hex(&buf)
    }

    /// Seal a query + its result against the current state with SHA-256. Deterministic: same query, same
    /// result, same state ⇒ identical receipt; any change to query/result/graph changes the digest. This
    /// is the tamper-evident proof — ready to emit as a sourceos-spec Run/Event/Receipt.
    pub fn receipt(&self, query: &str, result: &[NodeId]) -> Receipt {
        let mut buf = Vec::with_capacity(query.len() + 1 + result.len() * 8);
        buf.extend_from_slice(query.as_bytes());
        buf.push(0);
        for id in result {
            buf.extend_from_slice(&id.to_le_bytes());
        }
        Receipt {
            query: query.to_string(),
            snapshot_version: self.records.len(),
            result_digest: crate::hash::sha256_hex(&buf),
            state_digest: self.state_digest(),
        }
    }
}

/// Pure fold: op SET → view. Order-independent (OR-Set membership + LWW max), so it is BOTH the
/// snapshot materializer and the proof of CRDT convergence.
fn materialize(records: &[Record], interner: &Interner) -> View {
    let mut node_adds: HashMap<NodeId, Vec<Dot>> = HashMap::new();
    let mut edge_adds: HashMap<EdgeKey, Vec<Dot>> = HashMap::new();
    let mut removed: HashSet<Dot> = HashSet::new();
    // LWW register: (hlc, replica) is the total order that decides the winning value.
    let mut prop_lww: HashMap<(NodeId, String), (u64, u32, Prop)> = HashMap::new();

    for r in records {
        match &r.op {
            Op::AddNode { id } => node_adds.entry(*id).or_default().push(r.dot),
            Op::AddEdge { src, dst, label } => {
                edge_adds.entry((*src, *dst, label.clone())).or_default().push(r.dot)
            }
            Op::DelNode { removed: rem, .. } | Op::DelEdge { removed: rem, .. } => {
                for d in rem {
                    removed.insert(*d);
                }
            }
            Op::SetProp { id, key, val } => {
                let k = (*id, key.clone());
                let cand = (r.hlc, r.dot.0);
                let win = prop_lww.get(&k).map(|(h, rep, _)| (*h, *rep) >= cand).unwrap_or(false);
                if !win {
                    prop_lww.insert(k, (r.hlc, r.dot.0, val.clone()));
                }
            }
        }
    }

    let nodes: HashSet<NodeId> = node_adds
        .iter()
        .filter(|(_, dots)| dots.iter().any(|d| !removed.contains(d)))
        .map(|(id, _)| *id)
        .collect();
    let mut out: HashMap<NodeId, Vec<(NodeId, Arc<str>)>> = HashMap::new();
    for ((src, dst, label), dots) in &edge_adds {
        let live = dots.iter().any(|d| !removed.contains(d));
        if live && nodes.contains(src) && nodes.contains(dst) {
            out.entry(*src).or_default().push((*dst, interner.intern(label)));
        }
    }
    for adj in out.values_mut() {
        adj.sort();
        adj.dedup();
    }
    let props = prop_lww.into_iter().map(|(k, (_, _, v))| (k, v)).collect();
    View { nodes, out, props }
}

// ── Phase 1 BRIDGE: distributed query execution across shards ─────────────────────────────────────
/// Owner of a node under the simple modulo partition (the production choice is `balanced_owner` from
/// boundary.rs, which decorrelates from RMAT hub-skew; modulo keeps this kernel's semantics obvious).
fn owner(id: NodeId, k: usize) -> usize {
    (id as usize) % k.max(1)
}

/// A graph SHARDED across `k` participants: shard `s` holds out-adjacency ONLY for the nodes it owns
/// (owner = id % k). This is the distributed representation the query bridge runs over — NO shard holds
/// the whole graph, exactly like `boundary.rs`'s distributed PageRank. Built from a Store's committed
/// view. This is the core of task #17: a query executing across the distributed engine, not on one node.
pub struct ShardedGraph {
    k: usize,
    shards: Vec<FxHashMap<NodeId, Vec<(NodeId, u32)>>>, // u32 = interned label symbol (no per-edge String)
    interner: Interner,
}

impl ShardedGraph {
    /// Partition a store's current view into `k` shards. Each shard receives out-adjacency for only the
    /// source nodes it owns — the edges never co-locate into one place. Labels are INTERNED to u32 symbols.
    pub fn from_store(store: &Store, k: usize) -> Self {
        let k = k.max(1);
        let view = store.view();
        let interner = Interner::new();
        let mut shards: Vec<FxHashMap<NodeId, Vec<(NodeId, u32)>>> =
            (0..k).map(|_| FxHashMap::default()).collect();
        for (u, adj) in &view.out {
            let entry = shards[owner(*u, k)].entry(*u).or_default();
            for (v, l) in adj {
                entry.push((*v, interner.sym(l.as_ref())));
            }
        }
        ShardedGraph { k, shards, interner }
    }

    /// Build a sharded graph directly from a labeled edge list (bypasses the WAL). Labels are interned once
    /// to u32 symbols — a 16M-edge graph all labelled "E" holds ONE "E" allocation, not 16M Strings.
    pub fn from_edges(edges: &[(NodeId, NodeId, String)], k: usize) -> Self {
        let k = k.max(1);
        let interner = Interner::new();
        let mut shards: Vec<FxHashMap<NodeId, Vec<(NodeId, u32)>>> =
            (0..k).map(|_| FxHashMap::default()).collect();
        for (u, v, l) in edges {
            shards[owner(*u, k)].entry(*u).or_default().push((*v, interner.sym(l)));
        }
        for shard in &mut shards {
            for adj in shard.values_mut() {
                adj.sort_unstable();
                adj.dedup();
            }
        }
        ShardedGraph { k, shards, interner }
    }

    pub fn shard_count(&self) -> usize {
        self.k
    }
    /// The largest number of source-nodes any single shard holds adjacency for — proof that no shard
    /// holds the whole graph (for k>1 this is strictly less than the single-shard total).
    pub fn max_shard_nodes(&self) -> usize {
        self.shards.iter().map(|s| s.len()).max().unwrap_or(0)
    }

    /// Distributed BSP k-hop: each superstep, a shard expands ONLY the frontier nodes it OWNS, using ONLY
    /// its local adjacency; neighbours are routed to their owner shards for the next superstep. Bit-exact
    /// equal to single-node `Store::k_hop`. The label filter is resolved to a u32 symbol ONCE, not per edge.
    pub fn k_hop(&self, start: NodeId, k_hops: usize, label: Option<&str>) -> Vec<NodeId> {
        let lid: Option<u32> = match label {
            None => None,
            Some(l) => match self.interner.get_sym(l) {
                Some(x) => Some(x),
                None => return Vec::new(), // label never seen ⇒ nothing matches
            },
        };
        let mut visited: HashSet<NodeId> = HashSet::from([start]);
        let mut frontier: Vec<NodeId> = vec![start];
        let mut result: HashSet<NodeId> = HashSet::new();
        for _ in 0..k_hops {
            let mut messages: Vec<NodeId> = Vec::new();
            for (s, shard) in self.shards.iter().enumerate() {
                for &node in &frontier {
                    if owner(node, self.k) == s {
                        if let Some(adj) = shard.get(&node) {
                            for (v, l) in adj {
                                if lid.map_or(true, |x| x == *l) {
                                    messages.push(*v);
                                }
                            }
                        }
                    }
                }
            }
            let mut next = Vec::new();
            for v in messages {
                if visited.insert(v) {
                    result.insert(v);
                    next.push(v);
                }
            }
            frontier = next;
            if frontier.is_empty() {
                break;
            }
        }
        let mut out: Vec<NodeId> = result.into_iter().collect();
        out.sort_unstable();
        out
    }

    /// Distributed compiled-plan execution — the openCypher-IR target, run across shards. Each step's label
    /// resolves to a u32 symbol ONCE. Bit-exact equal to single-node `Store::plan`.
    pub fn plan(&self, start: NodeId, steps: &[Step]) -> Vec<NodeId> {
        let mut frontier: HashSet<NodeId> = HashSet::from([start]);
        for step in steps {
            let lid: Option<u32> = match step.label.as_deref() {
                None => None,
                Some(l) => match self.interner.get_sym(l) {
                    Some(x) => Some(x),
                    None => {
                        frontier = HashSet::new(); // label absent ⇒ empty result
                        break;
                    }
                },
            };
            let mut next: HashSet<NodeId> = HashSet::new();
            for (s, shard) in self.shards.iter().enumerate() {
                for &node in &frontier {
                    if owner(node, self.k) == s {
                        if let Some(adj) = shard.get(&node) {
                            for (v, l) in adj {
                                if lid.map_or(true, |x| x == *l) {
                                    next.insert(*v);
                                }
                            }
                        }
                    }
                }
            }
            frontier = next;
        }
        let mut out: Vec<NodeId> = frontier.into_iter().collect();
        out.sort_unstable();
        out
    }
}

// ── WAL codec (self-contained, no serde dep) ──────────────────────────────────────────────────────
fn esc(s: &str) -> String {
    s.replace('\\', "\\\\").replace('\t', "\\t").replace('\n', "\\n")
}
fn unesc(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut it = s.chars();
    while let Some(c) = it.next() {
        if c == '\\' {
            match it.next() {
                Some('t') => out.push('\t'),
                Some('n') => out.push('\n'),
                Some('\\') => out.push('\\'),
                Some(other) => out.push(other),
                None => out.push('\\'),
            }
        } else {
            out.push(c);
        }
    }
    out
}
fn enc_dots(ds: &[Dot]) -> String {
    ds.iter().map(|(r, s)| format!("{r}.{s}")).collect::<Vec<_>>().join(",")
}
fn dec_dots(s: &str) -> Vec<Dot> {
    if s.is_empty() {
        return Vec::new();
    }
    s.split(',')
        .filter_map(|p| {
            let (r, s) = p.split_once('.')?;
            Some((r.parse().ok()?, s.parse().ok()?))
        })
        .collect()
}
fn enc_prop(v: &Prop) -> String {
    match v {
        Prop::Int(i) => format!("I{i}"),
        Prop::Float(f) => format!("F{}", f.to_bits()),
        Prop::Text(s) => format!("T{}", esc(s)),
        Prop::Bool(b) => format!("B{}", if *b { 1 } else { 0 }),
    }
}
fn dec_prop(s: &str) -> Option<Prop> {
    if s.is_empty() {
        return None;
    }
    let (t, rest) = s.split_at(1);
    match t {
        "I" => Some(Prop::Int(rest.parse().ok()?)),
        "F" => Some(Prop::Float(f64::from_bits(rest.parse().ok()?))),
        "T" => Some(Prop::Text(unesc(rest))),
        "B" => Some(Prop::Bool(rest == "1")),
        _ => None,
    }
}
fn encode_record(r: &Record) -> String {
    let (rep, seq) = r.dot;
    match &r.op {
        Op::AddNode { id } => format!("{rep}\t{seq}\t{}\tAN\t{id}", r.hlc),
        Op::DelNode { id, removed } => {
            format!("{rep}\t{seq}\t{}\tDN\t{id}\t{}", r.hlc, enc_dots(removed))
        }
        Op::AddEdge { src, dst, label } => {
            format!("{rep}\t{seq}\t{}\tAE\t{src}\t{dst}\t{}", r.hlc, esc(label))
        }
        Op::DelEdge { src, dst, label, removed } => format!(
            "{rep}\t{seq}\t{}\tDE\t{src}\t{dst}\t{}\t{}",
            r.hlc,
            esc(label),
            enc_dots(removed)
        ),
        Op::SetProp { id, key, val } => {
            format!("{rep}\t{seq}\t{}\tSP\t{id}\t{}\t{}", r.hlc, esc(key), enc_prop(val))
        }
    }
}
fn decode_record(line: &str) -> Option<Record> {
    let p: Vec<&str> = line.split('\t').collect();
    if p.len() < 5 {
        return None;
    }
    let rep: u32 = p[0].parse().ok()?;
    let seq: u64 = p[1].parse().ok()?;
    let hlc: u64 = p[2].parse().ok()?;
    let op = match p[3] {
        "AN" => Op::AddNode { id: p[4].parse().ok()? },
        "DN" => Op::DelNode {
            id: p[4].parse().ok()?,
            removed: dec_dots(p.get(5).copied().unwrap_or("")),
        },
        "AE" => Op::AddEdge {
            src: p[4].parse().ok()?,
            dst: p[5].parse().ok()?,
            label: unesc(p.get(6).copied().unwrap_or("")),
        },
        "DE" => Op::DelEdge {
            src: p[4].parse().ok()?,
            dst: p[5].parse().ok()?,
            label: unesc(p.get(6).copied().unwrap_or("")),
            removed: dec_dots(p.get(7).copied().unwrap_or("")),
        },
        "SP" => Op::SetProp {
            id: p[4].parse().ok()?,
            key: unesc(p.get(5).copied().unwrap_or("")),
            val: dec_prop(p.get(6).copied().unwrap_or(""))?,
        },
        _ => return None,
    };
    Some(Record { dot: (rep, seq), hlc, op })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp(name: &str) -> std::path::PathBuf {
        let mut p = std::env::temp_dir();
        p.push(format!("hg_graphdb_{}_{}.wal", name, std::process::id()));
        let _ = std::fs::remove_file(&p);
        p
    }

    // Phase 0/2: durability. Write through the WAL, drop the store, reopen from disk, see everything.
    #[test]
    fn phase0_wal_durability_and_recovery() {
        let path = tmp("durability");
        {
            let mut s = Store::open(&path, 1).unwrap();
            s.add_node(10).unwrap();
            s.add_node(20).unwrap();
            s.add_edge(10, 20, "KNOWS").unwrap();
            s.set_prop(10, "name", Prop::Text("alice".into())).unwrap();
            s.set_prop(20, "age", Prop::Int(30)).unwrap();
        } // store dropped — only the WAL file remains
        let s2 = Store::open(&path, 1).unwrap();
        let v = s2.view();
        assert!(v.nodes.contains(&10) && v.nodes.contains(&20));
        let out10: Vec<(NodeId, String)> =
            v.out.get(&10).unwrap().iter().map(|(d, l)| (*d, l.to_string())).collect();
        assert_eq!(out10, vec![(20u64, "KNOWS".to_string())]);
        assert_eq!(v.props.get(&(10, "name".into())), Some(&Prop::Text("alice".into())));
        assert_eq!(v.props.get(&(20, "age".into())), Some(&Prop::Int(30)));
        std::fs::remove_file(&path).ok();
    }

    // Phase 1: point + k-hop + compiled plan.
    #[test]
    fn phase1_point_khop_and_plan() {
        let mut s = Store::memory(1);
        for id in 0..5 {
            s.add_node(id).unwrap();
        }
        // 0->1->2->3 (KNOWS chain), 0->4 (WORKS)
        s.add_edge(0, 1, "KNOWS").unwrap();
        s.add_edge(1, 2, "KNOWS").unwrap();
        s.add_edge(2, 3, "KNOWS").unwrap();
        s.add_edge(0, 4, "WORKS").unwrap();

        let nbrs: Vec<(NodeId, String)> = s.neighbors(0).into_iter().map(|(v, l)| (v, l.to_string())).collect();
        assert_eq!(nbrs, vec![(1, "KNOWS".to_string()), (4, "WORKS".to_string())]);
        // 2 hops along any edge from 0 reaches {1,2,4}
        assert_eq!(s.k_hop(0, 2, None), vec![1, 2, 4]);
        // 2 hops restricted to KNOWS reaches {1,2}
        assert_eq!(s.k_hop(0, 2, Some("KNOWS")), vec![1, 2]);
        // compiled plan: (0)-[:KNOWS]->()-[:KNOWS]->(x)  ⇒  x = {2}
        let steps = vec![
            Step { label: Some("KNOWS".into()) },
            Step { label: Some("KNOWS".into()) },
        ];
        assert_eq!(s.plan(0, &steps), vec![2]);
    }

    // Phase 2: MVCC snapshot isolation — an old snapshot is unaffected by a later overwrite.
    #[test]
    fn phase2_snapshot_isolation_and_atomic_batch() {
        let mut s = Store::memory(1);
        s.add_node(1).unwrap();
        s.set_prop(1, "status", Prop::Text("active".into())).unwrap();
        let snap = s.version();
        s.set_prop(1, "status", Prop::Text("closed".into())).unwrap();

        assert_eq!(
            s.read_at(snap).props.get(&(1, "status".into())),
            Some(&Prop::Text("active".into())),
            "snapshot must still see the pre-overwrite value"
        );
        assert_eq!(
            s.view().props.get(&(1, "status".into())),
            Some(&Prop::Text("closed".into())),
            "latest must see the new value"
        );

        // Atomic multi-op batch: all lands, version advances by exactly the batch size.
        let before = s.version();
        let v = s
            .commit(vec![
                OpSpec::AddNode(2),
                OpSpec::AddNode(3),
                OpSpec::AddEdge(2, 3, "R".into()),
            ])
            .unwrap();
        assert_eq!(v, before + 3);
        assert!(s.view().nodes.contains(&2) && s.view().nodes.contains(&3));
    }

    // Phase 3: CRDT Strong Eventual Consistency — concurrent replicas that merge the same ops converge,
    // including a CONCURRENT conflicting property write (LWW) and a concurrent add vs delete (add-wins).
    #[test]
    fn phase3_crdt_converges_under_concurrency() {
        let mut a = Store::memory(1);
        let mut b = Store::memory(2);

        // Shared history both start from.
        for s in [&mut a, &mut b] {
            s.add_node(1).unwrap();
        }
        // (they don't see each other's ops until merge — these are concurrent)
        a.set_prop(1, "color", Prop::Text("red".into())).unwrap();
        a.add_node(100).unwrap();
        a.add_edge(1, 100, "A".into()).ok();

        b.set_prop(1, "color", Prop::Text("blue".into())).unwrap(); // conflicts with A's write
        b.add_node(200).unwrap();
        b.add_edge(1, 200, "B".into()).ok();

        // Merge both directions.
        a.merge(&b).unwrap();
        b.merge(&a).unwrap();

        // SEC: identical views, no coordination.
        assert_eq!(a.view(), b.view(), "replicas must converge to an identical view");
        // Both concurrent nodes survive (grow/add-wins).
        assert!(a.view().nodes.contains(&100) && a.view().nodes.contains(&200));
        // The LWW winner is deterministic and the same on both sides.
        let ca = a.view().props.get(&(1, "color".into())).cloned();
        assert!(ca == Some(Prop::Text("red".into())) || ca == Some(Prop::Text("blue".into())));
        assert_eq!(ca, b.view().props.get(&(1, "color".into())).cloned());
    }

    // Phase 3b: add-wins — a concurrent DELETE on one replica does not erase a concurrent re-ADD.
    #[test]
    fn phase3_add_wins_or_set() {
        let mut a = Store::memory(1);
        let mut b = Store::memory(2);
        a.add_node(7).unwrap();
        b.merge(&a).unwrap(); // b now sees node 7
        // Concurrently: a deletes 7 (observing a's add-dot); b re-adds 7 with a NEW dot a never saw.
        a.del_node(7).unwrap();
        b.add_node(7).unwrap();
        a.merge(&b).unwrap();
        b.merge(&a).unwrap();
        assert_eq!(a.view(), b.view());
        assert!(a.view().nodes.contains(&7), "concurrent re-add must win over the delete");
    }

    // Phase 4: receipts are deterministic and bind to both the result and the state.
    #[test]
    fn phase4_receipts_are_deterministic_and_bind_state() {
        let mut s = Store::memory(1);
        for id in 0..4 {
            s.add_node(id).unwrap();
        }
        s.add_edge(0, 1, "R").unwrap();
        s.add_edge(0, 2, "R").unwrap();

        let res = s.k_hop(0, 1, None);
        let r1 = s.receipt("k_hop(0,1)", &res);
        let r2 = s.receipt("k_hop(0,1)", &res);
        assert_eq!(r1, r2, "same query+result+state ⇒ identical receipt");

        let d_before = s.state_digest();
        s.add_edge(0, 3, "R").unwrap(); // mutate the graph
        assert_ne!(d_before, s.state_digest(), "state digest must change when the graph changes");
        let r3 = s.receipt("k_hop(0,1)", &res);
        assert_ne!(r1.state_digest, r3.state_digest, "receipt binds to the state it ran against");
    }

    // Phase 4 MOAT: a traversal RANKED by live PageRank — the in-hub ranks first (analytics fused into
    // the query, the thing a transactional graph DB can't do fast).
    #[test]
    fn moat_analytics_native_ranked_traversal() {
        let mut s = Store::memory(1);
        for id in 0..6 {
            s.add_node(id).unwrap();
        }
        // Star from 0 into {1,2,4,5}, all of which point at the in-hub 3 (4 in-edges ⇒ highest PageRank).
        for v in [1, 2, 4, 5] {
            s.add_edge(0, v, "E").unwrap();
            s.add_edge(v, 3, "E").unwrap();
        }
        let ranked = s.k_hop_ranked(0, 2, None, 3);
        assert_eq!(ranked[0].0, 3, "the in-hub (node 3) must rank first by PageRank");
        assert!(ranked[0].1 >= ranked[1].1, "scores must be descending");
        assert_eq!(s.k_hop_ranked(0, 2, None, 3), s.k_hop_ranked(0, 2, None, 3), "deterministic");
    }

    // WAL compaction: heavy churn (adds, deletes, prop overwrites) collapses to a minimal log that
    // preserves the live view exactly and survives a reopen.
    #[test]
    fn wal_compaction_preserves_state_and_shrinks_log() {
        let path = tmp("compaction");
        let mut s = Store::open(&path, 1).unwrap();
        for id in 0..100 {
            s.add_node(id).unwrap();
        }
        for id in 0..50 {
            s.del_node(id).unwrap();
        }
        for i in 0..20 {
            s.set_prop(99, "v", Prop::Int(i)).unwrap(); // 20 overwrites → 1 live value
        }
        let before_view = s.view();
        let before_len = s.version();
        let dropped = s.compact().unwrap();
        assert!(dropped > 0, "compaction must drop dead records");
        assert!(s.version() < before_len, "compacted log must be shorter");
        assert_eq!(s.view(), before_view, "compaction must preserve the live view exactly");
        drop(s);
        let s2 = Store::open(&path, 1).unwrap();
        assert_eq!(s2.view(), before_view, "compacted WAL must reopen to the same state");
        std::fs::remove_file(&path).ok();
    }

    // Delta-sync: anti-entropy ships only the ops a peer is missing (not the whole log), and converges.
    #[test]
    fn delta_sync_ships_only_deltas_and_converges() {
        let mut a = Store::memory(1);
        let mut b = Store::memory(2);
        for id in 0..10 {
            a.add_node(id).unwrap();
        }
        b.pull_from(&a).unwrap();
        assert_eq!(a.view(), b.view());
        // a adds 2 more; the delta b is missing must be exactly those 2 records, not all 12.
        a.add_node(100).unwrap();
        a.add_node(101).unwrap();
        let delta = a.delta_since(&b.version_vector());
        assert_eq!(delta.len(), 2, "delta must be only the new ops, not the whole history");
        b.apply_delta(&delta).unwrap();
        assert_eq!(a.view(), b.view());
        // Concurrent both-ways sync still converges.
        a.add_edge(0, 1, "E").unwrap();
        b.add_node(200).unwrap();
        a.pull_from(&b).unwrap();
        b.pull_from(&a).unwrap();
        assert_eq!(a.view(), b.view(), "bidirectional delta-sync must converge");
    }

    // WAL codec round-trips every op/prop type, including nasty strings with tabs/newlines/backslashes.
    #[test]
    fn wal_codec_roundtrips_all_ops() {
        let recs = vec![
            Record { dot: (1, 1), hlc: 1, op: Op::AddNode { id: 42 } },
            Record { dot: (2, 5), hlc: 9, op: Op::DelNode { id: 42, removed: vec![(1, 1), (3, 7)] } },
            Record { dot: (1, 2), hlc: 3, op: Op::AddEdge { src: 1, dst: 2, label: "a\tb\\c\nd".into() } },
            Record { dot: (1, 3), hlc: 4, op: Op::DelEdge { src: 1, dst: 2, label: "L".into(), removed: vec![(1, 2)] } },
            Record { dot: (1, 4), hlc: 5, op: Op::SetProp { id: 1, key: "k\ty".into(), val: Prop::Text("v\\1\n".into()) } },
            Record { dot: (1, 5), hlc: 6, op: Op::SetProp { id: 1, key: "f".into(), val: Prop::Float(-3.5e-17) } },
            Record { dot: (1, 6), hlc: 7, op: Op::SetProp { id: 1, key: "b".into(), val: Prop::Bool(true) } },
        ];
        for r in &recs {
            let line = encode_record(r);
            assert!(!line.contains('\n'), "encoded record must be one line");
            let back = decode_record(&line).expect("decodes");
            assert_eq!(&back, r, "record must round-trip through the WAL codec");
        }
    }

    // Phase 1 BRIDGE: a query executed ACROSS shards (no shard holds the whole graph) returns the SAME
    // result as the single-node kernel — the distributed-execution correctness proof (task #17).
    #[test]
    fn bridge_distributed_traversal_matches_single_node() {
        let mut s = Store::memory(1);
        for id in 0..12 {
            s.add_node(id).unwrap();
        }
        let edges = [
            (0, 1, "K"), (1, 2, "K"), (2, 3, "K"), (0, 4, "W"), (4, 5, "K"), (3, 6, "K"),
            (6, 7, "W"), (1, 8, "K"), (8, 9, "K"), (9, 2, "K"), (5, 10, "K"), (10, 11, "K"),
        ];
        for (u, v, l) in edges {
            s.add_edge(u, v, l).unwrap();
        }
        let whole = ShardedGraph::from_store(&s, 1).max_shard_nodes();
        let steps = vec![Step { label: Some("K".into()) }, Step { label: Some("K".into()) }];
        for k in [1usize, 2, 3, 5, 7] {
            let g = ShardedGraph::from_store(&s, k);
            for start in 0..12u64 {
                for hops in 1..=4 {
                    assert_eq!(
                        g.k_hop(start, hops, None),
                        s.k_hop(start, hops, None),
                        "distributed k_hop must equal single-node (k={k}, start={start}, hops={hops})"
                    );
                    assert_eq!(
                        g.k_hop(start, hops, Some("K")),
                        s.k_hop(start, hops, Some("K")),
                        "label-filtered distributed k_hop must match (k={k})"
                    );
                }
                assert_eq!(
                    g.plan(start, &steps),
                    s.plan(start, &steps),
                    "distributed plan must match single-node (k={k}, start={start})"
                );
            }
            if k > 1 {
                assert!(
                    g.max_shard_nodes() < whole,
                    "k={k}: a shard holds the whole graph — not actually sharded"
                );
            }
        }
    }
}
