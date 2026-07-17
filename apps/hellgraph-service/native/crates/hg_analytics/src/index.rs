//! index — the ingest-prepared, read-optimized graph index. The op-log Store is WRITE-optimized (append a
//! WAL, materialize by folding). This is the READ side: at ingest we DICTIONARY-ENCODE node ids into a
//! dense, sorted, contiguous integer space (ordered integers — not a hashmap of random u64s), build CSR
//! adjacency BOTH directions with neighbours sorted, sub-slice each row by label via binary search, and
//! build secondary property indexes. Queries then run O(degree)/O(log degree), not O(op-log).
//!
//! The query logic lives ONCE, in the `GraphCore` trait — shared by the owned [`GraphIndex`] and the
//! zero-copy mmap-backed [`MmapGraphIndex`], so nothing is implemented twice. Degrees are DERIVED from the
//! CSR offsets (off[d+1]-off[d]) rather than stored — no redundant array.

use crate::fasthash::{FxHashMap, FxHashSet};
use crate::graphdb::{NodeId, Prop, Step, Store};
use memmap2::Mmap;
use rayon::prelude::*;
use std::fs::File;
use std::io;
use std::path::Path;

const MAGIC: u64 = 0x4847_4458_4d4d_4150; // "HGDXMMAP"

/// Hashable/orderable encoding of a property value for the equality index (Float keyed by bit pattern).
#[derive(Clone, PartialEq, Eq, Hash)]
pub enum PropKey {
    Int(i64),
    Float(u64),
    Text(String),
    Bool(bool),
}
impl PropKey {
    fn of(p: &Prop) -> Self {
        match p {
            Prop::Int(i) => PropKey::Int(*i),
            Prop::Float(f) => PropKey::Float(f.to_bits()),
            Prop::Text(s) => PropKey::Text(s.clone()),
            Prop::Bool(b) => PropKey::Bool(*b),
        }
    }
}

/// A sub-slice of `nbr` for one CSR row `[s,e)`, optionally filtered to an already-resolved label id. The
/// row is sorted by (label, endpoint), so a labelled lookup is a binary-search sub-slice — and NO string
/// work happens here (the label→id resolution is done ONCE per query, not per row).
fn slice_by_lid<'a>(nbr: &'a [u32], lbl: &[u32], s: usize, e: usize, lid: Option<u32>) -> &'a [u32] {
    match lid {
        None => &nbr[s..e],
        Some(lid) => {
            let row = &lbl[s..e];
            let lo = s + row.partition_point(|&x| x < lid);
            let hi = s + row.partition_point(|&x| x <= lid);
            &nbr[lo..hi]
        }
    }
}

/// The shared read/traversal surface over a dense-CSR graph. Implement the accessors (returning slices into
/// owned Vecs or an mmap); every query method is a provided default, so it is written exactly ONCE.
pub trait GraphCore: Sync {
    fn ids(&self) -> &[NodeId];
    fn labels(&self) -> &[String];
    fn out_off(&self) -> &[u32];
    fn out_nbr(&self) -> &[u32];
    fn out_lbl(&self) -> &[u32];
    fn in_off(&self) -> &[u32];
    fn in_nbr(&self) -> &[u32];
    fn in_lbl(&self) -> &[u32];

