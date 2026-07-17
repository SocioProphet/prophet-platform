//! boundary — boundary-only halo (ghost vertices) distributed PageRank. The scaling unlock.
//!
//! The plain `distributed_pagerank` exchanges the FULL O(n) rank vector to every shard each superstep —
//! that's a k·n broadcast, and it's the reason a naive BSP graph engine stops scaling: add a node and
//! every node pays for it. Here a shard exchanges ONLY the ranks of the remote vertices its own edges
//! actually reference — its "ghosts". With an edge-cut partition the ghost set is O(boundary) per shard,
//! so the recurring per-superstep network cost is Σ|ghosts| ≪ k·n. That is the difference between "rides a
//! cluster" and "broadcasts the world every step". The numeric result is bit-identical to single-graph
//! `pagerank` — the halo shrinks, the answer doesn't move.
//!
//! Cost accounting (honest): out-degrees are static topology, exchanged ONCE at setup (O(n) one-time).
//! The RECURRING cost — what grows with supersteps and dominates at scale — is the ghost rank halo, and
//! that is exactly what `halo_bytes`/`total_halo_bytes` measure.

use rayon::prelude::*;
use std::collections::{BTreeSet, HashMap};

/// One partition carrying a boundary-only halo. Owns node range `[lo, hi)`. `ghosts` holds the sorted,
/// distinct global ids of the remote source vertices this shard's in-edges reference (sorted → the halo
/// order is deterministic and machine-independent). `in_adj` stores, per owned node, the LOCAL index of
/// each in-neighbour: an owned source maps to `src - lo` in `[0, owned)`, a ghost source maps to
/// `owned + ghost_position`. That compact local index space is exactly what a real worker holds in RAM —
/// it never materialises the global vertex id space.
pub struct BoundaryShard {
    pub lo: usize,
    pub hi: usize,
    /// Global ids of the remote source vertices referenced by this shard's edges — sorted, distinct.
    pub ghosts: Vec<usize>,
    /// Per owned node (index `v - lo`): local indices (owned `< owned`, else ghost) of its in-neighbours.
    pub in_adj: Vec<Vec<usize>>,
}

impl BoundaryShard {
    /// Number of nodes this shard owns.
    pub fn owned(&self) -> usize {
        self.hi - self.lo
    }
    /// Bytes this shard RECEIVES per superstep for its halo (one f64 per ghost). The recurring cost.
    pub fn halo_bytes(&self) -> usize {
        self.ghosts.len() * 8
    }
}

/// Total recurring halo traffic across all shards, per superstep, in bytes. Compare against a full
/// broadcast (`k * n * 8`) to see the boundary-only saving on a given partition.
pub fn total_halo_bytes(shards: &[BoundaryShard]) -> usize {
    shards.iter().map(BoundaryShard::halo_bytes).sum()
}

/// The `k` equal contiguous vertex ranges (the range partition). Boundary `c` owns `[bounds[c], bounds[c+1])`.
/// This is the partition each worker can compute LOCALLY with no coordinator — the basis for distributed
/// generation: a worker knows which vertices it owns, generates its own edge slice, and routes each edge to
/// the shard owning its target. No node ever holds the whole graph.
pub fn range_bounds(n: usize, k: usize) -> Vec<usize> {
    if n == 0 {
        return vec![0];
    }
    let k = k.clamp(1, n);
    let size = n.div_ceil(k);
    (0..=k).map(|c| (c * size).min(n)).collect()
}

/// Which shard owns vertex `v`, given contiguous `bounds` — the routing function for the edge shuffle.
pub fn owner_of(v: usize, bounds: &[usize]) -> usize {
    let k = bounds.len() - 1;
    match bounds.binary_search(&v) {
        Ok(c) => c.min(k - 1),
        Err(c) => c - 1,
    }
}

// ---- Cyclic (round-robin) partition -------------------------------------------------------------
// The contiguous range partition hands ALL the low-numbered vertices to shard 0. Under a power-law
// (RMAT/Graph500) in-degree, those low ids ARE the hubs, so shard 0 inherits a ~⅓-of-all-edges spike —
// the memory blow-up that walls a billion-plus run on commodity nodes. The cyclic partition instead
// interleaves ownership (`v % k`), scattering the top-k hubs onto k different shards, so no shard
// inherits the spike. Crucially it keeps owned-vertex ENUMERATION at O(n/k): a shard's owned vertices are
// the arithmetic sequence `c, c+k, c+2k, …`, so local index `l` ↔ global `l*k + c` is a cheap bijection —
// no O(n) scan and no global hashmap to know what you own.

/// How many vertices shard `c` owns under the cyclic partition of `[0, n)` into `k` shards
/// (i.e. `|{ c, c+k, c+2k, … } ∩ [0, n)|`). Also the owned count in the BALANCED partition below, because
/// that one is cyclic in a bit-MIXED space of the same size.
#[inline]
pub fn cyclic_owned(n: usize, k: usize, c: usize) -> usize {
    if c >= n {
        0
    } else {
        (n - 1 - c) / k + 1
    }
}

// ---- Balanced partition (bit-mix permutation, then cyclic) ---------------------------------------
// A plain cyclic partition (`v % k`) does NOT fix RMAT skew: RMAT makes EVERY bit of the target id 0 with
// probability a+b, so reading the low log2(k) bits (cyclic) is just as skewed as reading the high bits
// (range) — one shard still gets (a+b)^log2(k) ≈ ⅓ of all edges at k=16. The fix is to MIX all the id bits
// first (an invertible hash permutation `mix`), then partition cyclically in mixed space:
//   owner(v)  = mix(v) % k       local(v) = mix(v) / k       global(l) = unmix(l*k + c)
// Mixing decorrelates the shard bits from the per-bit skew → each shard gets ~m/k. Because `mix` is a
// bijection on `[0, 2^bits)`, owned enumeration stays O(n/k) (no O(n) scan, no global hashmap) and the
// owned count stays closed-form (`cyclic_owned`). `unmix` is only needed to reassemble at verify scale.

const MIX_MULT: [u64; 2] = [0x2545_F491_4F6C_DD1D, 0x9E37_79B9_7F4A_7C15];

#[inline]
fn mask(bits: u32) -> u64 {
    if bits >= 64 {
        u64::MAX
    } else {
        (1u64 << bits) - 1
    }
}
#[inline]
fn xsr(x: u64, s: u32, m: u64) -> u64 {
    (x ^ (x >> s)) & m
}
// Invert y = x ^ (x >> s) by fixed-point iteration (each pass fixes the next `s` bits from the top).
#[inline]
fn inv_xsr(y: u64, s: u32, bits: u32, m: u64) -> u64 {
    let mut x = y & m;
    let iters = bits.div_ceil(s);
    for _ in 0..iters {
        x = (y ^ (x >> s)) & m;
    }
    x
}
// Modular inverse of odd `c` mod 2^bits (Newton doubling: 3→6→12→…→192 correct bits).
#[inline]
fn mul_inv(c: u64, m: u64) -> u64 {
    let mut inv = c;
    for _ in 0..6 {
        inv = inv.wrapping_mul(2u64.wrapping_sub(c.wrapping_mul(inv)));
    }
    inv & m
}

