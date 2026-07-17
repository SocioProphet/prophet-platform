//! cc — connected components via label propagation, single-graph AND distributed over sharded
//! partitions. Proves the partition-native BSP model (only an O(n) label halo crosses shard
//! boundaries; the O(E) edges stay sovereign per participant) is NOT PageRank-specific — it
//! generalizes to the whole class of vertex-centric graph algorithms.

use rayon::prelude::*;

/// Single-graph connected components (undirected) via min-label propagation. Deterministic — each
/// node ends labelled with the smallest node-id in its component.
pub fn connected_components(n: usize, edges: &[(usize, usize)]) -> Vec<u32> {
    if n == 0 {
        return Vec::new();
    }
    let mut adj: Vec<Vec<u32>> = vec![Vec::new(); n];
    for &(u, v) in edges {
        if u < n && v < n && u != v {
            adj[u].push(v as u32);
            adj[v].push(u as u32);
        }
    }
    let mut label: Vec<u32> = (0..n as u32).collect();
    loop {
        let mut changed = false;
        for v in 0..n {
            let mut m = label[v];
            for &u in &adj[v] {
                if label[u as usize] < m {
                    m = label[u as usize];
                }
            }
            if m < label[v] {
                label[v] = m;
                changed = true;
            }
        }
        if !changed {
            break;
        }
    }
    label
}

/// A CC shard: owned node range [lo, hi) + the UNDIRECTED adjacency of owned nodes (neighbours may
/// be remote — their label is read from the exchanged halo). A sovereign log = one of these.
pub struct CcShard {
    pub lo: usize,
    pub hi: usize,
    pub adj: Vec<Vec<u32>>,
}

/// Range-partition the undirected graph into `k` CC shards.
pub fn partition_undirected(n: usize, edges: &[(usize, usize)], k: usize) -> Vec<CcShard> {
    if n == 0 {
        return Vec::new();
    }
    let k = k.clamp(1, n);
    let size = n.div_ceil(k);
    let mut shards: Vec<CcShard> = (0..k)
        .map(|c| {
            let lo = c * size;
            let hi = ((c + 1) * size).min(n);
            CcShard {
                lo,
                hi,
                adj: vec![Vec::new(); hi - lo],
            }
        })
        .collect();
    for &(u, v) in edges {
        if u < n && v < n && u != v {
            let (cu, cv) = (u / size, v / size);
            let (ul, vl) = (u - shards[cu].lo, v - shards[cv].lo);
            shards[cu].adj[ul].push(v as u32);
            shards[cv].adj[vl].push(u as u32);
        }
    }
    shards
}

/// Distributed connected components (BSP): each superstep every shard recomputes its OWNED nodes'
/// labels in parallel from the exchanged O(n) label halo; disjoint owned ranges are gathered;
/// iterate to a global fixpoint. Only labels cross shard boundaries — edges stay sovereign.
/// Deterministic (min propagation, disjoint gather); reaches the same fixpoint as single-graph.
pub fn distributed_connected_components(n: usize, shards: &[CcShard]) -> Vec<u32> {
    if n == 0 {
        return Vec::new();
    }
    let mut label: Vec<u32> = (0..n as u32).collect();
    loop {
        let partials: Vec<(usize, Vec<u32>)> = shards
            .par_iter()
            .map(|sh| {
                let mut local = vec![0u32; sh.hi - sh.lo];
                for (i, nbrs) in sh.adj.iter().enumerate() {
                    let mut m = label[sh.lo + i];
                    for &u in nbrs {
                        if label[u as usize] < m {
                            m = label[u as usize];
                        }
                    }
                    local[i] = m;
                }
                (sh.lo, local)
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
