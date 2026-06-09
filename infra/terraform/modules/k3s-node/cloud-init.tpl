#cloud-config
package_update: true
package_upgrade: true
packages:
  - curl
  - ca-certificates
  - jq

runcmd:
  - |
    set -e
    export K3S_TOKEN="${k3s_token}"
    export INSTALL_K3S_VERSION="${k3s_version}"

    %{ if role == "control-plane" }
    curl -sfL https://get.k3s.io | sh -s - server \
      --cluster-init \
      --node-name "${node_name}" \
      --disable traefik \
      --disable servicelb \
      --tls-san $(curl -s http://169.254.169.254/hetzner/v1/metadata/public-ipv4) \
      ${extra_args}
    %{ else }
    curl -sfL https://get.k3s.io | sh -s - agent \
      --server "${k3s_server_url}" \
      --node-name "${node_name}" \
      ${extra_args}
    %{ endif }