    fn node_count(&self) -> usize {
        self.ids().len()
    }
    fn edge_count(&self) -> usize {
        self.out_nbr().len()
    }
    /// original id → dense index (binary search over the sorted dictionary).
    fn dense(&self, id: NodeId) -> Option<u32> {
        self.ids().binary_search(&id).ok().map(|i| i as u32)
    }
    fn original(&self, d: u32) -> NodeId {
        self.ids()[d as usize]
    }
    /// Degree DERIVED from offsets — no stored degree array.
    fn out_degree(&self, d: u32) -> u32 {
        let o = self.out_off();
        o[d as usize + 1] - o[d as usize]
    }
    fn in_degree(&self, d: u32) -> u32 {
        let o = self.in_off();
        o[d as usize + 1] - o[d as usize]
    }
    /// Resolve a label string to its integer id — the ONE place a string is compared. Do this once per
    /// query and pass the id down; never per node.
    fn label_id(&self, l: &str) -> Option<u32> {
        self.labels().iter().position(|x| x == l).map(|i| i as u32)
    }
    /// Out-neighbours filtered by an already-resolved label id (`None` = all). The hot-path form — no
    /// string work per node.
    fn out_neighbors_lid(&self, d: u32, lid: Option<u32>) -> &[u32] {
        let o = self.out_off();
        let (s, e) = (o[d as usize] as usize, o[d as usize + 1] as usize);
        slice_by_lid(self.out_nbr(), self.out_lbl(), s, e, lid)
    }
    fn in_neighbors_lid(&self, d: u32, lid: Option<u32>) -> &[u32] {
        let o = self.in_off();
        let (s, e) = (o[d as usize] as usize, o[d as usize + 1] as usize);
        slice_by_lid(self.in_nbr(), self.in_lbl(), s, e, lid)
    }
    /// Convenience string-label form (resolves the id once, then delegates). Absent label → empty.
    fn out_neighbors(&self, d: u32, label: Option<&str>) -> &[u32] {
        let o = self.out_off();
        let (s, e) = (o[d as usize] as usize, o[d as usize + 1] as usize);
        let lid = match label {
            None => None,
            Some(l) => match self.label_id(l) {
                Some(x) => Some(x),
                None => return &self.out_nbr()[s..s],
            },
        };
        slice_by_lid(self.out_nbr(), self.out_lbl(), s, e, lid)
    }
    fn in_neighbors(&self, d: u32, label: Option<&str>) -> &[u32] {
        let o = self.in_off();
        let (s, e) = (o[d as usize] as usize, o[d as usize + 1] as usize);
        let lid = match label {
            None => None,
            Some(l) => match self.label_id(l) {
                Some(x) => Some(x),
                None => return &self.in_nbr()[s..s],
            },
        };
        slice_by_lid(self.in_nbr(), self.in_lbl(), s, e, lid)
    }
    /// Edge existence via binary search in the label sub-slice (no Bloom — see GraphIndex::has_edge).
    fn has_edge_exact(&self, u: NodeId, v: NodeId, label: &str) -> bool {
        match (self.dense(u), self.dense(v)) {
            (Some(ud), Some(vd)) => self.out_neighbors(ud, Some(label)).binary_search(&vd).is_ok(),
            _ => false,
        }
    }
    /// k-hop over the CSR, sorted original ids. `visited` is a flat bit-array (dense-integer payoff). The
    /// frontier gather parallelises for a large frontier; the final sort makes the result deterministic.
    fn k_hop(&self, start: NodeId, k: usize, label: Option<&str>) -> Vec<NodeId> {
        let sd = match self.dense(start) {
            Some(d) => d,
            None => return Vec::new(),
        };
        // Resolve the label to an id ONCE — a string comparison per frontier vertex would be pure slack.
        let lid = match label {
            None => None,
            Some(l) => match self.label_id(l) {
                Some(x) => Some(x),
                None => return Vec::new(), // label absent ⇒ nothing matches
            },
        };
        let mut visited = vec![false; self.node_count()];
        visited[sd as usize] = true;
        let mut frontier = vec![sd];
        let mut result: Vec<u32> = Vec::new();
        for _ in 0..k {
            let candidates: Vec<u32> = if frontier.len() > 4096 {
                frontier
                    .par_iter()
                    .flat_map_iter(|&u| self.out_neighbors_lid(u, lid).iter().copied())
                    .collect()
            } else {
                let mut c = Vec::new();
                for &u in &frontier {
                    c.extend_from_slice(self.out_neighbors_lid(u, lid));
                }
                c
            };
            let mut next = Vec::new();
            for v in candidates {
                if !visited[v as usize] {
                    visited[v as usize] = true;
                    result.push(v);
                    next.push(v);
                }
            }
            frontier = next;
            if frontier.is_empty() {
                break;
            }
        }
        let mut out: Vec<NodeId> = result.iter().map(|&d| self.original(d)).collect();
        out.par_sort_unstable();
        out
    }
    /// Compiled fixed-length plan (exactly-length frontier) — the openCypher-IR target.
    fn plan(&self, start: NodeId, steps: &[Step]) -> Vec<NodeId> {
        let sd = match self.dense(start) {
            Some(d) => d,
            None => return Vec::new(),
        };
        let mut frontier: FxHashSet<u32> = FxHashSet::from_iter([sd]);
        for step in steps {
            // resolve this step's label id ONCE, not per frontier node.
            let lid = match step.label.as_deref() {
                None => None,
                Some(l) => match self.label_id(l) {
                    Some(x) => Some(x),
                    None => {
                        frontier = FxHashSet::default(); // label absent ⇒ empty result
                        break;
                    }
                },
            };
            let mut next: FxHashSet<u32> = FxHashSet::default();
            for &u in &frontier {
                for &v in self.out_neighbors_lid(u, lid) {
                    next.insert(v);
                }
            }
            frontier = next;
        }
        let mut out: Vec<NodeId> = frontier.into_iter().map(|d| self.original(d)).collect();
        out.par_sort_unstable();
        out
    }
}

