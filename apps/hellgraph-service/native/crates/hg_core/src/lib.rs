use std::fmt;

pub type AtomId = u128;
pub type ArtifactId = u128;
pub type TxnId = u64;

pub const FIELD_DIMENSIONS: usize = 26;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EpistemicMode {
    OpenWorld,
    ClosedWorld,
    BoundedSnapshot,
    Counterfactual,
    Simulation,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SecurityLabel {
    Public,
    Internal,
    Confidential,
    Restricted,
    LocalOnly,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Polarity {
    HigherIsBetter,
    LowerIsBetter,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProofVerdict {
    Proved,
    Violated,
    Inconclusive,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TruthValue {
    pub alpha: f64,
    pub beta: f64,
    pub prior_mass: f64,
    pub contradiction: f32,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct ActivationValue {
    pub salience: f64,
    pub recency: f64,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct DimSpec {
    pub index: usize,
    pub name: &'static str,
    pub lower: f64,
    pub upper: f64,
    pub polarity: Polarity,
    pub notes: &'static str,
}

#[derive(Clone, PartialEq)]
pub struct FieldState26 {
    pub dims: [f64; FIELD_DIMENSIONS],
    pub epsilon_eff: f64,
}

impl fmt::Debug for FieldState26 {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("FieldState26")
            .field("dims", &&self.dims[..])
            .field("epsilon_eff", &self.epsilon_eff)
            .finish()
    }
}

impl FieldState26 {
    pub fn zeroed() -> Self {
        Self {
            dims: [0.0; FIELD_DIMENSIONS],
            epsilon_eff: 0.0,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct FieldValue {
    pub field_pack_name: String,
    pub basis_version: u32,
    pub basis_fingerprint_fnv1a64: u64,
    pub state: FieldState26,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ProofValue {
    pub verdict: ProofVerdict,
    pub artifact_ref: Option<ArtifactId>,
    pub evidence_count: usize,
    pub epsilon_eff: f64,
    pub max_violation_magnitude: f64,
    pub insufficiency_reason: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct BoundViolationRecord {
    pub dim_index: usize,
    pub dim_name: String,
    pub value: f64,
    pub lower: f64,
    pub upper: f64,
    pub magnitude: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ProofArtifactRecord {
    pub subject_atom: AtomId,
    pub snapshot_txn: TxnId,
    pub field_pack_name: String,
    pub field_pack_basis_version: u32,
    pub basis_fingerprint_fnv1a64: u64,
    pub assumptions_fingerprint_fnv1a64: u64,
    pub evidence_basis_fingerprint_fnv1a64: u64,
    pub verdict: ProofVerdict,
    pub evidence_count: usize,
    pub epsilon_eff: f64,
    pub max_violation_magnitude: f64,
    pub violated: Vec<BoundViolationRecord>,
    pub insufficiency_reason: Option<String>,
    pub witness_summary: Option<String>,
    pub counterexample_summary: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ArtifactPayload {
    Proof(ProofArtifactRecord),
}

#[derive(Debug, Clone, PartialEq)]
pub struct StoredArtifact {
    pub artifact_id: ArtifactId,
    pub created_at_txn: TxnId,
    pub payload: ArtifactPayload,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub enum ValueKey {
    FieldCurrent,
    ProofCurrent,
    Prop(String),
}

#[derive(Debug, Clone, PartialEq)]
pub enum ValuePayload {
    Field(FieldValue),
    Proof(ProofValue),
}

#[derive(Debug, Clone, PartialEq)]
pub struct ValueEnvelope {
    pub subject_atom: AtomId,
    pub key: ValueKey,
    pub payload: ValuePayload,
    pub committed_at_txn: TxnId,
    pub retired_at_txn: Option<TxnId>,
    pub epistemic_mode: EpistemicMode,
    pub security: SecurityLabel,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AtomKind {
    Node,
    Link,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LinkSemantics {
    DirectedBinary,
    OrderedNary,
    UnorderedNary,
    SetLike,
    MultiSetLike,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AtomHeader {
    pub atom_id: AtomId,
    pub kind: AtomKind,
    pub type_name: String,
    pub created_txn: TxnId,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NodeAtom {
    pub hdr: AtomHeader,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RoleBinding {
    pub role_name: String,
    pub target: AtomId,
    pub ordinal: u16,
}

/// SP-RETR-FIBER-001 (WO_FIBER_002): the two edge classes of the composite graph H.
/// `Containment` = E^⊑ (single-parent, mereological, the per-document trees);
/// `Relational` = E_R (typed many-to-many, the cross-document links). Defaults to
/// `Relational`: every link created before this field existed — and every link restored
/// from a journal written before it — is relational.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum EdgeClass {
    Containment,
    #[default]
    Relational,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LinkAtom {
    pub hdr: AtomHeader,
    pub semantics: LinkSemantics,
    pub members: Vec<RoleBinding>,
    pub edge_class: EdgeClass,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Atom {
    Node(NodeAtom),
    Link(LinkAtom),
}

pub fn clamp_unit(x: f64) -> f64 {
    // NaN-safe unit clamp: NaN and negatives both floor to 0.0. NOT f64::clamp — that would
    // propagate NaN (x.clamp(0.0, 1.0) on NaN yields NaN), which this function must map to 0.0.
    if x.is_nan() || x < 0.0 {
        0.0
    } else if x > 1.0 {
        1.0
    } else {
        x
    }
}

pub fn mean_abs(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    values.iter().map(|v| v.abs()).sum::<f64>() / values.len() as f64
}

pub fn fnv1a64(bytes: &[u8]) -> u64 {
    let mut h: u64 = 0xcbf29ce484222325;
    for b in bytes {
        h ^= *b as u64;
        h = h.wrapping_mul(0x100000001b3);
    }
    h
}

pub fn fnv1a64_str(s: &str) -> u64 {
    fnv1a64(s.as_bytes())
}
