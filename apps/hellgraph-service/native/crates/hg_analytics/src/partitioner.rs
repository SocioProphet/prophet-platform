//! partitioner — deterministic streaming edge-cut partitioners (Fennel, LDG).
//!
//! A range partition ignores graph structure, so a hub's neighbours scatter across every shard and the
//! boundary halo stays fat. A streaming edge-cut partitioner instead places each vertex on the shard where
//! its already-placed neighbours live (minus a balance penalty), which minimises the cross-shard edge cut
//! and therefore the ghost halo the cluster must exchange each superstep. This runs ONCE at setup.
//!
//! Both are deterministic: vertices are streamed in id order, and ties break to the lower shard id (then
//! the emptier shard), so the assignment is identical on every machine and every run — a product property.
//!
//! - Fennel (Tsourakakis et al.): maximise `|N(v)∩p| − α·γ·|p|^(γ−1)`, γ=1.5, α=m·k^(γ−1)/n^γ.
//! - LDG (Stanton & Kliot): maximise `|N(v)∩p| · (1 − |p|/capacity)`.
//!
//! `relabel_contiguous` turns an assignment into the (remapped edges, block boundaries) a boundary-halo
//! PageRank consumes via `partition_edges_boundary_at` — so a smart partition drives the exact same run.

/// Build an undirected adjacency (both directions) — the neighbourhood the scorers read. O(n+m).
fn undirected_adj(n: usize, edges: &[(usize, usize)]) -> Vec<Vec<usize>> {
    let mut adj: Vec<Vec<usize>> = vec![Vec::new(); n];
    for &(u, v) in edges {
        if u < n && v < n && u != v {
            adj[u].push(v);
            adj[v].push(u);
        }
    }
    adj
}

/// Pick the best shard for `cnt` (neighbour counts per shard) under `score`, breaking ties deterministically
/// to the lower shard id, then to the emptier shard (keeps balance when neighbour signal is absent).
fn pick_best(k: usize, size: &[usize], score: impl Fn(usize) -> f64) -> usize {
    let mut best = 0usize;
    let mut best_score = f64::MIN;
    for p in 0..k {
        let s = score(p);
        if s > best_score || (s == best_score && size[p] < size[best]) {
            best_score = s;
            best = p;
        }
    }
    best
}

/// Fennel streaming partition → `part[v]` = shard id in `0..k`. Deterministic, balanced by construction.
pub fn fennel_partition(n: usize, edges: &[(usize, usize)], k: usize) -> Vec<usize> {
    if n == 0 {
        return Vec::new();
    }
    let k = k.clamp(1, n);
    let adj = undirected_adj(n, edges);
    let gamma = 1.5f64;
    let m = edges.len().max(1) as f64;
    let alpha = m * (k as f64).powf(gamma - 1.0) / (n as f64).powf(gamma);
    let mut part = vec![usize::MAX; n];
    let mut size = vec![0usize; k];
    let mut cnt = vec![0f64; k];
    let mut touched: Vec<usize> = Vec::new();
    for v in 0..n {
        touched.clear();
        for &w in &adj[v] {
            let p = part[w];
            if p != usize::MAX {
                if cnt[p] == 0.0 {
                    touched.push(p);
                }
                cnt[p] += 1.0;
            }
        }
        let best = pick_best(k, &size, |p| {
            cnt[p] - alpha * gamma * (size[p] as f64).powf(gamma - 1.0)
        });
        part[v] = best;
        size[best] += 1;
        for &p in &touched {
            cnt[p] = 0.0;
        }
    }
    part
}

/// LDG (Linear Deterministic Greedy) streaming partition → `part[v]`. Capacity has 5% slack over `n/k`.
pub fn ldg_partition(n: usize, edges: &[(usize, usize)], k: usize) -> Vec<usize> {
    if n == 0 {
        return Vec::new();
    }
    let k = k.clamp(1, n);
    let adj = undirected_adj(n, edges);
    let capacity = (n as f64 / k as f64 * 1.05).ceil().max(1.0);
    let mut part = vec![usize::MAX; n];
    let mut size = vec![0usize; k];
    let mut cnt = vec![0f64; k];
    let mut touched: Vec<usize> = Vec::new();
    for v in 0..n {
        touched.clear();
        for &w in &adj[v] {
            let p = part[w];
            if p != usize::MAX {
                if cnt[p] == 0.0 {
                    touched.push(p);
                }
                cnt[p] += 1.0;
            }
        }
        let best = pick_best(k, &size, |p| {
            let slack = 1.0 - size[p] as f64 / capacity;
            cnt[p] * slack.max(0.0)
        });
        part[v] = best;
        size[best] += 1;
        for &p in &touched {
            cnt[p] = 0.0;
        }
    }
    part
}