/// Invertible bit-mix permutation on `[0, 2^bits)`. Decorrelates a vertex id from the RMAT per-bit skew.
pub fn mix_bits(v: usize, bits: u32) -> usize {
    let m = mask(bits);
    let (s1, s2) = (bits / 2, bits / 3 + 1);
    let mut x = v as u64 & m;
    x = xsr(x, s1, m);
    x = x.wrapping_mul(MIX_MULT[0]) & m;
    x = xsr(x, s2, m);
    x = x.wrapping_mul(MIX_MULT[1]) & m;
    x = xsr(x, s1, m);
    (x & m) as usize
}

/// Inverse of [`mix_bits`] — recovers the global vertex id from a mixed value.
pub fn unmix_bits(w: usize, bits: u32) -> usize {
    let m = mask(bits);
    let (s1, s2) = (bits / 2, bits / 3 + 1);
    let mut x = w as u64 & m;
    x = inv_xsr(x, s1, bits, m);
    x = x.wrapping_mul(mul_inv(MIX_MULT[1], m)) & m;
    x = inv_xsr(x, s2, bits, m);
    x = x.wrapping_mul(mul_inv(MIX_MULT[0], m)) & m;
    x = inv_xsr(x, s1, bits, m);
    (x & m) as usize
}

/// Balanced owner of vertex `v` (`n = 2^bits` vertices, `k` shards): `mix(v) % k`.
#[inline]
pub fn balanced_owner(v: usize, bits: u32, k: usize) -> usize {
    mix_bits(v, bits) % k
}
/// Balanced local index of an owned vertex `v`: `mix(v) / k`.
#[inline]
pub fn balanced_local(v: usize, bits: u32, k: usize) -> usize {
    mix_bits(v, bits) / k
}
/// Global vertex id of shard `c`'s balanced local index `l`: `unmix(l*k + c)`.
#[inline]
pub fn balanced_to_global(l: usize, bits: u32, k: usize, c: usize) -> usize {
    unmix_bits(l * k + c, bits)
}

/// Range-partition into `k` boundary shards (each owns a contiguous node range) + the global out-degree
/// vector (static setup metadata). Each shard's ghost set is discovered from the in-edges it owns.
pub fn partition_edges_boundary(
    n: usize,
    edges: &[(usize, usize)],
    k: usize,
) -> (Vec<BoundaryShard>, Vec<u32>) {
    if n == 0 {
        return (Vec::new(), Vec::new());
    }
    let k = k.clamp(1, n);
    let size = n.div_ceil(k);
    let bounds: Vec<usize> = (0..=k).map(|c| (c * size).min(n)).collect();
    partition_edges_boundary_at(n, edges, &bounds)
}

/// Build boundary shards from EXPLICIT contiguous boundaries: shard `c` owns `[bounds[c], bounds[c+1])`.
/// `bounds` must be non-decreasing with `bounds[0] == 0` and `bounds[last] == n`. This is the general form
/// a smart partitioner drives — relabel vertices so each partition is a contiguous block (unequal sizes),
/// pass the block boundaries here, and the same boundary-halo PageRank runs on the edge-cut-minimised
/// layout. The equal-`size` range partition is just the special case `partition_edges_boundary` produces.
pub fn partition_edges_boundary_at(
    n: usize,
    edges: &[(usize, usize)],
    bounds: &[usize],
) -> (Vec<BoundaryShard>, Vec<u32>) {
    if n == 0 || bounds.len() < 2 {
        return (Vec::new(), Vec::new());
    }
    let k = bounds.len() - 1;
    // Owner of a global id via binary search over the boundaries: largest c with bounds[c] <= v.
    let owner = |v: usize| -> usize {
        match bounds.binary_search(&v) {
            Ok(c) => c.min(k - 1), // v is exactly a boundary start → that block
            Err(c) => c - 1,       // between bounds[c-1] and bounds[c]
        }
    };
    let mut out_deg = vec![0u32; n];
    let mut raw: Vec<Vec<Vec<usize>>> = (0..k)
        .map(|c| vec![Vec::new(); bounds[c + 1] - bounds[c]])
        .collect();
    let mut ghost_sets: Vec<BTreeSet<usize>> = vec![BTreeSet::new(); k];
    for &(u, v) in edges {
        if u < n && v < n {
            out_deg[u] += 1;
            let c = owner(v);
            let (lo, hi) = (bounds[c], bounds[c + 1]);
            raw[c][v - lo].push(u);
            if u < lo || u >= hi {
                ghost_sets[c].insert(u); // remote source → ghost
            }
        }
    }
    let mut shards = Vec::with_capacity(k);
    for c in 0..k {
        let (lo, hi) = (bounds[c], bounds[c + 1]);
        let owned = hi - lo;
        let ghosts: Vec<usize> = ghost_sets[c].iter().copied().collect();
        let ghost_idx: HashMap<usize, usize> =
            ghosts.iter().enumerate().map(|(i, &g)| (g, i)).collect();
        let in_adj: Vec<Vec<usize>> = raw[c]
            .iter()
            .map(|srcs| {
                srcs.iter()
                    .map(|&u| {
                        if u >= lo && u < hi {
                            u - lo
                        } else {
                            owned + ghost_idx[&u]
                        }
                    })
                    .collect()
            })
            .collect();
        shards.push(BoundaryShard {
            lo,
            hi,
            ghosts,
            in_adj,
        });
    }
    (shards, out_deg)
}

/// Distributed PageRank with a boundary-only halo. Each superstep, every shard assembles a LOCAL rank
/// view = its owned ranks + only its ghost ranks (the boundary halo pulled from the ghosts' owners),
/// then computes its owned partial from that local view alone — it never reads the global rank vector by
/// arbitrary index, only the O(owned + ghosts) slice a real worker would have received. Deterministic
/// (disjoint owned ranges, sorted ghosts, fixed order) and bit-identical to single-graph `pagerank`.
pub fn distributed_pagerank_boundary(
    n: usize,
    shards: &[BoundaryShard],
    out_deg: &[u32],
    damping: f64,
    max_iters: usize,
    tol: f64,
) -> Vec<f64> {
    if n == 0 {
        return Vec::new();
    }
    let base = (1.0 - damping) / n as f64;
    let mut rank = vec![1.0 / n as f64; n];
    for _ in 0..max_iters {
        // Dangling mass: derived from the static out-degree topology (setup metadata), O(n) serial.
        let mut dangling = 0.0;
        for u in 0..n {
            if out_deg[u] == 0 {
                dangling += rank[u];
            }
        }
        let add = base + damping * dangling / n as f64;
        // Each shard works from its local view only: owned rank slice + ghost halo. Ghost out-degrees
        // come from the static setup vector (exchanged once), not the per-step halo.
        let partials: Vec<(usize, Vec<f64>)> = shards
            .par_iter()
            .map(|sh| {
                let owned = sh.owned();
                // The received message: owned ranks followed by the boundary halo (ghost ranks).
                let mut local_rank = vec![0.0f64; owned + sh.ghosts.len()];
                local_rank[..owned].copy_from_slice(&rank[sh.lo..sh.hi]);
                for (i, &g) in sh.ghosts.iter().enumerate() {
                    local_rank[owned + i] = rank[g];
                }
                let mut out = vec![0.0f64; owned];
                for (i, nbrs) in sh.in_adj.iter().enumerate() {
                    let mut acc = 0.0;
                    for &li in nbrs {
                        let gid = if li < owned {
                            sh.lo + li
                        } else {
                            sh.ghosts[li - owned]
                        };
                        acc += local_rank[li] / out_deg[gid] as f64;
                    }
                    out[i] = add + damping * acc;
                }
                (sh.lo, out)
            })
            .collect();
        let mut next = vec![0.0f64; n];
        for (lo, local) in &partials {
            next[*lo..*lo + local.len()].copy_from_slice(local);
        }
        let diff: f64 = (0..n).map(|i| (next[i] - rank[i]).abs()).sum();
        rank = next;
        if diff < tol {
            break;
        }
    }
    rank
}