/// The owned, in-memory index.
pub struct GraphIndex {
    id_of: Vec<NodeId>,
    labels: Vec<String>,
    out_off: Vec<u32>,
    out_nbr: Vec<u32>,
    out_lbl: Vec<u32>,
    in_off: Vec<u32>,
    in_nbr: Vec<u32>,
    in_lbl: Vec<u32>,
    prop_idx: FxHashMap<(String, PropKey), Vec<u32>>,
    edge_bloom: Option<crate::probabilistic::Bloom>,
}

impl GraphCore for GraphIndex {
    fn ids(&self) -> &[NodeId] {
        &self.id_of
    }
    fn labels(&self) -> &[String] {
        &self.labels
    }
    fn out_off(&self) -> &[u32] {
        &self.out_off
    }
    fn out_nbr(&self) -> &[u32] {
        &self.out_nbr
    }
    fn out_lbl(&self) -> &[u32] {
        &self.out_lbl
    }
    fn in_off(&self) -> &[u32] {
        &self.in_off
    }
    fn in_nbr(&self) -> &[u32] {
        &self.in_nbr
    }
    fn in_lbl(&self) -> &[u32] {
        &self.in_lbl
    }
}

/// Hash an (u, v, label) edge to a 64-bit key for the Bloom filter (FxHash, non-cryptographic).
fn edge_key(u: NodeId, v: NodeId, label: &str) -> u64 {
    use std::hash::{Hash, Hasher};
    let mut h = crate::fasthash::FxHasher::default();
    u.hash(&mut h);
    v.hash(&mut h);
    label.hash(&mut h);
    h.finish()
}

/// Build a CSR from dense edges `(row, label, endpoint)` via COUNTING SORT: bucket by `row` in O(m), then
/// sort each row by `(label, endpoint)` (packed into one u64) and dedup. No global comparison sort.
fn build_csr(
    n: usize,
    edges: impl Iterator<Item = (u32, u32, u32)> + Clone,
) -> (Vec<u32>, Vec<u32>, Vec<u32>) {
    let mut off = vec![0u32; n + 1];
    let mut m = 0usize;
    for (r, _, _) in edges.clone() {
        off[r as usize + 1] += 1;
        m += 1;
    }
    for i in 0..n {
        off[i + 1] += off[i];
    }
    let mut packed = vec![0u64; m];
    let mut cursor = off.clone();
    for (r, l, e) in edges {
        let p = cursor[r as usize] as usize;
        packed[p] = ((l as u64) << 32) | (e as u64);
        cursor[r as usize] += 1;
    }
    let mut nbr = Vec::with_capacity(m);
    let mut lbl = Vec::with_capacity(m);
    let mut new_off = vec![0u32; n + 1];
    for r in 0..n {
        let s = off[r] as usize;
        let e = off[r + 1] as usize;
        let row = &mut packed[s..e];
        row.sort_unstable();
        let mut last = 0u64;
        let mut first = true;
        for &pk in row.iter() {
            if first || pk != last {
                lbl.push((pk >> 32) as u32);
                nbr.push((pk & 0xffff_ffff) as u32);
                last = pk;
                first = false;
            }
        }
        new_off[r + 1] = nbr.len() as u32;
    }
    (new_off, nbr, lbl)
}

