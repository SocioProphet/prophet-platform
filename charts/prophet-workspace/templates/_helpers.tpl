{{- define "pw.image" -}}
{{ .root.Values.image.registry }}/{{ index .root.Values.image .name }}:{{ .root.Values.image.tag }}
{{- end -}}

{{- define "pw.pgEnv" -}}
- name: POSTGRES_HOST
  value: {{ .Values.postgres.host | quote }}
- name: POSTGRES_DB
  value: {{ .Values.postgres.db | quote }}
- name: POSTGRES_USER
  valueFrom: { secretKeyRef: { name: {{ .Values.postgres.existingSecret }}, key: username } }
- name: POSTGRES_PASSWORD
  valueFrom: { secretKeyRef: { name: {{ .Values.postgres.existingSecret }}, key: password } }
{{- end -}}