// ── Residual (delta-push) boundary halo — send only the ghosts that MOVED ──────────────────────────────────────
/// Byte accounting for a delta halo run: `dense_bytes` is what the plain boundary halo ships (every ghost,
/// every superstep, one f64 = 8 B), `delta_bytes` is what the residual halo ships (only ghosts whose owner
/// rank moved by more than `delta_eps`, as sparse (id,value) = 12 B pairs). The honest crossover: delta wins
/// once the changed fraction drops below 8/12 = 2/3, which converging PageRank reaches fast (rank freezes
/// vertex-by-vertex), so late supersteps ship almost nothing.
pub struct DeltaHaloStats {
    pub supersteps: usize,
    pub dense_bytes: usize,
    pub delta_bytes: usize,
}

/// Distributed boundary-halo PageRank that exchanges the ghost halo as RESIDUAL DELTAS: each shard keeps a
/// local cache of its ghost ranks and, per superstep, receives only the ghosts whose owner value moved by
/// more than `delta_eps` (sparse id+value updates) — converged ghosts send nothing. With `delta_eps == 0`
/// this is bit-identical to `distributed_pagerank_boundary` (a cache refreshed to the exact value equals
/// reading it directly), and it still drops the byte count as ranks freeze; with a small `delta_eps` it
/// trades a bounded O(delta_eps) perturbation for a large late-run wire saving. Returns `(rank, stats)` so
/// the dense-vs-delta traffic and the resulting error are both measurable. Deterministic.
pub fn distributed_pagerank_boundary_delta(
    n: usize,
    shards: &[BoundaryShard],
    out_deg: &[u32],
    damping: f64,
    max_iters: usize,
    tol: f64,
    delta_eps: f64,
) -> (Vec<f64>, DeltaHaloStats) {
    if n == 0 {
        return (
            Vec::new(),
            DeltaHaloStats {
                supersteps: 0,
                dense_bytes: 0,
                delta_bytes: 0,
            },
        );
    }
    let base = (1.0 - damping) / n as f64;
    let mut rank = vec![1.0 / n as f64; n];
    // Per-shard ghost caches — the only ghost state a real worker holds. All shards start agreeing (1/n),
    // matching the initial rank, so superstep 1 already reads exact ghosts (no warm-up error).
    let mut caches: Vec<Vec<f64>> = shards
        .iter()
        .map(|s| vec![1.0 / n as f64; s.ghosts.len()])
        .collect();
    let mut stats = DeltaHaloStats {
        supersteps: 0,
        dense_bytes: 0,
        delta_bytes: 0,
    };
    for _ in 0..max_iters {
        stats.supersteps += 1;
        let mut dangling = 0.0;
        for u in 0..n {
            if out_deg[u] == 0 {
                dangling += rank[u];
            }
        }
        let add = base + damping * dangling / n as f64;
        // Each shard computes from its owned ranks + its CACHED ghost view (possibly stale by < delta_eps).
        let partials: Vec<(usize, Vec<f64>)> = shards
            .par_iter()
            .zip(&caches)
            .map(|(sh, cache)| {
                let owned = sh.owned();
                let mut local_rank = vec![0.0f64; owned + sh.ghosts.len()];
                local_rank[..owned].copy_from_slice(&rank[sh.lo..sh.hi]);
                local_rank[owned..].copy_from_slice(cache);
                let mut out = vec![0.0f64; owned];
                for (i, nbrs) in sh.in_adj.iter().enumerate() {
                    let mut acc = 0.0;
                    for &li in nbrs {
                        let gid = if li < owned {
                            sh.lo + li
                        } else {
                            sh.ghosts[li - owned]
                        };
                        acc += local_rank[li] / out_deg[gid] as f64;
                    }
                    out[i] = add + damping * acc;
                }
                (sh.lo, out)
            })
            .collect();
        let mut next = rank.clone();
        for (lo, local) in &partials {
            next[*lo..*lo + local.len()].copy_from_slice(local);
        }
        let diff: f64 = (0..n).map(|i| (next[i] - rank[i]).abs()).sum();
        rank = next;
        // DELTA EXCHANGE for the next superstep: refresh each shard's ghost cache from the new true rank,
        // shipping only the movers. Dense accounting bills every ghost; delta bills only the sent pairs.
        for (sh, cache) in shards.iter().zip(caches.iter_mut()) {
            stats.dense_bytes += sh.ghosts.len() * 8;
            for (i, &g) in sh.ghosts.iter().enumerate() {
                if (rank[g] - cache[i]).abs() > delta_eps {
                    cache[i] = rank[g];
                    stats.delta_bytes += 12; // sparse (u32 ghost slot + f64 value)
                }
            }
        }
        if diff < tol {
            break;
        }
    }
    (rank, stats)
}

// ── Boundary-halo connected components ────────────────────────────────────────────────────────────────────────
/// A CC partition with a boundary-only halo. Owns `[lo, hi)`; `ghosts` are the sorted distinct global ids
/// of the remote NEIGHBOURS this shard's owned nodes touch (undirected). `adj` stores, per owned node, the
/// LOCAL index of each neighbour (owned `< owned`, else ghost). The halo exchanged each superstep is just
/// the ghost LABELS (u32) — proving the boundary-halo model is not PageRank-specific but covers the whole
/// vertex-centric class.
pub struct BoundaryCcShard {
    pub lo: usize,
    pub hi: usize,
    pub ghosts: Vec<usize>,
    pub adj: Vec<Vec<usize>>,
}

impl BoundaryCcShard {
    pub fn owned(&self) -> usize {
        self.hi - self.lo
    }
    /// Bytes received per superstep for the label halo (one u32 per ghost).
    pub fn halo_bytes(&self) -> usize {
        self.ghosts.len() * 4
    }
}

/// Total recurring CC label-halo traffic per superstep, in bytes.
pub fn total_cc_halo_bytes(shards: &[BoundaryCcShard]) -> usize {
    shards.iter().map(BoundaryCcShard::halo_bytes).sum()
}

/// Range-partition the undirected graph into `k` boundary CC shards.
pub fn partition_cc_boundary(n: usize, edges: &[(usize, usize)], k: usize) -> Vec<BoundaryCcShard> {
    if n == 0 {
        return Vec::new();
    }
    let k = k.clamp(1, n);
    let size = n.div_ceil(k);
    let bounds: Vec<usize> = (0..=k).map(|c| (c * size).min(n)).collect();
    partition_cc_boundary_at(n, edges, &bounds)
}

