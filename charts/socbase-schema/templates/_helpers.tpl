{{- define "socbase.pgAdminEnv" -}}
- name: PGHOST
  value: {{ .Values.postgres.host | quote }}
- name: PGPORT
  value: {{ .Values.postgres.port | quote }}
- name: PGDATABASE
  value: {{ .Values.postgres.db | quote }}
{{- if .Values.postgres.username }}
- name: PGUSER
  value: {{ .Values.postgres.username | quote }}
{{- else }}
- name: PGUSER
  valueFrom: { secretKeyRef: { name: {{ .Values.postgres.existingSecret }}, key: username } }
{{- end }}
- name: PGPASSWORD
  valueFrom: { secretKeyRef: { name: {{ .Values.postgres.existingSecret }}, key: password } }
{{- end -}}
