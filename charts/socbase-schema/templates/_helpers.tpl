{{- define "socbase.pgAdminEnv" -}}
- name: PGHOST
  value: {{ .Values.postgres.host | quote }}
- name: PGPORT
  value: {{ .Values.postgres.port | quote }}
- name: PGDATABASE
  value: {{ .Values.postgres.db | quote }}
- name: PGUSER
  valueFrom: { secretKeyRef: { name: {{ .Values.postgres.existingSecret }}, key: username } }
- name: PGPASSWORD
  valueFrom: { secretKeyRef: { name: {{ .Values.postgres.existingSecret }}, key: password } }
{{- end -}}
