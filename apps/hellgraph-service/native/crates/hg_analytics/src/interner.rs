//! interner — a string interner (symbol table), the world-class fix for "a String per edge". Every label,
//! property key, and repeated text value is interned ONCE to a compact `u32` symbol backed by a shared
//! `Arc<str>`. Effects:
//!   • storage: 16M edges labelled "E" hold ONE "E" allocation + 16M 4-byte symbols (or shared Arc refs),
//!     not 16M heap Strings;
//!   • compare/hash: on a `u32` symbol, not the string bytes, everywhere on the hot path;
//!   • equality: `Arc<str>` compares by CONTENT, so interned labels stay cross-replica-comparable (the CRDT
//!     View convergence still holds — two replicas that interned in a different order still compare equal).
//!
//! Design: a single append-only table behind an `RwLock`; the common "already interned" path takes only a
//! read lock. Backed by `Arc<str>` so `resolve` is a ref-count bump, never a string copy. This is the
//! rustc/`string-interner` pattern, no external crate.

use crate::fasthash::FxHashMap;
use std::sync::{Arc, RwLock};

#[derive(Default)]
struct Inner {
    map: FxHashMap<Arc<str>, u32>, // str content → symbol
    vec: Vec<Arc<str>>,            // symbol → shared str
}

/// A thread-safe string interner. Share it as `Arc<Interner>` across the Store, its View, ShardedGraph, and
/// the index so they all speak the same symbol space.
#[derive(Default)]
pub struct Interner {
    inner: RwLock<Inner>,
}

impl Interner {
    pub fn new() -> Self {
        Self::default()
    }

    /// Intern `s`, returning the shared `Arc<str>` (all equal strings share ONE allocation).
    pub fn intern(&self, s: &str) -> Arc<str> {
        if let Some(arc) = self.inner.read().unwrap().lookup(s) {
            return arc;
        }
        let mut g = self.inner.write().unwrap();
        if let Some(arc) = g.lookup(s) {
            return arc; // lost the race — someone interned it between the read and the write
        }
        let arc: Arc<str> = Arc::from(s);
        let id = g.vec.len() as u32;
        g.vec.push(arc.clone());
        g.map.insert(arc.clone(), id);
        arc
    }

    /// Intern `s`, returning its `u32` symbol (for the read-optimized structures).
    pub fn sym(&self, s: &str) -> u32 {
        {
            let g = self.inner.read().unwrap();
            if let Some(&id) = g.map.get(s) {
                return id;
            }
        }
        let mut g = self.inner.write().unwrap();
        if let Some(&id) = g.map.get(s) {
            return id;
        }
        let arc: Arc<str> = Arc::from(s);
        let id = g.vec.len() as u32;
        g.vec.push(arc.clone());
        g.map.insert(arc, id);
        id
    }

    /// The `u32` symbol for `s` if already interned (no insert).
    pub fn get_sym(&self, s: &str) -> Option<u32> {
        self.inner.read().unwrap().map.get(s).copied()
    }

    /// Resolve a symbol back to its shared string (ref-count bump, no copy).
    pub fn resolve(&self, sym: u32) -> Arc<str> {
        self.inner.read().unwrap().vec[sym as usize].clone()
    }

    pub fn len(&self) -> usize {
        self.inner.read().unwrap().vec.len()
    }
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

impl Inner {
    fn lookup(&self, s: &str) -> Option<Arc<str>> {
        self.map.get(s).map(|&id| self.vec[id as usize].clone())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn interns_once_and_shares_allocation() {
        let it = Interner::new();
        let a = it.intern("KNOWS");
        let b = it.intern("KNOWS");
        // same content ⇒ SAME allocation (pointer equality), not just equal bytes.
        assert!(Arc::ptr_eq(&a, &b), "equal strings must share one allocation");
        let c = it.intern("WORKS");
        assert!(!Arc::ptr_eq(&a, &c));
        assert_eq!(it.len(), 2);
    }

    #[test]
    fn symbols_are_stable_and_resolve() {
        let it = Interner::new();
        let k = it.sym("KNOWS");
        let w = it.sym("WORKS");
        assert_ne!(k, w);
        assert_eq!(it.sym("KNOWS"), k, "symbol is stable");
        assert_eq!(it.get_sym("KNOWS"), Some(k));
        assert_eq!(it.get_sym("nope"), None);
        assert_eq!(&*it.resolve(k), "KNOWS");
        assert_eq!(&*it.resolve(w), "WORKS");
    }

    #[test]
    fn intern_and_sym_share_the_same_table() {
        let it = Interner::new();
        let arc = it.intern("CITY");
        let s = it.sym("CITY");
        assert_eq!(it.len(), 1, "intern and sym must not create duplicate entries");
        assert!(Arc::ptr_eq(&arc, &it.resolve(s)));
    }
}
