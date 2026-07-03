locals {
  generated_dir = abspath("${path.module}/${var.generated_dir}")

  required_metadata_fields = [
    "workstream",
    "meeting_type",
    "canonical_issue",
    "dashboard_key",
    "expected_outputs"
  ]

  calendars = [
    {
      calendarId        = var.cloud_vendor_strategy_calendar_id
      calendarName      = "SP - Cloud Vendor Strategy"
      workstreamDefault = "cloud-vendor-strategy"
    },
    {
      calendarId        = var.launch_council_calendar_id
      calendarName      = "SP - Launch Council"
      workstreamDefault = "cloud-vendor-strategy"
    }
  ]

  apps_script_config = {
    spreadsheetId         = var.spreadsheet_id
    syncWindowDaysBack    = var.sync_window_days_back
    syncWindowDaysForward = var.sync_window_days_forward
    dryRun                = var.prototype_dry_run
    calendars             = local.calendars
    requiredMetadataFields = local.required_metadata_fields
    tabs = {
      Meetings    = "Meetings"
      Automations = "Automations"
    }
  }

  clasp_config = {
    scriptId         = var.apps_script_project_id
    rootDir          = "apps-script/google-workspace-ops-prototype"
    scriptExtensions = [".gs", ".js"]
    htmlExtensions   = [".html"]
    jsonExtensions   = [".json"]
    filePushOrder = [
      "appsscript.json",
      "setup.gs",
      "sync-calendar-events-to-meetings.gs",
      "parser-test.gs",
      "seed-workspace-rows.gs",
      "seed-dashboard-rows.gs"
    ]
  }

  mesh_summary = {
    mesh_name                         = var.mesh_name
    google_project_id                 = var.google_project_id
    project_services_enabled          = var.enable_google_project_services
    workspace_groups_enabled          = var.enable_workspace_groups
    generated_local_deployment_files  = var.generate_local_deployment_files
    spreadsheet_id                    = var.spreadsheet_id
    apps_script_project_id            = var.apps_script_project_id
    cloud_vendor_strategy_calendar_id = var.cloud_vendor_strategy_calendar_id
    launch_council_calendar_id        = var.launch_council_calendar_id
    dry_run                           = var.prototype_dry_run
  }
}
