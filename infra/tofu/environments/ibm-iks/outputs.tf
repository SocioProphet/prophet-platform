output "cluster_name" {
  value = ibm_container_vpc_cluster.this.name
}
output "registry_namespace" {
  value = ibm_cr_namespace.images.name
}
output "get_credentials" {
  value = "ibmcloud ks cluster config --cluster ${ibm_container_vpc_cluster.this.name}"
}