/// Count edges whose endpoints land in different shards — the edge cut. Lower = smaller boundary halo.
pub fn edge_cut(part: &[usize], edges: &[(usize, usize)]) -> usize {
    edges
        .iter()
        .filter(|&&(u, v)| u < part.len() && v < part.len() && u != v && part[u] != part[v])
        .count()
}

/// (min, max) shard size for a partition — the balance. A good partition keeps max/min close to 1.
pub fn balance(part: &[usize], k: usize) -> (usize, usize) {
    let mut size = vec![0usize; k.max(1)];
    for &p in part {
        if p < size.len() {
            size[p] += 1;
        }
    }
    let min = size.iter().copied().min().unwrap_or(0);
    let max = size.iter().copied().max().unwrap_or(0);
    (min, max)
}

/// Relabel vertices so each shard owns a CONTIGUOUS id block (ordered by shard id, then original id →
/// deterministic). Returns `(remapped_edges, block_boundaries, perm)` where `perm[old] = new`. Feed
/// `remapped_edges` + `block_boundaries` to `partition_edges_boundary_at` to run the boundary-halo
/// PageRank on the edge-cut-minimised layout.
pub fn relabel_contiguous(
    n: usize,
    part: &[usize],
    k: usize,
    edges: &[(usize, usize)],
) -> (Vec<(usize, usize)>, Vec<usize>, Vec<usize>) {
    if n == 0 {
        return (Vec::new(), vec![0], Vec::new());
    }
    let k = k.max(1);
    let mut order: Vec<usize> = (0..n).collect();
    order.sort_by_key(|&v| (part[v], v)); // stable, contiguous blocks per shard
    let mut perm = vec![0usize; n];
    for (newid, &old) in order.iter().enumerate() {
        perm[old] = newid;
    }
    let remapped: Vec<(usize, usize)> = edges.iter().map(|&(u, v)| (perm[u], perm[v])).collect();
    let mut size = vec![0usize; k];
    for &p in part {
        size[p] += 1;
    }
    let mut bounds = vec![0usize; k + 1];
    for c in 0..k {
        bounds[c + 1] = bounds[c] + size[c];
    }
    (remapped, bounds, perm)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{distributed_pagerank_boundary, pagerank, partition_edges_boundary_at, Kronecker};

    #[test]
    fn fennel_beats_range_on_edge_cut() {
        let n = Kronecker::vertices(12); // 4096
        let edges: Vec<(usize, usize)> = Kronecker::new(12, 8, 0xCAFE).collect();
        let k = 16;

        // Range partition = contiguous equal blocks.
        let size = n.div_ceil(k);
        let range: Vec<usize> = (0..n).map(|v| (v / size).min(k - 1)).collect();

        let fennel = fennel_partition(n, &edges, k);
        let cut_range = edge_cut(&range, &edges);
        let cut_fennel = edge_cut(&fennel, &edges);
        assert!(
            cut_fennel < cut_range,
            "fennel cut {cut_fennel} should beat range cut {cut_range}"
        );
        // It must stay in the same ballpark (Fennel trades some balance for cut on power-law RMAT —
        // a giant hub's neighbourhood pulls together — so allow up to 3× ideal here).
        let (_min, max) = balance(&fennel, k);
        assert!(
            max <= 3 * n / k,
            "fennel imbalanced: max shard {max} vs ideal {}",
            n / k
        );
    }

    #[test]
    fn partitioners_are_deterministic() {
        let n = Kronecker::vertices(11);
        let edges: Vec<(usize, usize)> = Kronecker::new(11, 8, 3).collect();
        assert_eq!(
            fennel_partition(n, &edges, 8),
            fennel_partition(n, &edges, 8)
        );
        assert_eq!(ldg_partition(n, &edges, 8), ldg_partition(n, &edges, 8));
    }

    #[test]
    fn relabelled_partition_runs_boundary_pagerank_exactly() {
        // A smart partition, relabelled to contiguous blocks, must produce the SAME PageRank scores as
        // the original graph (up to the vertex permutation) — the partition changes layout, not answers.
        let n = Kronecker::vertices(10); // 1024
        let edges: Vec<(usize, usize)> = Kronecker::new(10, 8, 0xABCD).collect();
        let k = 8;
        let part = fennel_partition(n, &edges, k);
        let (remapped, bounds, perm) = relabel_contiguous(n, &part, k, &edges);

        let serial = pagerank(n, &edges, 0.85, 60, 1e-12);
        let (shards, out_deg) = partition_edges_boundary_at(n, &remapped, &bounds);
        let dist = distributed_pagerank_boundary(n, &shards, &out_deg, 0.85, 60, 1e-12);

        // Compare original vertex v (serial) against its relabelled slot perm[v] (dist).
        let max_delta = (0..n)
            .map(|v| (serial[v] - dist[perm[v]]).abs())
            .fold(0.0f64, f64::max);
        assert!(
            max_delta < 1e-12,
            "relabel changed the answer: max|Δ| = {max_delta:e}"
        );
    }
}