impl GraphIndex {
    /// Prepare the index from a store's committed view — the ingest step done RIGHT.
    pub fn from_store(s: &Store) -> Self {
        let view = s.view();
        let mut id_of: Vec<NodeId> = view.nodes.iter().cloned().collect();
        id_of.sort_unstable();
        let dense: FxHashMap<NodeId, u32> =
            id_of.iter().enumerate().map(|(i, &id)| (id, i as u32)).collect();

        let mut labels: Vec<String> = Vec::new();
        let mut label_id: FxHashMap<String, u32> = FxHashMap::default();
        let mut oedges: Vec<(u32, u32, u32)> = Vec::new();
        for (u, adj) in &view.out {
            let ud = dense[u];
            for (v, l) in adj {
                if let Some(&vd) = dense.get(v) {
                    let lid = match label_id.get(l.as_ref()) {
                        Some(&id) => id,
                        None => {
                            let id = labels.len() as u32;
                            labels.push(l.to_string());
                            label_id.insert(l.to_string(), id);
                            id
                        }
                    };
                    oedges.push((ud, lid, vd));
                }
            }
        }
        let mut prop_idx: FxHashMap<(String, PropKey), Vec<u32>> = FxHashMap::default();
        for ((id, key), val) in &view.props {
            if let Some(&d) = dense.get(id) {
                prop_idx.entry((key.clone(), PropKey::of(val))).or_default().push(d);
            }
        }
        Self::assemble(id_of, labels, oedges, prop_idx)
    }

    /// Bulk-ingest constructor from a labelled edge list (nodes inferred from endpoints). Collects DISTINCT
    /// ids first (hash set) and sorts only the ~n distinct — not all 2m endpoints.
    pub fn from_edges(edges: &[(NodeId, NodeId, String)]) -> Self {
        let mut set: FxHashSet<NodeId> = FxHashSet::default();
        for (u, v, _) in edges {
            set.insert(*u);
            set.insert(*v);
        }
        let mut id_of: Vec<NodeId> = set.into_iter().collect();
        id_of.sort_unstable();
        let dense: FxHashMap<NodeId, u32> =
            id_of.iter().enumerate().map(|(i, &id)| (id, i as u32)).collect();
        let mut labels: Vec<String> = Vec::new();
        let mut label_id: FxHashMap<String, u32> = FxHashMap::default();
        let mut oedges: Vec<(u32, u32, u32)> = Vec::with_capacity(edges.len());
        for (u, v, l) in edges {
            let lid = *label_id.entry(l.clone()).or_insert_with(|| {
                let id = labels.len() as u32;
                labels.push(l.clone());
                id
            });
            oedges.push((dense[u], lid, dense[v]));
        }
        Self::assemble(id_of, labels, oedges, FxHashMap::default())
    }

    fn assemble(
        id_of: Vec<NodeId>,
        labels: Vec<String>,
        oedges: Vec<(u32, u32, u32)>,
        mut prop_idx: FxHashMap<(String, PropKey), Vec<u32>>,
    ) -> Self {
        let n = id_of.len();
        let (out_off, out_nbr, out_lbl) = build_csr(n, oedges.iter().map(|&(s, l, d)| (s, l, d)));
        let (in_off, in_nbr, in_lbl) = build_csr(n, oedges.iter().map(|&(s, l, d)| (d, l, s)));
        for v in prop_idx.values_mut() {
            v.sort_unstable();
            v.dedup();
        }
        GraphIndex {
            id_of,
            labels,
            out_off,
            out_nbr,
            out_lbl,
            in_off,
            in_nbr,
            in_lbl,
            prop_idx,
            edge_bloom: None,
        }
    }

