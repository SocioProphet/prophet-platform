# Crystal Atlas data and capability catalog

## Catalog families

### Source catalog
Records source kind, distribution class, capability ref, license ref, and freshness policy.

### Asset catalog
Records asset kind, tenant, source refs, schema ref, freshness, and lifecycle metadata.

### Provider capability catalog
Describes what a provider surface can actually do:
- auth modes
- content types
- read/write granularity
- replay
- masking
- structured outputs
- tool use
- latency/cost bands

### Model catalog
Records provider-linked model/runtime capabilities.

### Workflow catalog
Records input/output contracts, tool requirements, allowed channels, and workflow identity.

### Policy decision catalog
Records explicit publication or routing decisions.

## Data tier model
Crystal Atlas distinguishes source licensing from product packaging.

Distribution classes:
- open
- public_derived
- free_tier_packaged
- internal_private
- premium_byo
- premium_platform_managed
- restricted_nonredistributable

Free-tier data is a product packaging class. Open data is a source/license class. Premium data is a provider/commercial class.
