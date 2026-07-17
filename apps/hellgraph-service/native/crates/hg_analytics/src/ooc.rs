//! ooc — out-of-core CSR: the O(E) graph structure lives in a memory-mapped file (paged by the OS),
//! so only O(n) working vectors are heap-resident. This breaks the "the graph must fit in RAM"
//! ceiling — the #1 real gap vs centralized in-memory engines. PageRank runs DIRECTLY over the
//! mapping (edges are read from disk-backed pages, never materialized into a heap Vec).
//!
//! File layout (native-endian, naturally aligned; the mmap base is page-aligned):
//!   [n: u64, m: u64] header · offsets: (n+1) × u64 · in_neighbors: m × u32 · out_deg: n × u32
//! `offsets`/`in_neighbors` are the in-edge CSR (pull PageRank reads in-neighbours per node).

use memmap2::{Mmap, MmapMut};
use rayon::prelude::*;
use std::fs::{File, OpenOptions};
use std::io::{self, BufWriter, Write};
use std::path::Path;

/// Build the out-of-core CSR from a re-iterable edge STREAM using only O(n) heap — it never holds all
/// edges, so you can INGEST a graph larger than RAM (not just query one). Two streaming passes:
/// (1) count degrees → offsets; (2) place in-neighbours via random writes into the disk-backed
/// (mmap'd) neighbours region. `edges` is invoked twice and MUST yield the same stream both times.
/// Produces a byte-identical file to `write_csr` (verified in tests).
pub fn write_csr_streaming<I, F>(path: &Path, n: usize, edges: F) -> io::Result<()>
where
    I: Iterator<Item = (usize, usize)>,
    F: Fn() -> I,
{
    let mut in_deg = vec![0u64; n];
    let mut out_deg = vec![0u32; n];
    for (u, v) in edges() {
        if u < n && v < n {
            in_deg[v] += 1;
            out_deg[u] += 1;
        }
    }
    let mut offsets = vec![0u64; n + 1];
    for v in 0..n {
        offsets[v + 1] = offsets[v] + in_deg[v];
    }
    drop(in_deg);
    let m = offsets[n] as usize;

    let (header, off_bytes, nbr_bytes, deg_bytes) = (16, (n + 1) * 8, m * 4, n * 4);
    let (off_start, nbr_start, deg_start) =
        (header, header + off_bytes, header + off_bytes + nbr_bytes);
    let total = header + off_bytes + nbr_bytes + deg_bytes;

    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(true)
        .open(path)?;
    file.set_len(total as u64)?;
    // SAFETY: exclusive writable map of a freshly-sized file we own.
    let mut mmap = unsafe { MmapMut::map_mut(&file)? };
    mmap[0..8].copy_from_slice(bytemuck::bytes_of(&(n as u64)));
    mmap[8..16].copy_from_slice(bytemuck::bytes_of(&(m as u64)));
    mmap[off_start..off_start + off_bytes].copy_from_slice(bytemuck::cast_slice(&offsets));
    mmap[deg_start..deg_start + deg_bytes].copy_from_slice(bytemuck::cast_slice(&out_deg));

    // Pass 2: random-write in-neighbours into the disk-backed region (O(n) cursor heap only).
    let mut cursor: Vec<u64> = offsets.clone();
    {
        let nbr: &mut [u32] = bytemuck::cast_slice_mut(&mut mmap[nbr_start..nbr_start + nbr_bytes]);
        for (u, v) in edges() {
            if u < n && v < n {
                nbr[cursor[v] as usize] = u as u32;
                cursor[v] += 1;
            }
        }
    }
    mmap.flush()
}

/// Serialize the in-edge CSR of a graph to `path` (ready to mmap). O(n+m) temp heap during build,
/// but the resulting file is what gets processed out-of-core.
pub fn write_csr(path: &Path, n: usize, edges: &[(usize, usize)]) -> io::Result<()> {
    let mut in_deg = vec![0u64; n];
    let mut out_deg = vec![0u32; n];
    for &(u, v) in edges {
        if u < n && v < n {
            in_deg[v] += 1;
            out_deg[u] += 1;
        }
    }
    let mut offsets = vec![0u64; n + 1];
    for v in 0..n {
        offsets[v + 1] = offsets[v] + in_deg[v];
    }
    let m = offsets[n] as usize;
    let mut cursor = offsets.clone();
    let mut in_nbr = vec![0u32; m];
    for &(u, v) in edges {
        if u < n && v < n {
            in_nbr[cursor[v] as usize] = u as u32;
            cursor[v] += 1;
        }
    }
    let mut w = BufWriter::new(File::create(path)?);
    w.write_all(bytemuck::cast_slice(&[n as u64, m as u64]))?;
    w.write_all(bytemuck::cast_slice(&offsets))?;
    w.write_all(bytemuck::cast_slice(&in_nbr))?;
    w.write_all(bytemuck::cast_slice(&out_deg))?;
    w.flush()
}

