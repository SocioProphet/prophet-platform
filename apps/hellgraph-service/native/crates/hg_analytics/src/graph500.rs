//! graph500 — Graph500 Kronecker (RMAT) synthetic graph generator: the standard, reproducible,
//! on-the-fly dataset for scale benchmarks (no download). `scale` → 2^scale vertices; `edgefactor`
//! edges per vertex. Standard RMAT quadrant probabilities A=0.57, B=0.19, C=0.19, D=0.05.
//! Deterministic (seeded splitmix64). Feeds straight into the CSR builders as a re-iterable stream.

/// splitmix64's additive constant. The state is a PURE additive counter (`state += GOLDEN` each split),
/// which is exactly what makes the stream O(1)-seekable: the state after `k` splits is `seed + k·GOLDEN`.
const GOLDEN: u64 = 0x9e3779b97f4a7c15;

/// splitmix64 step → uniform f64 in [0,1). Deterministic, fast, well-distributed.
#[inline]
fn split_next(state: &mut u64) -> f64 {
    *state = state.wrapping_add(GOLDEN);
    let mut z = *state;
    z = (z ^ (z >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94d049bb133111eb);
    z ^= z >> 31;
    (z >> 11) as f64 / ((1u64 << 53) as f64)
}

/// A deterministic RMAT edge stream. Create a fresh one per pass (same seed → same edges), so it
/// works with the two-pass CSR builders.
pub struct Kronecker {
    state: u64,
    scale: u32,
    remaining: usize,
}

impl Kronecker {
    pub fn new(scale: u32, edgefactor: usize, seed: u64) -> Self {
        Kronecker {
            state: seed,
            scale,
            remaining: edgefactor * (1usize << scale),
        }
    }
    /// O(1) seek to a SLICE of the same deterministic stream: yields EXACTLY the edges the full stream
    /// (`new(scale, _, seed)`) produces at positions `[start, start+count)`. Each edge consumes `scale`
    /// splits, so we jump the additive state forward by `start·scale` splits in constant time. This is the
    /// primitive that lets every worker generate ONLY its own edge range — no coordinator, no shared state,
    /// no single node ever holding the whole graph.
    pub fn slice(scale: u32, seed: u64, start: usize, count: usize) -> Self {
        let splits = (start as u64).wrapping_mul(scale as u64);
        Kronecker {
            state: seed.wrapping_add(splits.wrapping_mul(GOLDEN)),
            scale,
            remaining: count,
        }
    }

    /// Generate the FULL deterministic edge stream in PARALLEL: split `[0, m)` into `chunks` contiguous
    /// slices, generate each independently via the O(1) seek, and concatenate IN ORDER. Bit-identical to the
    /// serial `new(...).collect()` (the slice invariant), but saturating all cores — the single-node analog
    /// of distributed generation (#12): the same seekable slices, one per core here vs one per worker on the
    /// cluster. This is what kills the single-threaded generation wall (222s at the billion). The per-chunk
    /// generation (the expensive `scale` splits/edge) is parallel; the final concat is a cheap ordered memcpy.
    pub fn generate_parallel(
        scale: u32,
        edgefactor: usize,
        seed: u64,
        chunks: usize,
    ) -> Vec<(usize, usize)> {
        use rayon::prelude::*;
        let m = Self::edges(scale, edgefactor);
        if m == 0 {
            return Vec::new();
        }
        let chunks = chunks.clamp(1, m);
        // rayon `collect` into a Vec preserves iterator order, so `concat` yields the exact serial stream.
        let parts: Vec<Vec<(usize, usize)>> = (0..chunks)
            .into_par_iter()
            .map(|c| {
                let start = c * m / chunks;
                let end = (c + 1) * m / chunks;
                Kronecker::slice(scale, seed, start, end - start).collect()
            })
            .collect();
        parts.concat()
    }

    /// Vertex count for a scale (= 2^scale).
    pub fn vertices(scale: u32) -> usize {
        1usize << scale
    }
    /// Edge count for a scale + edgefactor.
    pub fn edges(scale: u32, edgefactor: usize) -> usize {
        edgefactor * (1usize << scale)
    }
}

impl Iterator for Kronecker {
    type Item = (usize, usize);
    #[inline]
    fn next(&mut self) -> Option<(usize, usize)> {
        if self.remaining == 0 {
            return None;
        }
        self.remaining -= 1;
        // RMAT: recurse into a quadrant `scale` times, setting one bit of (u,v) per level.
        const A: f64 = 0.57;
        const AB: f64 = 0.76; // A + B
        const ABC: f64 = 0.95; // A + B + C
        let (mut u, mut v) = (0u64, 0u64);
        for i in 0..self.scale {
            let r = split_next(&mut self.state);
            let bit = 1u64 << i;
            if r >= ABC {
                u |= bit;
                v |= bit; // D: bottom-right
            } else if r >= AB {
                u |= bit; // C: bottom-left
            } else if r >= A {
                v |= bit; // B: top-right
            }
            // else A: top-left — no bits set
        }
        Some((u as usize, v as usize))
    }
}

#[cfg(test)]
mod tests {
    use super::Kronecker;

    #[test]
    fn parallel_generation_is_bit_identical_to_serial() {
        let (scale, ef, seed) = (14u32, 16usize, 0xF00Du64);
        let serial: Vec<(usize, usize)> = Kronecker::new(scale, ef, seed).collect();
        for chunks in [1usize, 4, 16, 64, 100] {
            let parallel = Kronecker::generate_parallel(scale, ef, seed, chunks);
            assert_eq!(
                parallel, serial,
                "chunks={chunks}: parallel generation diverged from the serial stream"
            );
        }
    }

    #[test]
    fn slice_matches_the_full_stream_exactly() {
        let scale = 12u32;
        let ef = 8usize;
        let seed = 0xA11CE;
        let full: Vec<(usize, usize)> = Kronecker::new(scale, ef, seed).collect();
        let m = full.len();

        // Split the stream into k contiguous slices generated independently — the concatenation must be
        // bit-identical to the full stream (this is the distributed-generation invariant).
        for k in [1usize, 3, 8, 7] {
            let mut rebuilt: Vec<(usize, usize)> = Vec::with_capacity(m);
            for c in 0..k {
                let start = c * m / k;
                let end = (c + 1) * m / k;
                rebuilt.extend(Kronecker::slice(scale, seed, start, end - start));
            }
            assert_eq!(
                rebuilt, full,
                "k={k}: sliced generation diverged from the full stream"
            );
        }
    }
}
