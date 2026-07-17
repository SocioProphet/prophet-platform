//! fasthash — FxHash: the fast, non-cryptographic hasher (the one rustc itself uses internally). std's
//! default HashMap uses SipHash, which is DoS-resistant and CRYPTOGRAPHIC — great for untrusted keys on a
//! web server, pure overhead for our INTERNAL integer keys (node ids, dots, dense indices). Swapping it in
//! for the hot maps is the single biggest "world-class hash index" win: ~3-5× less time per probe, and our
//! keys (u32/u64) hit the fast integer path. No dependency.

use std::collections::{HashMap, HashSet};
use std::hash::{BuildHasherDefault, Hasher};

const SEED: u64 = 0x51_7c_c1_b7_27_22_0a_95; // the FxHash multiplier

#[derive(Default)]
pub struct FxHasher {
    hash: u64,
}
impl FxHasher {
    #[inline]
    fn add(&mut self, i: u64) {
        self.hash = (self.hash.rotate_left(5) ^ i).wrapping_mul(SEED);
    }
}
impl Hasher for FxHasher {
    #[inline]
    fn write(&mut self, bytes: &[u8]) {
        for chunk in bytes.chunks(8) {
            let mut b = [0u8; 8];
            b[..chunk.len()].copy_from_slice(chunk);
            self.add(u64::from_le_bytes(b));
        }
    }
    #[inline]
    fn write_u8(&mut self, i: u8) {
        self.add(i as u64);
    }
    #[inline]
    fn write_u32(&mut self, i: u32) {
        self.add(i as u64);
    }
    #[inline]
    fn write_u64(&mut self, i: u64) {
        self.add(i);
    }
    #[inline]
    fn write_usize(&mut self, i: usize) {
        self.add(i as u64);
    }
    #[inline]
    fn finish(&self) -> u64 {
        self.hash
    }
}

pub type FxBuildHasher = BuildHasherDefault<FxHasher>;
pub type FxHashMap<K, V> = HashMap<K, V, FxBuildHasher>;
pub type FxHashSet<K> = HashSet<K, FxBuildHasher>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn works_as_a_hashmap_and_distributes() {
        let mut m: FxHashMap<u64, u64> = FxHashMap::default();
        for i in 0..10_000u64 {
            m.insert(i.wrapping_mul(2654435761), i);
        }
        assert_eq!(m.len(), 10_000);
        for i in 0..10_000u64 {
            assert_eq!(m.get(&i.wrapping_mul(2654435761)), Some(&i));
        }
        // sanity: distinct integer keys land in distinct hashes (no absurd collision pile-up)
        let mut hashes: FxHashSet<u64> = FxHashSet::default();
        for i in 0..1000u64 {
            let mut h = FxHasher::default();
            h.write_u64(i);
            hashes.insert(h.finish());
        }
        assert_eq!(hashes.len(), 1000, "distinct integer keys must not collapse");
    }
}
