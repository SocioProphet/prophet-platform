//! probabilistic — the sketch structures that actually earn their place in a graph DB. HONEST placement:
//!   • Bloom filter — an O(1) "definitely-not-an-edge" pre-check for `has_edge`, so NEGATIVE lookups skip
//!     the dictionary + binary search entirely. Wins exactly when non-edges dominate (triangle counting,
//!     link-prediction candidate filtering, join probes). It does NOT speed positive lookups.
//!   • HyperLogLog — distinct-cardinality in ~O(1) memory, for the QUERY PLANNER (estimate a frontier's
//!     distinct reach without materializing it) and whole-graph distinct-value analytics. Exact structures
//!     (degree arrays, bit-array visited) still win the in-memory hot path; HLL is for planning/at-scale.
//!
//! What we deliberately do NOT use: a Bloom filter for k-hop `visited` — a dense bit-array is exact AND
//! faster there, so a probabilistic set would be strictly worse. Sketches only where they beat exact.

/// A classic Bloom filter with double-hashing (`h_i = h1 + i·h2`). Power-of-two sizing so the modulo is a
/// mask. No false negatives; false-positive rate ≈ (1 − e^(−k·n/m))^k.
pub struct Bloom {
    bits: Vec<u64>,
    mask: usize, // m_bits - 1 (m_bits is a power of two)
    k: u32,
}

impl Bloom {
    /// Size for `n_items` at `bits_per_item` bits each (10 ⇒ ~1% false positive). k chosen ≈ ln2·bits.
    pub fn new(n_items: usize, bits_per_item: usize) -> Self {
        let m_bits = (n_items.max(1) * bits_per_item.max(1)).next_power_of_two().max(64);
        let k = ((bits_per_item as f64) * std::f64::consts::LN_2).round().clamp(1.0, 16.0) as u32;
        Bloom { bits: vec![0u64; m_bits / 64], mask: m_bits - 1, k }
    }

    #[inline]
    fn slots(&self, key: u64) -> (u64, u64) {
        (key, key.rotate_left(32) | 1) // h2 must be odd so it strides the whole table
    }

    pub fn insert(&mut self, key: u64) {
        let (h1, h2) = self.slots(key);
        for i in 0..self.k as u64 {
            let b = (h1.wrapping_add(i.wrapping_mul(h2)) as usize) & self.mask;
            self.bits[b >> 6] |= 1u64 << (b & 63);
        }
    }

    /// `false` ⇒ the key was DEFINITELY never inserted. `true` ⇒ probably inserted (verify exactly).
    pub fn maybe_contains(&self, key: u64) -> bool {
        let (h1, h2) = self.slots(key);
        for i in 0..self.k as u64 {
            let b = (h1.wrapping_add(i.wrapping_mul(h2)) as usize) & self.mask;
            if self.bits[b >> 6] & (1u64 << (b & 63)) == 0 {
                return false;
            }
        }
        true
    }

    pub fn bits(&self) -> usize {
        (self.mask + 1) as usize
    }
}

/// splitmix64 finalizer — spreads integer keys before sketching.
#[inline]
pub fn mix64(mut z: u64) -> u64 {
    z = (z ^ (z >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94d049bb133111eb);
    z ^ (z >> 31)
}

/// HyperLogLog distinct-count estimator (register width 6-bit rounded to a byte; p in 4..=16).
pub struct HyperLogLog {
    reg: Vec<u8>,
    p: u32,
}

impl HyperLogLog {
    pub fn new(p: u32) -> Self {
        let p = p.clamp(4, 16);
        HyperLogLog { reg: vec![0u8; 1 << p], p }
    }

    pub fn add(&mut self, x: u64) {
        let h = mix64(x);
        let idx = (h >> (64 - self.p)) as usize;
        let tail = h << self.p; // meaningful bits shifted to the top
        let rank = if tail == 0 { (64 - self.p + 1) as u8 } else { tail.leading_zeros() as u8 + 1 };
        if rank > self.reg[idx] {
            self.reg[idx] = rank;
        }
    }

    pub fn estimate(&self) -> f64 {
        let m = self.reg.len() as f64;
        let alpha = match self.reg.len() {
            16 => 0.673,
            32 => 0.697,
            64 => 0.709,
            _ => 0.7213 / (1.0 + 1.079 / m),
        };
        let sum: f64 = self.reg.iter().map(|&r| 2f64.powi(-(r as i32))).sum();
        let raw = alpha * m * m / sum;
        // small-range (linear counting) correction when many registers are still zero.
        if raw <= 2.5 * m {
            let zeros = self.reg.iter().filter(|&&r| r == 0).count();
            if zeros > 0 {
                return m * (m / zeros as f64).ln();
            }
        }
        raw
    }

    /// HLLs are mergeable (register-wise max) — the property that makes them work in a DISTRIBUTED planner:
    /// each shard sketches locally, the coordinator merges O(m) bytes, no raw sets on the wire.
    pub fn merge(&mut self, other: &HyperLogLog) {
        for (a, &b) in self.reg.iter_mut().zip(&other.reg) {
            if b > *a {
                *a = b;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bloom_has_no_false_negatives_and_bounded_false_positives() {
        let n = 10_000usize;
        let mut b = Bloom::new(n, 10);
        for i in 0..n as u64 {
            b.insert(mix64(i));
        }
        // no false negatives
        for i in 0..n as u64 {
            assert!(b.maybe_contains(mix64(i)), "inserted key must be reported present");
        }
        // false-positive rate on absent keys should be small (~1% at 10 bits/item)
        let mut fp = 0;
        for i in n as u64..(n as u64 + 20_000) {
            if b.maybe_contains(mix64(i)) {
                fp += 1;
            }
        }
        let rate = fp as f64 / 20_000.0;
        assert!(rate < 0.05, "false-positive rate {rate} too high");
    }

    #[test]
    fn hll_estimates_distinct_within_a_few_percent() {
        for &n in &[1_000u64, 100_000, 1_000_000] {
            let mut h = HyperLogLog::new(14); // 16384 registers
            for i in 0..n {
                h.add(i.wrapping_mul(0x9e3779b97f4a7c15));
            }
            let est = h.estimate();
            let err = (est - n as f64).abs() / n as f64;
            assert!(err < 0.05, "HLL error {err:.3} for n={n} (est {est:.0})");
        }
    }

    #[test]
    fn hll_merge_is_a_union() {
        let mut a = HyperLogLog::new(12);
        let mut b = HyperLogLog::new(12);
        for i in 0..50_000u64 {
            a.add(mix64(i));
        }
        for i in 25_000..75_000u64 {
            b.add(mix64(i)); // overlaps a on [25k,50k)
        }
        a.merge(&b);
        let est = a.estimate(); // true union = 75_000 distinct
        let err = (est - 75_000.0).abs() / 75_000.0;
        assert!(err < 0.05, "merged HLL error {err:.3} (est {est:.0})");
    }
}