    /// Build the edge-existence Bloom filter (opt-in). Do this when the workload PROBES edges a lot
    /// (triangle counting, link-prediction candidate filtering); non-edges then reject in O(k). Skip it for
    /// pure-traversal workloads to keep ingest lean.
    pub fn with_edge_bloom(mut self) -> Self {
        let mut bloom = crate::probabilistic::Bloom::new(self.edge_count().max(1), 10);
        for u in 0..self.id_of.len() {
            let s = self.out_off[u] as usize;
            let e = self.out_off[u + 1] as usize;
            for i in s..e {
                let v = self.out_nbr[i];
                let l = self.out_lbl[i] as usize;
                bloom.insert(edge_key(self.id_of[u], self.id_of[v as usize], &self.labels[l]));
            }
        }
        self.edge_bloom = Some(bloom);
        self
    }

    /// Does edge (u→v :label) exist? The Bloom filter (if built) rejects a non-edge in O(k) before any
    /// dictionary lookup; otherwise / on a hit we verify exactly.
    pub fn has_edge(&self, u: NodeId, v: NodeId, label: &str) -> bool {
        if let Some(bloom) = &self.edge_bloom {
            if !bloom.maybe_contains(edge_key(u, v, label)) {
                return false;
            }
        }
        self.has_edge_exact(u, v, label)
    }

    /// Nodes whose property `key` equals `val` — a secondary-index point lookup (the FxHashMap already
    /// rejects a miss in O(1), so no per-property Bloom is needed on top of it).
    pub fn nodes_with_prop(&self, key: &str, val: &Prop) -> Vec<NodeId> {
        self.prop_idx
            .get(&(key.to_string(), PropKey::of(val)))
            .map(|v| v.iter().map(|&d| self.id_of[d as usize]).collect())
            .unwrap_or_default()
    }

    /// Persist the index to `path` so it can be MMAP'd back (paged from disk) instead of rebuilt on restart.
    /// The numeric CSR core is written 8-byte aligned for zero-copy mapping; labels are a length-prefixed
    /// blob. (The property index + Bloom are not persisted — rebuild on demand if needed.)
    pub fn save(&self, path: &Path) -> io::Result<()> {
        let n = self.node_count() as u64;
        let m = self.edge_count() as u64;
        let mut lblob = Vec::new();
        for l in &self.labels {
            lblob.extend_from_slice(&(l.len() as u32).to_le_bytes());
            lblob.extend_from_slice(l.as_bytes());
        }
        let mut buf = Vec::new();
        buf.extend_from_slice(&MAGIC.to_le_bytes());
        buf.extend_from_slice(&n.to_le_bytes());
        buf.extend_from_slice(&m.to_le_bytes());
        buf.extend_from_slice(&(self.labels.len() as u64).to_le_bytes());
        buf.extend_from_slice(&(lblob.len() as u64).to_le_bytes());
        buf.extend_from_slice(&lblob);
        while buf.len() % 8 != 0 {
            buf.push(0); // align the numeric arrays for zero-copy mmap
        }
        buf.extend_from_slice(bytemuck::cast_slice(&self.id_of)); // u64
        buf.extend_from_slice(bytemuck::cast_slice(&self.out_off));
        buf.extend_from_slice(bytemuck::cast_slice(&self.out_nbr));
        buf.extend_from_slice(bytemuck::cast_slice(&self.out_lbl));
        buf.extend_from_slice(bytemuck::cast_slice(&self.in_off));
        buf.extend_from_slice(bytemuck::cast_slice(&self.in_nbr));
        buf.extend_from_slice(bytemuck::cast_slice(&self.in_lbl));
        std::fs::write(path, buf)
    }
}

/// A read-only index whose CSR core is PAGED FROM DISK (mmap, zero-copy) — no rebuild on restart. Shares
/// every query with `GraphIndex` via `GraphCore`.
pub struct MmapGraphIndex {
    mmap: Mmap,
    n: usize,
    m: usize,
    labels: Vec<String>,
    ids_at: usize,
    out_off_at: usize,
    out_nbr_at: usize,
    out_lbl_at: usize,
    in_off_at: usize,
    in_nbr_at: usize,
    in_lbl_at: usize,
}

