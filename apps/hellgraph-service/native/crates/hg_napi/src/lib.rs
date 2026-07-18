//! hg_napi — Node/N-API binding for the benchmarked hg_analytics CSR kernel.
//!
//! This is the SAME Rust kernel measured in hellgraph-bench (PreparedGraph CSR + parallel PageRank / WCC),
//! exposed to the Node hellgraph-service so the SHIPPING product runs the benchmarked code — not a separate
//! single-threaded TS re-implementation. Edges are passed as parallel from/to index arrays (dense 0..n ids).
use hg_analytics::{bfs_parallel, cdlp_parallel, connected_components_parallel, sssp_parallel, PreparedGraph};
use napi_derive::napi;

fn zip_edges(from: &[u32], to: &[u32]) -> Vec<(usize, usize)> {
    from.iter().zip(to.iter()).map(|(&a, &b)| (a as usize, b as usize)).collect()
}

/// PageRank over the CSR kernel. Returns one score per node (index-aligned to 0..node_count).
#[napi]
pub fn pagerank(node_count: u32, edges_from: Vec<u32>, edges_to: Vec<u32>, damping: f64, iters: u32, tol: f64) -> Vec<f64> {
    let edges = zip_edges(&edges_from, &edges_to);
    PreparedGraph::build(node_count as usize, &edges).pagerank(damping, iters as usize, tol)
}

/// Weakly-connected components (parallel union-find). Returns a component id per node.
#[napi]
pub fn connected_components(node_count: u32, edges_from: Vec<u32>, edges_to: Vec<u32>) -> Vec<u32> {
    let edges = zip_edges(&edges_from, &edges_to);
    connected_components_parallel(node_count as usize, &edges)
}

/// BFS from `src` — level-synchronous parallel. Returns hop distance per node (u32::MAX = unreached).
#[napi]
pub fn bfs(node_count: u32, edges_from: Vec<u32>, edges_to: Vec<u32>, src: u32) -> Vec<u32> {
    let edges = zip_edges(&edges_from, &edges_to);
    bfs_parallel(node_count as usize, &edges, src as usize)
}

/// SSSP from `src` — parallel label-correcting (atomic-min over f64). Returns weighted distance per node
/// (f64::INFINITY = unreached). `weights` is edge-aligned to (edges_from, edges_to).
#[napi]
pub fn sssp(node_count: u32, edges_from: Vec<u32>, edges_to: Vec<u32>, weights: Vec<f64>, src: u32) -> Vec<f64> {
    let edges = zip_edges(&edges_from, &edges_to);
    sssp_parallel(node_count as usize, &edges, &weights, src as usize)
}

/// CDLP — community detection by label propagation (LDBC in∪out multiset), `iters` sweeps. One label per node.
#[napi]
pub fn cdlp(node_count: u32, edges_from: Vec<u32>, edges_to: Vec<u32>, iters: u32) -> Vec<u32> {
    let edges = zip_edges(&edges_from, &edges_to);
    cdlp_parallel(node_count as usize, &edges, iters as usize)
}

/// Identifies the kernel so the service can log which analytics backend is live.
#[napi]
pub fn backend() -> String {
    "hg_analytics-rust (benchmarked CSR kernel)".to_string()
}