/// Build boundary CC shards from explicit contiguous boundaries (the general form a smart partition drives).
pub fn partition_cc_boundary_at(
    n: usize,
    edges: &[(usize, usize)],
    bounds: &[usize],
) -> Vec<BoundaryCcShard> {
    if n == 0 || bounds.len() < 2 {
        return Vec::new();
    }
    let k = bounds.len() - 1;
    let owner = |v: usize| -> usize {
        match bounds.binary_search(&v) {
            Ok(c) => c.min(k - 1),
            Err(c) => c - 1,
        }
    };
    // Undirected: each edge contributes a neighbour to BOTH endpoints' owning shards.
    let mut raw: Vec<Vec<Vec<usize>>> = (0..k)
        .map(|c| vec![Vec::new(); bounds[c + 1] - bounds[c]])
        .collect();
    let mut ghost_sets: Vec<BTreeSet<usize>> = vec![BTreeSet::new(); k];
    let mut note = |shard: usize, node: usize, nbr: usize| {
        let (lo, hi) = (bounds[shard], bounds[shard + 1]);
        raw[shard][node - lo].push(nbr);
        if nbr < lo || nbr >= hi {
            ghost_sets[shard].insert(nbr);
        }
    };
    for &(u, v) in edges {
        if u < n && v < n && u != v {
            note(owner(u), u, v);
            note(owner(v), v, u);
        }
    }
    let mut shards = Vec::with_capacity(k);
    for c in 0..k {
        let (lo, hi) = (bounds[c], bounds[c + 1]);
        let owned = hi - lo;
        let ghosts: Vec<usize> = ghost_sets[c].iter().copied().collect();
        let ghost_idx: HashMap<usize, usize> =
            ghosts.iter().enumerate().map(|(i, &g)| (g, i)).collect();
        let adj: Vec<Vec<usize>> = raw[c]
            .iter()
            .map(|nbrs| {
                nbrs.iter()
                    .map(|&w| {
                        if w >= lo && w < hi {
                            w - lo
                        } else {
                            owned + ghost_idx[&w]
                        }
                    })
                    .collect()
            })
            .collect();
        shards.push(BoundaryCcShard {
            lo,
            hi,
            ghosts,
            adj,
        });
    }
    shards
}

/// Distributed connected components with a boundary-only label halo. Each superstep every shard assembles
/// its local label view (owned labels + ghost label halo) and min-propagates over its owned nodes; disjoint
/// owned ranges are gathered; iterate to a global fixpoint. Only ghost labels cross boundaries — edges stay
/// sovereign. Deterministic and identical to single-graph `connected_components`.
pub fn distributed_cc_boundary(n: usize, shards: &[BoundaryCcShard]) -> Vec<u32> {
    if n == 0 {
        return Vec::new();
    }
    let mut label: Vec<u32> = (0..n as u32).collect();
    loop {
        let partials: Vec<(usize, Vec<u32>)> = shards
            .par_iter()
            .map(|sh| {
                let owned = sh.owned();
                // Received message: owned labels + the boundary halo (ghost labels).
                let mut local_label = vec![0u32; owned + sh.ghosts.len()];
                local_label[..owned].copy_from_slice(&label[sh.lo..sh.hi]);
                for (i, &g) in sh.ghosts.iter().enumerate() {
                    local_label[owned + i] = label[g];
                }
                let mut out = vec![0u32; owned];
                for (i, nbrs) in sh.adj.iter().enumerate() {
                    let mut m = local_label[i];
                    for &li in nbrs {
                        if local_label[li] < m {
                            m = local_label[li];
                        }
                    }
                    out[i] = m;
                }
                (sh.lo, out)
            })
            .collect();
        let mut changed = false;
        let mut next = label.clone();
        for (lo, local) in &partials {
            for (i, &l) in local.iter().enumerate() {
                if l != next[lo + i] {
                    next[lo + i] = l;
                    changed = true;
                }
            }
        }
        label = next;
        if !changed {
            break;
        }
    }
    label
}

/// Distributed breadth-first search (hop distance from `source`) with a boundary-only halo, over the
/// undirected CC shards. This is the TRAVERSAL shape — a frontier expansion, not a fixpoint smoothing like
/// PageRank — so it proves the boundary-halo model covers the LDBC traversal class too. Each superstep is
/// a Bellman-Ford-style relaxation (`dist[v] = min(dist[v], min_{u~v} dist[u] + 1)`); only ghost distances
/// (u32) cross shard boundaries. Deterministic; converges in O(diameter) supersteps to the exact BFS tree.
/// Unreachable vertices stay `u32::MAX`. (Weighted SSSP is the same loop with `+ w(u,v)` instead of `+ 1`.)
pub fn distributed_bfs_boundary(n: usize, shards: &[BoundaryCcShard], source: usize) -> Vec<u32> {
    if n == 0 {
        return Vec::new();
    }
    let mut dist = vec![u32::MAX; n];
    if source < n {
        dist[source] = 0;
    }
    loop {
        let partials: Vec<(usize, Vec<u32>)> = shards
            .par_iter()
            .map(|sh| {
                let owned = sh.owned();
                let mut local_dist = vec![u32::MAX; owned + sh.ghosts.len()];
                local_dist[..owned].copy_from_slice(&dist[sh.lo..sh.hi]);
                for (i, &g) in sh.ghosts.iter().enumerate() {
                    local_dist[owned + i] = dist[g];
                }
                let mut out = vec![u32::MAX; owned];
                for (i, nbrs) in sh.adj.iter().enumerate() {
                    let mut m = local_dist[i];
                    for &li in nbrs {
                        let du = local_dist[li];
                        if du != u32::MAX && du + 1 < m {
                            m = du + 1;
                        }
                    }
                    out[i] = m;
                }
                (sh.lo, out)
            })
            .collect();
        let mut changed = false;
        let mut next = dist.clone();
        for (lo, local) in &partials {
            for (i, &dv) in local.iter().enumerate() {
                if dv < next[lo + i] {
                    next[lo + i] = dv;
                    changed = true;
                }
            }
        }
        dist = next;
        if !changed {
            break;
        }
    }
    dist
}

// ── Boundary-halo weighted single-source shortest path (SSSP) ──────────────────────────────────────────────────
/// A weighted-SSSP partition with a boundary-only halo. Like `BoundaryCcShard` but each neighbour carries
/// an edge weight, so `adj[i]` is `(local index, weight)` pairs. The halo is f64 distances.
pub struct BoundaryWShard {
    pub lo: usize,
    pub hi: usize,
    pub ghosts: Vec<usize>,
    pub adj: Vec<Vec<(usize, f64)>>,
}

impl BoundaryWShard {
    pub fn owned(&self) -> usize {
        self.hi - self.lo
    }
    /// Bytes received per superstep for the distance halo (one f64 per ghost).
    pub fn halo_bytes(&self) -> usize {
        self.ghosts.len() * 8
    }
}

/// Total recurring SSSP distance-halo traffic per superstep, in bytes.
pub fn total_w_halo_bytes(shards: &[BoundaryWShard]) -> usize {
    shards.iter().map(BoundaryWShard::halo_bytes).sum()
}

