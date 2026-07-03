/**
 * Sync Google Calendar events into the Meetings ledger.
 *
 * Prototype implementation for issue #49.
 * Standards source: SocioProphet/socioprophet-standards-storage#92.
 */

function syncCalendarEventsToMeetings(config) {
  const startedAt = new Date();
  const runId = 'arun_' + Utilities.formatDate(startedAt, 'UTC', 'yyyyMMdd_HHmmss') + '_calendar_sync';
  let affectedRecords = 0;
  let status = 'started';
  let error = '';

  try {
    validateConfig_(config);
    const ss = SpreadsheetApp.openById(config.spreadsheetId);
    const meetingsSheet = ss.getSheetByName(config.tabs.Meetings || 'Meetings');
    const automationsSheet = ss.getSheetByName(config.tabs.Automations || 'Automations');
    if (!meetingsSheet || !automationsSheet) {
      throw new Error('Required ledger tabs missing: Meetings and/or Automations');
    }

    const now = new Date();
    const start = new Date(now.getTime() - (config.syncWindowDaysBack || 14) * 24 * 60 * 60 * 1000);
    const end = new Date(now.getTime() + (config.syncWindowDaysForward || 60) * 24 * 60 * 60 * 1000);

    config.calendars.forEach(function(calendarConfig) {
      const calendar = CalendarApp.getCalendarById(calendarConfig.calendarId);
      if (!calendar) {
        throw new Error('Calendar not found: ' + calendarConfig.calendarId);
      }

      const events = calendar.getEvents(start, end);
      events.forEach(function(event) {
        const description = event.getDescription() || '';
        const metadata = parseSocioprophetMetadata_(description);
        const validation = validateMetadata_(metadata, config.requiredMetadataFields || []);

        if (!validation.ok) {
          writeAutomationRun_(automationsSheet, {
            run_id: runId + '_quarantine_' + safeId_(event.getId()),
            automation_name: 'syncCalendarEventsToMeetings',
            trigger_type: 'time_driven',
            source_object: 'calendar:' + calendarConfig.calendarId + ':event:' + event.getId(),
            target_object: 'sheet:Meetings',
            started_at: startedAt.toISOString(),
            completed_at: new Date().toISOString(),
            status: 'quarantined',
            error: 'Missing required metadata: ' + validation.missing.join(', '),
            affected_records: 0,
            replay_ref: ''
          });
          return;
        }

        const row = buildMeetingRow_(event, calendarConfig, metadata);
        if (!config.dryRun) {
          upsertByKey_(meetingsSheet, 'meeting_id', row);
        }
        affectedRecords += 1;
      });
    });

    status = 'succeeded';
  } catch (e) {
    status = 'failed';
    error = e && e.message ? e.message : String(e);
  }

  try {
    if (config && config.spreadsheetId) {
      const ss = SpreadsheetApp.openById(config.spreadsheetId);
      const automationsSheet = ss.getSheetByName((config.tabs && config.tabs.Automations) || 'Automations');
      if (automationsSheet) {
        writeAutomationRun_(automationsSheet, {
          run_id: runId,
          automation_name: 'syncCalendarEventsToMeetings',
          trigger_type: 'time_driven',
          source_object: 'configured_calendars',
          target_object: 'sheet:Meetings',
          started_at: startedAt.toISOString(),
          completed_at: new Date().toISOString(),
          status: status,
          error: error,
          affected_records: affectedRecords,
          replay_ref: ''
        });
      }
    }
  } catch (logError) {
    throw new Error('Sync status=' + status + '; logging failed: ' + logError.message + '; original_error=' + error);
  }

  if (status === 'failed') {
    throw new Error(error);
  }
  return { run_id: runId, status: status, affected_records: affectedRecords };
}

