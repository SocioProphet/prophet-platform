{{- define "pw.image" -}}
{{ .root.Values.image.registry }}/{{ index .root.Values.image .name }}:{{ .root.Values.image.tag }}
{{- end -}}

{{- /* cloud-vendor-agnostic LoadBalancer annotations: per-provider preset (by .Values.cloudProvider) + per-service override */ -}}
{{- define "pw.lbAnnotations" -}}
{{- $preset := index .root.Values.loadBalancerAnnotations .root.Values.cloudProvider | default dict -}}
{{- $merged := merge (deepCopy (.extra | default dict)) $preset -}}
{{- with $merged }}{{- toYaml . | nindent 4 }}{{- end -}}
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