/// Range-partition a weighted undirected graph (`weights` parallel to `edges`) into `k` boundary SSSP shards.
pub fn partition_wsssp_boundary(
    n: usize,
    edges: &[(usize, usize)],
    weights: &[f64],
    k: usize,
) -> Vec<BoundaryWShard> {
    if n == 0 {
        return Vec::new();
    }
    let k = k.clamp(1, n);
    let size = n.div_ceil(k);
    let bounds: Vec<usize> = (0..=k).map(|c| (c * size).min(n)).collect();
    partition_wsssp_boundary_at(n, edges, weights, &bounds)
}

/// Build weighted-SSSP boundary shards from explicit contiguous boundaries. `weights[i]` is the weight of
/// `edges[i]` (undirected → applied to both directions). Non-positive/missing weights default to 1.0.
pub fn partition_wsssp_boundary_at(
    n: usize,
    edges: &[(usize, usize)],
    weights: &[f64],
    bounds: &[usize],
) -> Vec<BoundaryWShard> {
    if n == 0 || bounds.len() < 2 {
        return Vec::new();
    }
    let k = bounds.len() - 1;
    let owner = |v: usize| -> usize {
        match bounds.binary_search(&v) {
            Ok(c) => c.min(k - 1),
            Err(c) => c - 1,
        }
    };
    // raw[shard][owned local] = Vec<(global neighbour, weight)>
    let mut raw: Vec<Vec<Vec<(usize, f64)>>> = (0..k)
        .map(|c| vec![Vec::new(); bounds[c + 1] - bounds[c]])
        .collect();
    let mut ghost_sets: Vec<BTreeSet<usize>> = vec![BTreeSet::new(); k];
    let mut note = |shard: usize, node: usize, nbr: usize, w: f64| {
        let (lo, hi) = (bounds[shard], bounds[shard + 1]);
        raw[shard][node - lo].push((nbr, w));
        if nbr < lo || nbr >= hi {
            ghost_sets[shard].insert(nbr);
        }
    };
    for (i, &(u, v)) in edges.iter().enumerate() {
        if u < n && v < n && u != v {
            let w = weights.get(i).copied().filter(|&w| w > 0.0).unwrap_or(1.0);
            note(owner(u), u, v, w);
            note(owner(v), v, u, w);
        }
    }
    let mut shards = Vec::with_capacity(k);
    for c in 0..k {
        let (lo, hi) = (bounds[c], bounds[c + 1]);
        let owned = hi - lo;
        let ghosts: Vec<usize> = ghost_sets[c].iter().copied().collect();
        let ghost_idx: HashMap<usize, usize> =
            ghosts.iter().enumerate().map(|(i, &g)| (g, i)).collect();
        let adj: Vec<Vec<(usize, f64)>> = raw[c]
            .iter()
            .map(|nbrs| {
                nbrs.iter()
                    .map(|&(w, wt)| {
                        let li = if w >= lo && w < hi {
                            w - lo
                        } else {
                            owned + ghost_idx[&w]
                        };
                        (li, wt)
                    })
                    .collect()
            })
            .collect();
        shards.push(BoundaryWShard {
            lo,
            hi,
            ghosts,
            adj,
        });
    }
    shards
}

/// Distributed weighted single-source shortest path with a boundary-only halo (BSP Bellman-Ford relaxation:
/// `dist[v] = min(dist[v], min_{u~v} dist[u] + w(u,v))`). Only ghost DISTANCES (f64) cross shard boundaries.
/// Deterministic — shortest-path distances are unique, so the min-fixpoint is order-independent and exact vs
/// serial Dijkstra. Unreachable vertices stay `f64::INFINITY`. BFS is the special case `w ≡ 1`.
pub fn distributed_sssp_boundary(n: usize, shards: &[BoundaryWShard], source: usize) -> Vec<f64> {
    if n == 0 {
        return Vec::new();
    }
    let mut dist = vec![f64::INFINITY; n];
    if source < n {
        dist[source] = 0.0;
    }
    loop {
        let partials: Vec<(usize, Vec<f64>)> = shards
            .par_iter()
            .map(|sh| {
                let owned = sh.owned();
                let mut local_dist = vec![f64::INFINITY; owned + sh.ghosts.len()];
                local_dist[..owned].copy_from_slice(&dist[sh.lo..sh.hi]);
                for (i, &g) in sh.ghosts.iter().enumerate() {
                    local_dist[owned + i] = dist[g];
                }
                let mut out = vec![f64::INFINITY; owned];
                for (i, nbrs) in sh.adj.iter().enumerate() {
                    let mut m = local_dist[i];
                    for &(li, w) in nbrs {
                        let du = local_dist[li];
                        if du.is_finite() && du + w < m {
                            m = du + w;
                        }
                    }
                    out[i] = m;
                }
                (sh.lo, out)
            })
            .collect();
        let mut changed = false;
        let mut next = dist.clone();
        for (lo, local) in &partials {
            for (i, &dv) in local.iter().enumerate() {
                if dv < next[lo + i] {
                    next[lo + i] = dv;
                    changed = true;
                }
            }
        }
        dist = next;
        if !changed {
            break;
        }
    }
    dist
}

// ── Boundary-halo community detection by label propagation (CDLP) ──────────────────────────────────────────────
/// Distributed CDLP (LDBC Graphalytics community detection) with a boundary-only halo, over the undirected
/// CC shards. SYNCHRONOUS label propagation for a FIXED number of iterations (LDBC semantics — not run to a
/// fixpoint): each round every vertex adopts the label most frequent among its neighbours, ties broken by
/// the SMALLEST label id. Only ghost labels (u32) cross shard boundaries. Deterministic (synchronous update
/// from the previous round + deterministic tie-break) → identical to a single-graph CDLP. This is the LABEL-
/// VOTING shape (distinct from WCC's min-propagation): it proves the boundary-halo model covers it too.
pub fn distributed_cdlp_boundary(n: usize, shards: &[BoundaryCcShard], iters: usize) -> Vec<u32> {
    if n == 0 {
        return Vec::new();
    }
    let mut label: Vec<u32> = (0..n as u32).collect();
    for _ in 0..iters {
        let partials: Vec<(usize, Vec<u32>)> = shards
            .par_iter()
            .map(|sh| {
                let owned = sh.owned();
                let mut local_label = vec![0u32; owned + sh.ghosts.len()];
                local_label[..owned].copy_from_slice(&label[sh.lo..sh.hi]);
                for (i, &g) in sh.ghosts.iter().enumerate() {
                    local_label[owned + i] = label[g];
                }
                let mut out = vec![0u32; owned];
                for (i, nbrs) in sh.adj.iter().enumerate() {
                    if nbrs.is_empty() {
                        out[i] = local_label[i]; // isolated → keep own label
                        continue;
                    }
                    out[i] = most_frequent_label(nbrs.iter().map(|&li| local_label[li]));
                }
                (sh.lo, out)
            })
            .collect();
        // Synchronous: build the next global label vector wholesale from this round's partials.
        let mut next = label.clone();
        for (lo, local) in &partials {
            next[*lo..*lo + local.len()].copy_from_slice(local);
        }
        label = next;
    }
    label
}