impl MmapGraphIndex {
    pub fn open(path: &Path) -> io::Result<Self> {
        let file = File::open(path)?;
        // SAFETY: read-only map of a file we control for the life of the process.
        let mmap = unsafe { Mmap::map(&file)? };
        let rd = |a: usize| u64::from_le_bytes(mmap[a..a + 8].try_into().unwrap());
        if rd(0) != MAGIC {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "bad graph-index magic"));
        }
        let n = rd(8) as usize;
        let m = rd(16) as usize;
        let n_labels = rd(24) as usize;
        let lblob_len = rd(32) as usize;
        let mut labels = Vec::with_capacity(n_labels);
        let mut p = 40;
        for _ in 0..n_labels {
            let len = u32::from_le_bytes(mmap[p..p + 4].try_into().unwrap()) as usize;
            p += 4;
            labels.push(String::from_utf8_lossy(&mmap[p..p + len]).into_owned());
            p += len;
        }
        let mut at = 40 + lblob_len;
        while at % 8 != 0 {
            at += 1;
        }
        let ids_at = at;
        let out_off_at = ids_at + n * 8;
        let out_nbr_at = out_off_at + (n + 1) * 4;
        let out_lbl_at = out_nbr_at + m * 4;
        let in_off_at = out_lbl_at + m * 4;
        let in_nbr_at = in_off_at + (n + 1) * 4;
        let in_lbl_at = in_nbr_at + m * 4;
        Ok(MmapGraphIndex {
            mmap,
            n,
            m,
            labels,
            ids_at,
            out_off_at,
            out_nbr_at,
            out_lbl_at,
            in_off_at,
            in_nbr_at,
            in_lbl_at,
        })
    }
}

impl GraphCore for MmapGraphIndex {
    fn ids(&self) -> &[NodeId] {
        bytemuck::cast_slice(&self.mmap[self.ids_at..self.ids_at + self.n * 8])
    }
    fn labels(&self) -> &[String] {
        &self.labels
    }
    fn out_off(&self) -> &[u32] {
        bytemuck::cast_slice(&self.mmap[self.out_off_at..self.out_off_at + (self.n + 1) * 4])
    }
    fn out_nbr(&self) -> &[u32] {
        bytemuck::cast_slice(&self.mmap[self.out_nbr_at..self.out_nbr_at + self.m * 4])
    }
    fn out_lbl(&self) -> &[u32] {
        bytemuck::cast_slice(&self.mmap[self.out_lbl_at..self.out_lbl_at + self.m * 4])
    }
    fn in_off(&self) -> &[u32] {
        bytemuck::cast_slice(&self.mmap[self.in_off_at..self.in_off_at + (self.n + 1) * 4])
    }
    fn in_nbr(&self) -> &[u32] {
        bytemuck::cast_slice(&self.mmap[self.in_nbr_at..self.in_nbr_at + self.m * 4])
    }
    fn in_lbl(&self) -> &[u32] {
        bytemuck::cast_slice(&self.mmap[self.in_lbl_at..self.in_lbl_at + self.m * 4])
    }
}

