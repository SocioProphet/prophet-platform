# Gateway auth notes

Preferred production posture:

- terminate external auth at the gateway
- validate identity and organization membership at the gateway
- inject trusted subject / organization / scopes headers only on the internal hop
- do not trust caller-supplied identity headers from the public edge

Static token configuration in this lane is for local bring-up only.
