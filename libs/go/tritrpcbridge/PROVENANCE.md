# Provenance

`libs/go/tritrpcbridge/tritrpcv1/*` is copied from the stable Go TritRPC v1 port in `SocioProphet/TriTRPC` and kept intentionally small. The copied files correspond to the stable v1 envelope/decoder/TLEB3/TritPack implementation, while platform-specific stream binding and health helpers live under `binding/`.

This repo should treat the upstream TriTRPC repo as the normative specification and fixture source. Local changes in this module should be limited to import-path normalization, provenance comments, and platform binding glue.
