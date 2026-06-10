resource "google_folder" "folders" {
  for_each = var.folders

  display_name = each.value.display_name
  parent = (
    each.value.parent == "" || each.value.parent == null
    ? "organizations/${var.org_id}"
    : (startswith(each.value.parent, "folders/")
      ? each.value.parent
    : google_folder.folders[each.value.parent].name)
  )
}