/// The label appearing most often among `labels`, ties broken by the smallest label id (LDBC CDLP rule).
fn most_frequent_label(labels: impl Iterator<Item = u32>) -> u32 {
    let mut counts: HashMap<u32, usize> = HashMap::new();
    for l in labels {
        *counts.entry(l).or_insert(0) += 1;
    }
    // Max by count, then min by label id → deterministic.
    counts
        .into_iter()
        .fold(None, |best: Option<(u32, usize)>, (lab, cnt)| match best {
            Some((bl, bc)) if bc > cnt || (bc == cnt && bl <= lab) => Some((bl, bc)),
            _ => Some((lab, cnt)),
        })
        .map(|(lab, _)| lab)
        .unwrap_or(0)
}

// ── Boundary-halo local clustering coefficient (LCC) — the 2-hop kernel ────────────────────────────────────────
/// An LCC partition. Unlike the 1-hop kernels above, LCC needs each owned vertex to know the ADJACENCY of
/// its neighbours (to count edges among them), so a boundary vertex needs its ghost neighbours' neighbour
/// lists — 2-hop information. `adj` therefore holds the sorted global neighbour list of every owned vertex
/// AND every ghost. LCC is single-pass, so this heavier halo is exchanged ONCE at setup, not per superstep.
pub struct BoundaryLccShard {
    pub lo: usize,
    pub hi: usize,
    /// global id → sorted, deduped global neighbour ids, for every owned vertex and every ghost.
    pub adj: HashMap<usize, Vec<u32>>,
}

impl BoundaryLccShard {
    pub fn owned(&self) -> usize {
        self.hi - self.lo
    }
}

/// Range-partition into `k` LCC shards. Each shard carries its owned vertices' adjacency plus the adjacency
/// of every ghost (the 2-hop halo) — enough to count each owned vertex's triangles locally.
pub fn partition_lcc_boundary(
    n: usize,
    edges: &[(usize, usize)],
    k: usize,
) -> Vec<BoundaryLccShard> {
    if n == 0 {
        return Vec::new();
    }
    let k = k.clamp(1, n);
    let size = n.div_ceil(k);
    // Global undirected adjacency (sorted, deduped) — the ground truth we slice per shard.
    let mut gadj: Vec<Vec<u32>> = vec![Vec::new(); n];
    for &(u, v) in edges {
        if u < n && v < n && u != v {
            gadj[u].push(v as u32);
            gadj[v].push(u as u32);
        }
    }
    for a in gadj.iter_mut() {
        a.sort_unstable();
        a.dedup();
    }
    (0..k)
        .map(|c| {
            let lo = c * size;
            let hi = ((c + 1) * size).min(n);
            let mut adj: HashMap<usize, Vec<u32>> = HashMap::new();
            let mut ghosts: BTreeSet<usize> = BTreeSet::new();
            #[allow(clippy::needless_range_loop)]
            for v in lo..hi {
                adj.insert(v, gadj[v].clone());
                for &w in &gadj[v] {
                    let w = w as usize;
                    if w < lo || w >= hi {
                        ghosts.insert(w); // remote neighbour → its adjacency must come along (2-hop)
                    }
                }
            }
            for g in ghosts {
                adj.insert(g, gadj[g].clone());
            }
            BoundaryLccShard { lo, hi, adj }
        })
        .collect()
}

/// Count of common elements between two sorted, deduped slices (a linear merge).
fn sorted_intersection_count(a: &[u32], b: &[u32]) -> usize {
    let (mut i, mut j, mut c) = (0usize, 0usize, 0usize);
    while i < a.len() && j < b.len() {
        match a[i].cmp(&b[j]) {
            std::cmp::Ordering::Less => i += 1,
            std::cmp::Ordering::Greater => j += 1,
            std::cmp::Ordering::Equal => {
                c += 1;
                i += 1;
                j += 1;
            }
        }
    }
    c
}