/// Bucketed (external-memory) CSR builder — the fully-SEQUENTIAL-I/O ingest for a truly larger-than-
/// RAM graph. Destination nodes are split into `num_buckets` contiguous ranges; the neighbours region
/// is emitted one bucket at a time, in order, so ALL output writes are sequential (no random-write
/// page-thrash like the mmap `write_csr_streaming`). Peak heap is O(n) + O(m / num_buckets) — the
/// per-bucket neighbour buffer — independent of total edge count. `edges` is streamed once per bucket
/// (cheap for a generator; sequential re-read for a file). Byte-identical output to `write_csr`.
pub fn write_csr_bucketed<I, F>(
    path: &Path,
    n: usize,
    edges: F,
    num_buckets: usize,
) -> io::Result<()>
where
    I: Iterator<Item = (usize, usize)>,
    F: Fn() -> I,
{
    let buckets = num_buckets.clamp(1, n.max(1));
    let mut in_deg = vec![0u64; n];
    let mut out_deg = vec![0u32; n];
    for (u, v) in edges() {
        if u < n && v < n {
            in_deg[v] += 1;
            out_deg[u] += 1;
        }
    }
    let mut offsets = vec![0u64; n + 1];
    for v in 0..n {
        offsets[v + 1] = offsets[v] + in_deg[v];
    }
    drop(in_deg);
    let m = offsets[n] as usize;

    let mut w = BufWriter::new(File::create(path)?);
    w.write_all(bytemuck::cast_slice(&[n as u64, m as u64]))?;
    w.write_all(bytemuck::cast_slice(&offsets))?;

    // Neighbours, emitted bucket-by-bucket in destination order → sequential writes.
    let range = n.div_ceil(buckets);
    let mut cursor = offsets.clone(); // O(n)
    for b in 0..buckets {
        let blo = b * range;
        let bhi = ((b + 1) * range).min(n);
        if blo >= bhi {
            continue;
        }
        let base = offsets[blo] as usize;
        let mut buf = vec![0u32; offsets[bhi] as usize - base]; // O(m / buckets)
        for (u, v) in edges() {
            if v >= blo && v < bhi && u < n {
                buf[cursor[v] as usize - base] = u as u32;
                cursor[v] += 1;
            }
        }
        w.write_all(bytemuck::cast_slice(&buf))?;
    }
    w.write_all(bytemuck::cast_slice(&out_deg))?;
    w.flush()
}

/// A read-only, memory-mapped CSR graph. The edge structure is NOT in heap — it is paged from the
/// file on demand. Only the caller's O(n) rank vectors are resident.
pub struct MmapCsr {
    mmap: Mmap,
    n: usize,
    m: usize,
    off_start: usize,
    nbr_start: usize,
    deg_start: usize,
}

impl MmapCsr {
    pub fn open(path: &Path) -> io::Result<Self> {
        let file = File::open(path)?;
        // SAFETY: read-only map of a file we control; the process holds it for its lifetime.
        let mmap = unsafe { Mmap::map(&file)? };
        let n = u64::from_le_bytes(mmap[0..8].try_into().unwrap()) as usize;
        let m = u64::from_le_bytes(mmap[8..16].try_into().unwrap()) as usize;
        let off_start = 16;
        let nbr_start = off_start + (n + 1) * 8;
        let deg_start = nbr_start + m * 4;
        Ok(Self {
            mmap,
            n,
            m,
            off_start,
            nbr_start,
            deg_start,
        })
    }

    pub fn n(&self) -> usize {
        self.n
    }
    pub fn edge_count(&self) -> usize {
        self.m
    }
    /// Bytes of edge structure held on disk (mmap'd), NOT in heap.
    pub fn mapped_bytes(&self) -> usize {
        self.mmap.len()
    }

    fn offsets(&self) -> &[u64] {
        bytemuck::cast_slice(&self.mmap[self.off_start..self.off_start + (self.n + 1) * 8])
    }
    fn neighbors(&self) -> &[u32] {
        bytemuck::cast_slice(&self.mmap[self.nbr_start..self.nbr_start + self.m * 4])
    }
    pub fn out_deg(&self) -> &[u32] {
        bytemuck::cast_slice(&self.mmap[self.deg_start..self.deg_start + self.n * 4])
    }
    /// In-neighbours of node `v` — a slice straight into the mmap (no copy).
    pub fn in_neighbors(&self, v: usize) -> &[u32] {
        let off = self.offsets();
        &self.neighbors()[off[v] as usize..off[v + 1] as usize]
    }
}

/// PageRank computed DIRECTLY over the out-of-core CSR: edges are read from the mmap (disk-backed),
/// only the O(n) rank vectors are heap-resident. Same fixed point as the in-memory `pagerank`;
/// parallel (rayon) + deterministic.
pub fn pagerank_mmap(csr: &MmapCsr, damping: f64, max_iters: usize, tol: f64) -> Vec<f64> {
    let n = csr.n();
    if n == 0 {
        return Vec::new();
    }
    let out_deg = csr.out_deg();
    let base = (1.0 - damping) / n as f64;
    let mut rank = vec![1.0 / n as f64; n];
    for _ in 0..max_iters {
        let mut dangling = 0.0;
        for u in 0..n {
            if out_deg[u] == 0 {
                dangling += rank[u];
            }
        }
        let add = base + damping * dangling / n as f64;
        let next: Vec<f64> = (0..n)
            .into_par_iter()
            .map(|v| {
                let mut acc = 0.0;
                for &u in csr.in_neighbors(v) {
                    acc += rank[u as usize] / out_deg[u as usize] as f64;
                }
                add + damping * acc
            })
            .collect();
        let diff: f64 = (0..n).map(|i| (next[i] - rank[i]).abs()).sum();
        rank = next;
        if diff < tol {
            break;
        }
    }
    rank
}