function validateConfig_(config) {
  if (!config) throw new Error('Missing config');
  if (!config.spreadsheetId) throw new Error('Missing config.spreadsheetId');
  if (!Array.isArray(config.calendars) || config.calendars.length === 0) throw new Error('Missing config.calendars');
  config.calendars.forEach(function(c) {
    if (!c.calendarId) throw new Error('Calendar config missing calendarId');
  });
}

function parseSocioprophetMetadata_(description) {
  const marker = 'socioprophet:';
  const markerIndex = description.indexOf(marker);
  if (markerIndex === -1) return {};

  const block = description.slice(markerIndex + marker.length).split('\n');
  const out = {};
  let currentListKey = null;

  block.forEach(function(rawLine) {
    const line = rawLine.replace(/\r/g, '');
    if (!line.trim()) return;
    if (/^\S/.test(line) && line.indexOf(':') === -1 && line.trim() !== '-') return;

    const listMatch = line.match(/^\s*-\s*(.+)$/);
    if (listMatch && currentListKey) {
      out[currentListKey].push(listMatch[1].trim());
      return;
    }

    const kvMatch = line.match(/^\s*([A-Za-z0-9_\-]+):\s*(.*)$/);
    if (kvMatch) {
      const key = kvMatch[1].trim();
      const value = kvMatch[2].trim();
      if (value === '') {
        out[key] = [];
        currentListKey = key;
      } else {
        out[key] = value;
        currentListKey = null;
      }
    }
  });

  return out;
}

function validateMetadata_(metadata, requiredFields) {
  const missing = requiredFields.filter(function(field) {
    return metadata[field] === undefined || metadata[field] === null || metadata[field] === '' || (Array.isArray(metadata[field]) && metadata[field].length === 0);
  });
  return { ok: missing.length === 0, missing: missing };
}

function buildMeetingRow_(event, calendarConfig, metadata) {
  const meetingId = safeId_(calendarConfig.calendarId) + ':' + safeId_(event.getId()) + ':' + event.getStartTime().toISOString();
  return {
    meeting_id: meetingId,
    calendar_event_id: event.getId(),
    calendar_id: calendarConfig.calendarId,
    workstream_id: metadata.workstream || calendarConfig.workstreamDefault || '',
    meeting_type: metadata.meeting_type || '',
    scheduled_start: event.getStartTime().toISOString(),
    scheduled_end: event.getEndTime().toISOString(),
    actual_status: 'scheduled',
    attendee_groups: normalizeList_(metadata.attendee_groups).join(','),
    decisions_count: 0,
    action_items_count: 0,
    risks_count: 0,
    source_note_ref: metadata.drive_note_ref || '',
    next_review_date: metadata.next_review_date || ''
  };
}

function normalizeList_(value) {
  if (Array.isArray(value)) return value;
  if (!value) return [];
  return String(value).split(',').map(function(v) { return v.trim(); }).filter(Boolean);
}

function upsertByKey_(sheet, keyColumnName, rowObject) {
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const keyIndex = headers.indexOf(keyColumnName);
  if (keyIndex === -1) throw new Error('Key column missing: ' + keyColumnName);

  const key = rowObject[keyColumnName];
  const lastRow = sheet.getLastRow();
  let targetRow = lastRow + 1;

  if (lastRow > 1) {
    const keys = sheet.getRange(2, keyIndex + 1, lastRow - 1, 1).getValues();
    for (let i = 0; i < keys.length; i++) {
      if (keys[i][0] === key) {
        targetRow = i + 2;
        break;
      }
    }
  }

  const values = headers.map(function(header) {
    return rowObject[header] !== undefined ? rowObject[header] : '';
  });
  sheet.getRange(targetRow, 1, 1, headers.length).setValues([values]);
}

function writeAutomationRun_(sheet, record) {
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const values = headers.map(function(header) {
    return record[header] !== undefined ? record[header] : '';
  });
  sheet.appendRow(values);
}

function safeId_(value) {
  return String(value || '').replace(/[^A-Za-z0-9_:\-.]/g, '_');
}