impl Store {
    /// Freeze the current view into a read-optimized [`GraphIndex`] (the ingest-prepare step).
    pub fn freeze(&self) -> GraphIndex {
        GraphIndex::from_store(self)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::graphdb::Prop;

    fn sample() -> Store {
        let mut s = Store::memory(1);
        // deliberately non-contiguous, unordered original ids to prove dictionary encoding.
        for id in [100u64, 5, 42, 7, 1000, 3] {
            s.add_node(id).unwrap();
        }
        s.add_edge(100, 5, "KNOWS").unwrap();
        s.add_edge(100, 42, "WORKS").unwrap();
        s.add_edge(5, 7, "KNOWS").unwrap();
        s.add_edge(7, 1000, "KNOWS").unwrap();
        s.add_edge(42, 3, "KNOWS").unwrap();
        s.set_prop(5, "city", Prop::Text("NYC".into())).unwrap();
        s.set_prop(7, "city", Prop::Text("NYC".into())).unwrap();
        s.set_prop(100, "city", Prop::Text("LA".into())).unwrap();
        s
    }

    #[test]
    fn dictionary_is_dense_sorted_and_roundtrips() {
        let idx = sample().freeze();
        assert_eq!(idx.node_count(), 6);
        for d in 0..idx.node_count() as u32 {
            assert_eq!(idx.dense(idx.original(d)), Some(d));
        }
        for d in 1..idx.node_count() as u32 {
            assert!(idx.original(d - 1) < idx.original(d), "dictionary must be ascending");
        }
        assert_eq!(idx.dense(999), None, "absent id → None");
    }

    #[test]
    fn labelled_slice_and_edge_existence() {
        let idx = sample().freeze();
        let d100 = idx.dense(100).unwrap();
        let knows: Vec<NodeId> = idx.out_neighbors(d100, Some("KNOWS")).iter().map(|&d| idx.original(d)).collect();
        assert_eq!(knows, vec![5]);
        let works: Vec<NodeId> = idx.out_neighbors(d100, Some("WORKS")).iter().map(|&d| idx.original(d)).collect();
        assert_eq!(works, vec![42]);
        assert!(idx.has_edge(100, 5, "KNOWS"));
        assert!(!idx.has_edge(100, 5, "WORKS"));
        assert!(!idx.has_edge(100, 999, "KNOWS"));
    }

    #[test]
    fn reverse_index_and_degrees() {
        let idx = sample().freeze();
        let d7 = idx.dense(7).unwrap();
        let preds: Vec<NodeId> = idx.in_neighbors(d7, Some("KNOWS")).iter().map(|&d| idx.original(d)).collect();
        assert_eq!(preds, vec![5]);
        assert_eq!(idx.in_degree(d7), 1);
        assert_eq!(idx.out_degree(idx.dense(100).unwrap()), 2);
    }

    #[test]
    fn property_secondary_index() {
        let idx = sample().freeze();
        let mut nyc = idx.nodes_with_prop("city", &Prop::Text("NYC".into()));
        nyc.sort_unstable();
        assert_eq!(nyc, vec![5, 7]);
        assert_eq!(idx.nodes_with_prop("city", &Prop::Text("LA".into())), vec![100]);
        assert!(idx.nodes_with_prop("city", &Prop::Text("Paris".into())).is_empty());
    }

    #[test]
    fn indexed_queries_match_the_store() {
        let s = sample();
        let idx = s.freeze();
        for &start in &[100u64, 5, 42, 7] {
            for k in 1..=4 {
                assert_eq!(idx.k_hop(start, k, None), s.k_hop(start, k, None), "k_hop (start={start}, k={k})");
                assert_eq!(
                    idx.k_hop(start, k, Some("KNOWS")),
                    s.k_hop(start, k, Some("KNOWS")),
                    "labelled k_hop"
                );
            }
        }
    }

    #[test]
    fn mmap_roundtrip_matches_owned() {
        let idx = sample().freeze();
        let path = std::env::temp_dir().join(format!("hg_gidx_{}.bin", std::process::id()));
        idx.save(&path).unwrap();
        let m = MmapGraphIndex::open(&path).unwrap();
        assert_eq!(m.node_count(), idx.node_count());
        assert_eq!(m.edge_count(), idx.edge_count());
        for &start in &[100u64, 5, 42, 7] {
            for k in 1..=3 {
                assert_eq!(m.k_hop(start, k, None), idx.k_hop(start, k, None), "mmap k_hop must match owned");
                assert_eq!(m.k_hop(start, k, Some("KNOWS")), idx.k_hop(start, k, Some("KNOWS")));
            }
        }
        assert!(m.has_edge_exact(100, 5, "KNOWS"));
        assert!(!m.has_edge_exact(100, 5, "WORKS"));
        // reverse index survives the round-trip too
        assert_eq!(m.in_degree(m.dense(7).unwrap()), 1);
        std::fs::remove_file(&path).ok();
    }
}
