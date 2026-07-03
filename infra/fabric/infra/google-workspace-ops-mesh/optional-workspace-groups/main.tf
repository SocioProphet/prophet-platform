resource "googleworkspace_group" "ops_groups" {
  for_each = var.workspace_groups

  email       = each.value.email
  name        = each.value.name
  description = each.value.description
}

locals {
  workspace_group_members = flatten([
    for group_key, group in var.workspace_groups : [
      for member in try(group.members, []) : {
        key         = "${group_key}:${member}"
        group_key   = group_key
        group_email = group.email
        member      = member
      }
    ]
  ])
}

resource "googleworkspace_group_member" "ops_group_members" {
  for_each = {
    for item in local.workspace_group_members : item.key => item
  }

  group_id = googleworkspace_group.ops_groups[each.value.group_key].id
  email    = each.value.member
  role     = "MEMBER"
}