/// Distributed local clustering coefficient with a boundary (2-hop) halo. Single pass: for each owned
/// vertex `v`, LCC(v) = edges-among-N(v) / C(deg,2), computed as `Σ_{a∈N(v)} |N(a) ∩ N(v)| / (deg·(deg−1))`
/// (each triangle edge counted twice → the deg·(deg−1) denominator). Vertices with degree < 2 get 0.
/// Deterministic and exact vs a single-graph LCC. The adjacency-carrying halo is why this is the "2-hop"
/// kernel — but being single-pass, it is exchanged once, not every superstep.
pub fn distributed_lcc_boundary(n: usize, shards: &[BoundaryLccShard]) -> Vec<f64> {
    if n == 0 {
        return Vec::new();
    }
    let partials: Vec<(usize, Vec<f64>)> = shards
        .par_iter()
        .map(|sh| {
            let mut out = vec![0.0f64; sh.owned()];
            for v in sh.lo..sh.hi {
                let nv = &sh.adj[&v];
                let d = nv.len();
                if d < 2 {
                    continue;
                }
                // Σ over neighbours a of |N(a) ∩ N(v)| — each edge among N(v) counted twice.
                let mut sum = 0usize;
                for &a in nv {
                    sum += sorted_intersection_count(&sh.adj[&(a as usize)], nv);
                }
                out[v - sh.lo] = sum as f64 / (d as f64 * (d as f64 - 1.0));
            }
            (sh.lo, out)
        })
        .collect();
    let mut lcc = vec![0.0f64; n];
    for (lo, local) in &partials {
        lcc[*lo..*lo + local.len()].copy_from_slice(local);
    }
    lcc
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{connected_components, pagerank, Kronecker};

    #[test]
    fn balanced_partition_is_a_bijection() {
        // mix must permute [0, 2^bits) exactly, and balanced_local/owner/to_global must round-trip — else
        // ownership loses or duplicates vertices in the distributed shuffle.
        for bits in [4u32, 8, 12, 16, 18] {
            let n = 1usize << bits;
            let k = 16;
            let mut seen = vec![false; n];
            for v in 0..n {
                let w = mix_bits(v, bits);
                assert!(w < n && !seen[w], "mix not a permutation at bits={bits}, v={v}");
                seen[w] = true;
                let c = balanced_owner(v, bits, k);
                let l = balanced_local(v, bits, k);
                assert_eq!(balanced_to_global(l, bits, k, c), v, "roundtrip failed bits={bits} v={v}");
            }
        }
    }

    #[test]
    fn balanced_partition_flattens_rmat_skew() {
        // The range partition hands shard 0 ~⅓ of a Graph500/RMAT graph's edges; the balanced partition
        // must keep every shard within ~1.2× of the mean.
        let (scale, ef, k) = (18u32, 16usize, 16usize);
        let (n, m) = (Kronecker::vertices(scale), Kronecker::edges(scale, ef));
        let bounds = range_bounds(n, k);
        let (mut range, mut balanced) = (vec![0usize; k], vec![0usize; k]);
        for (_u, v) in Kronecker::new(scale, ef, 0xB0A7) {
            range[owner_of(v, &bounds)] += 1;
            balanced[balanced_owner(v, scale, k)] += 1;
        }
        let mean = m as f64 / k as f64;
        let range_max = *range.iter().max().unwrap() as f64 / mean;
        let bal_max = *balanced.iter().max().unwrap() as f64 / mean;
        assert!(range_max > 3.0, "expected range partition to be badly skewed, got {range_max:.2}×");
        assert!(bal_max < 1.2, "balanced partition should be near-even, got {bal_max:.2}×");
    }

    /// Serial reference BFS (hop distance) for verification.
    fn serial_bfs(n: usize, edges: &[(usize, usize)], source: usize) -> Vec<u32> {
        let mut adj: Vec<Vec<usize>> = vec![Vec::new(); n];
        for &(u, v) in edges {
            if u < n && v < n && u != v {
                adj[u].push(v);
                adj[v].push(u);
            }
        }
        let mut dist = vec![u32::MAX; n];
        let mut q = std::collections::VecDeque::new();
        dist[source] = 0;
        q.push_back(source);
        while let Some(u) = q.pop_front() {
            for &w in &adj[u] {
                if dist[w] == u32::MAX {
                    dist[w] = dist[u] + 1;
                    q.push_back(w);
                }
            }
        }
        dist
    }

    #[test]
    fn distributed_generation_reproduces_centralized_partition() {
        // THE #12 invariant: each worker independently generates its OWN edge slice (via the seekable
        // Kronecker) and routes each edge to the shard owning its target vertex — and the resulting per-shard
        // in-edge partition is BIT-IDENTICAL to a coordinator range-partitioning the whole graph. If this
        // holds, the distributed engine (no node holds the whole graph) computes the same verified answer.
        let scale = 12u32;
        let ef = 8usize;
        let seed = 0xB0A7u64;
        let k = 8usize;
        let n = Kronecker::vertices(scale);
        let m = Kronecker::edges(scale, ef);
        let bounds = range_bounds(n, k);

        // Centralized: the whole graph, range-partitioned by target vertex.
        let mut central: Vec<BTreeSet<(usize, usize)>> = vec![BTreeSet::new(); k];
        for e in Kronecker::new(scale, ef, seed) {
            central[owner_of(e.1, &bounds)].insert(e);
        }

        // Distributed: every worker generates ONLY its edge slice, routes each edge to the owner. No worker
        // ever sees the whole graph; the slices are disjoint and cover [0, m).
        let mut dist: Vec<BTreeSet<(usize, usize)>> = vec![BTreeSet::new(); k];
        for c in 0..k {
            let start = c * m / k;
            let count = (c + 1) * m / k - start;
            for e in Kronecker::slice(scale, seed, start, count) {
                dist[owner_of(e.1, &bounds)].insert(e);
            }
        }

        assert_eq!(
            central, dist,
            "distributed generation+routing diverged from centralized partition"
        );
    }

    #[test]
    fn boundary_halo_pagerank_matches_serial_exactly() {
        // A hub-heavy RMAT graph: ghost sets are non-trivial, so this exercises the halo path for real.
        let scale = 8u32; // 256 vertices
        let n = Kronecker::vertices(scale);
        let edges: Vec<(usize, usize)> = Kronecker::new(scale, 8, 0xBEEF).collect();

        let serial = pagerank(n, &edges, 0.85, 100, 1e-10);
        let (shards, out_deg) = partition_edges_boundary(n, &edges, 8);
        let dist = distributed_pagerank_boundary(n, &shards, &out_deg, 0.85, 100, 1e-10);

        assert_eq!(serial.len(), dist.len());
        let max_delta = serial
            .iter()
            .zip(&dist)
            .map(|(a, b)| (a - b).abs())
            .fold(0.0f64, f64::max);
        // Same fixed point, not "close": the halo shrinks, the numbers do not move.
        assert!(
            max_delta < 1e-12,
            "max|Δ| = {max_delta:e} — halo changed the answer"
        );
    }

    #[test]
    fn delta_halo_is_exact_at_eps_zero_and_saves_bytes_when_converging() {
        // Hub-heavy RMAT → real ghost sets. Run to a tight tolerance so many vertices freeze late.
        let scale = 10u32; // 1024 vertices
        let n = Kronecker::vertices(scale);
        let edges: Vec<(usize, usize)> = Kronecker::new(scale, 8, 0xDE17).collect();
        let (shards, out_deg) = partition_edges_boundary(n, &edges, 8);

        // eps=0: the residual halo is BIT-IDENTICAL to the dense boundary halo (a cache refreshed to the
        // exact value == reading it directly). HONEST: it does NOT save bytes on PageRank — f64 ranks keep
        // wiggling in their low bits every superstep, so almost nothing freezes bit-exactly and 12 B sparse
        // pairs cost MORE than 8 B dense. The saving needs a threshold (below).
        let exact = distributed_pagerank_boundary(n, &shards, &out_deg, 0.85, 200, 1e-12);
        let (delta0, _s0) =
            distributed_pagerank_boundary_delta(n, &shards, &out_deg, 0.85, 200, 1e-12, 0.0);
        assert_eq!(
            delta0, exact,
            "eps=0 residual halo must equal the dense halo exactly"
        );

        // Thresholded eps: THIS is where the wire saving lives. Ghosts moving < eps stop being sent, so the
        // late supersteps ship almost nothing — for a bounded O(eps) perturbation of the answer.
        let eps = 1e-9;
        let (delta1, s1) =
            distributed_pagerank_boundary_delta(n, &shards, &out_deg, 0.85, 200, 1e-12, eps);
        let maxd = exact
            .iter()
            .zip(&delta1)
            .map(|(a, b)| (a - b).abs())
            .fold(0.0f64, f64::max);
        assert!(
            maxd < 1e-5,
            "delta_eps={eps} perturbed the answer too much: max|Δ| {maxd:e}"
        );
        assert!(
            s1.delta_bytes < s1.dense_bytes,
            "thresholded residual halo must beat dense: delta {}B not < dense {}B",
            s1.delta_bytes,
            s1.dense_bytes
        );
        // Deterministic run-to-run.
        assert_eq!(
            delta1,
            distributed_pagerank_boundary_delta(n, &shards, &out_deg, 0.85, 200, 1e-12, eps).0
        );
    }

    #[test]
    fn boundary_halo_is_deterministic_across_runs() {
        let n = Kronecker::vertices(8);
        let edges: Vec<(usize, usize)> = Kronecker::new(8, 8, 7).collect();
        let (s1, d1) = partition_edges_boundary(n, &edges, 8);
        let (s2, d2) = partition_edges_boundary(n, &edges, 8);
        // Same ghost sets, same order.
        for (a, b) in s1.iter().zip(&s2) {
            assert_eq!(a.ghosts, b.ghosts);
        }
        let r1 = distributed_pagerank_boundary(n, &s1, &d1, 0.85, 50, 1e-10);
        let r2 = distributed_pagerank_boundary(n, &s2, &d2, 0.85, 50, 1e-10);
        assert_eq!(r1, r2);
    }

    #[test]
    fn boundary_halo_beats_full_broadcast_on_local_graph() {
        // A ring has locality: each node's only in-neighbour is its predecessor, so a contiguous range
        // partition leaves exactly ONE ghost per shard boundary. The boundary halo should be a tiny
        // fraction of the k·n full-broadcast cost.
        let n = 4096usize;
        let edges: Vec<(usize, usize)> = (0..n).map(|i| (i, (i + 1) % n)).collect();
        let k = 16usize;
        let (shards, _out) = partition_edges_boundary(n, &edges, k);
        let halo = total_halo_bytes(&shards);
        let full_broadcast = k * n * 8;
        // Ring → ~1 ghost per shard; halo is orders of magnitude under the full broadcast.
        assert!(
            halo * 100 < full_broadcast,
            "boundary halo {halo}B not <1% of full broadcast {full_broadcast}B"
        );
    }

    #[test]
    fn boundary_halo_cc_matches_serial_exactly() {
        // Two disjoint RMAT blobs offset into disjoint id ranges → a real multi-component graph the
        // boundary label halo must reconcile across shards.
        let half = Kronecker::vertices(8); // 256
        let n = 2 * half;
        let mut edges: Vec<(usize, usize)> = Kronecker::new(8, 6, 1).collect();
        edges.extend(Kronecker::new(8, 6, 2).map(|(u, v)| (u + half, v + half)));

        let serial = connected_components(n, &edges);
        let shards = partition_cc_boundary(n, &edges, 8);
        let dist = distributed_cc_boundary(n, &shards);
        assert_eq!(serial, dist, "boundary-halo CC diverged from serial");
    }

    #[test]
    fn boundary_halo_sssp_matches_serial_dijkstra() {
        // Weighted RMAT: deterministic positive weights from a hash of (u,v). Verify distributed SSSP
        // against serial Dijkstra (the ground truth for weighted shortest paths).
        let n = Kronecker::vertices(9); // 512
        let edges: Vec<(usize, usize)> = Kronecker::new(9, 8, 0x5DEE).collect();
        let weights: Vec<f64> = edges
            .iter()
            .map(|&(u, v)| 1.0 + ((u.wrapping_mul(2654435761) ^ v) % 16) as f64)
            .collect();
        let source = 0;

        // Serial Dijkstra reference (undirected).
        let mut adj: Vec<Vec<(usize, f64)>> = vec![Vec::new(); n];
        for (i, &(u, v)) in edges.iter().enumerate() {
            if u != v {
                adj[u].push((v, weights[i]));
                adj[v].push((u, weights[i]));
            }
        }
        // Dijkstra with a min-heap keyed on the f64 bit pattern (monotonic for non-negative distances).
        let mut ref_dist = vec![f64::INFINITY; n];
        ref_dist[source] = 0.0;
        let mut heap = std::collections::BinaryHeap::new();
        heap.push((std::cmp::Reverse(0.0f64.to_bits()), source));
        while let Some((std::cmp::Reverse(bits), u)) = heap.pop() {
            let du = f64::from_bits(bits);
            if du > ref_dist[u] {
                continue;
            }
            for &(w, wt) in &adj[u] {
                let nd = du + wt;
                if nd < ref_dist[w] {
                    ref_dist[w] = nd;
                    heap.push((std::cmp::Reverse(nd.to_bits()), w));
                }
            }
        }

        let shards = partition_wsssp_boundary(n, &edges, &weights, 8);
        let dist = distributed_sssp_boundary(n, &shards, source);
        let maxd = ref_dist
            .iter()
            .zip(&dist)
            .map(|(a, b)| {
                if a.is_infinite() && b.is_infinite() {
                    0.0
                } else {
                    (a - b).abs()
                }
            })
            .fold(0.0f64, f64::max);
        assert!(
            maxd < 1e-9,
            "boundary SSSP diverged from Dijkstra: max|Δ| {maxd:e}"
        );
    }

    #[test]
    fn boundary_halo_lcc_matches_serial_exactly() {
        let n = Kronecker::vertices(9); // 512
        let edges: Vec<(usize, usize)> = Kronecker::new(9, 8, 0x1CCC).collect();

        // Serial LCC reference: edges among each vertex's neighbours / C(deg,2).
        let mut g: Vec<std::collections::BTreeSet<usize>> = vec![Default::default(); n];
        for &(u, v) in &edges {
            if u != v {
                g[u].insert(v);
                g[v].insert(u);
            }
        }
        let mut ref_lcc = vec![0.0f64; n];
        for v in 0..n {
            let nv: Vec<usize> = g[v].iter().copied().collect();
            let d = nv.len();
            if d < 2 {
                continue;
            }
            let mut edges_among = 0usize;
            for i in 0..d {
                for j in (i + 1)..d {
                    if g[nv[i]].contains(&nv[j]) {
                        edges_among += 1;
                    }
                }
            }
            ref_lcc[v] = 2.0 * edges_among as f64 / (d as f64 * (d as f64 - 1.0));
        }

        let shards = partition_lcc_boundary(n, &edges, 8);
        let lcc = distributed_lcc_boundary(n, &shards);
        let maxd = ref_lcc
            .iter()
            .zip(&lcc)
            .map(|(a, b)| (a - b).abs())
            .fold(0.0f64, f64::max);
        assert!(
            maxd < 1e-12,
            "boundary LCC diverged from serial: max|Δ| {maxd:e}"
        );
    }

    #[test]
    fn boundary_halo_cdlp_matches_serial_exactly() {
        let n = Kronecker::vertices(9); // 512
        let edges: Vec<(usize, usize)> = Kronecker::new(9, 8, 0xC0DE).collect();
        let iters = 10;

        // Serial synchronous CDLP reference (same tie-break: most frequent, then smallest label).
        let mut adj: Vec<Vec<usize>> = vec![Vec::new(); n];
        for &(u, v) in &edges {
            if u != v {
                adj[u].push(v);
                adj[v].push(u);
            }
        }
        let mut label: Vec<u32> = (0..n as u32).collect();
        for _ in 0..iters {
            let mut next = label.clone();
            for v in 0..n {
                if adj[v].is_empty() {
                    continue;
                }
                next[v] = super::most_frequent_label(adj[v].iter().map(|&w| label[w]));
            }
            label = next;
        }

        let shards = partition_cc_boundary(n, &edges, 8);
        let dist = distributed_cdlp_boundary(n, &shards, iters);
        assert_eq!(label, dist, "boundary-halo CDLP diverged from serial");
    }

    #[test]
    fn boundary_halo_bfs_matches_serial_exactly() {
        // One connected RMAT blob so most vertices are reachable → a real multi-hop BFS across shards.
        let n = Kronecker::vertices(9); // 512
        let edges: Vec<(usize, usize)> = Kronecker::new(9, 8, 0xB5).collect();
        let source = 0;
        let serial = serial_bfs(n, &edges, source);
        let shards = partition_cc_boundary(n, &edges, 8);
        let dist = distributed_bfs_boundary(n, &shards, source);
        assert_eq!(serial, dist, "boundary-halo BFS diverged from serial");
    }

    #[test]
    fn boundary_cc_halo_beats_full_broadcast_on_ring() {
        let n = 4096usize;
        let edges: Vec<(usize, usize)> = (0..n).map(|i| (i, (i + 1) % n)).collect();
        let k = 16usize;
        let shards = partition_cc_boundary(n, &edges, k);
        let halo = total_cc_halo_bytes(&shards);
        let full_broadcast = k * n * 4; // u32 labels
        assert!(
            halo * 50 < full_broadcast,
            "CC boundary halo {halo}B not «  full broadcast {full_broadcast}B"
        );
    }
}
