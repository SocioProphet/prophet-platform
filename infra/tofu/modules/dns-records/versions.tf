terraform {
  # Provider-agnostic: this module computes a normalized record model and holds NO
  # provider resources. Cloud-specific emitters (dns-zone-gcp, dns-zone-aws, ...) consume
  # its outputs. Adding a cloud = one new emitter against this same contract.
  required_version = ">= 1.8.0"
}
