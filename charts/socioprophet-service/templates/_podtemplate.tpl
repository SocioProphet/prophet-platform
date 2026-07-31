{{- /*
Shared pod template body (the `template:` value under a Deployment or Rollout's
spec). Extracted so deployment.yaml and rollout.yaml render byte-identical pods —
a service that flips `rollout.enabled` gets the same containers/probes/env/volumes,
only the surrounding workload kind + strategy differ.
*/ -}}
{{- define "svc.podTemplateSpec" -}}
metadata:
  labels:
    {{- include "svc.selectorLabels" . | nindent 4 }}
    {{- with .Values.podLabels }}{{- toYaml . | nindent 4 }}{{- end }}
  annotations:
    {{- if .Values.config }}
    checksum/config: {{ .Values.config | toYaml | sha256sum }}
    {{- end }}
    {{- with .Values.podAnnotations }}{{- toYaml . | nindent 4 }}{{- end }}
spec:
  serviceAccountName: {{ include "svc.serviceAccountName" . }}
  {{- with .Values.imagePullSecrets }}
  imagePullSecrets: {{- toYaml . | nindent 4 }}
  {{- end }}
  securityContext: {{- toYaml .Values.podSecurityContext | nindent 4 }}
  enableServiceLinks: {{ .Values.enableServiceLinks }}
  containers:
    - name: {{ include "svc.name" . }}
      image: {{ include "svc.image" . | quote }}
      imagePullPolicy: {{ .Values.image.pullPolicy }}
      securityContext: {{- toYaml .Values.containerSecurityContext | nindent 8 }}
      ports:
        - name: {{ .Values.service.portName }}
          containerPort: {{ .Values.service.port }}
          protocol: TCP
        {{- range .Values.service.extraPorts }}
        - name: {{ .name }}
          containerPort: {{ .port }}
          protocol: {{ .protocol | default "TCP" }}
        {{- end }}
      {{- if or .Values.config .Values.secretEnv .Values.extraEnv }}
      env:
        {{- range $k, $v := .Values.config }}
        - name: {{ $k }}
          valueFrom:
            configMapKeyRef:
              name: {{ include "svc.fullname" $ }}-config
              key: {{ $k }}
        {{- end }}
        {{- range $k, $s := .Values.secretEnv }}
        - name: {{ $k }}
          valueFrom:
            secretKeyRef:
              name: {{ $s.secretName }}
              key: {{ $s.key }}
              {{- if hasKey $s "optional" }}
              optional: {{ $s.optional }}
              {{- end }}
        {{- end }}
        {{- with .Values.extraEnv }}{{- toYaml . | nindent 8 }}{{- end }}
      {{- end }}
      {{- if .Values.probes.enabled }}
      {{- if .Values.probes.httpGet }}
      readinessProbe:
        httpGet: { path: {{ .Values.probes.path }}, port: {{ .Values.service.portName }} }
        initialDelaySeconds: {{ .Values.probes.initialDelaySeconds }}
        periodSeconds: {{ .Values.probes.periodSeconds }}
      livenessProbe:
        httpGet: { path: {{ .Values.probes.path }}, port: {{ .Values.service.portName }} }
        initialDelaySeconds: {{ add .Values.probes.initialDelaySeconds 10 }}
        periodSeconds: {{ .Values.probes.periodSeconds }}
      {{- else }}
      readinessProbe:
        tcpSocket: { port: {{ .Values.service.portName }} }
        initialDelaySeconds: {{ .Values.probes.initialDelaySeconds }}
        periodSeconds: {{ .Values.probes.periodSeconds }}
      {{- end }}
      {{- end }}
      resources: {{- toYaml .Values.resources | nindent 8 }}
      {{- if or .Values.tmpDir.enabled .Values.writableDirs .Values.extraFileMounts .Values.persistence.enabled }}
      volumeMounts:
        {{- if .Values.persistence.enabled }}
        - name: data
          mountPath: {{ .Values.persistence.mountPath }}
        {{- end }}
        {{- if .Values.tmpDir.enabled }}
        - name: tmp
          mountPath: /tmp
        {{- end }}
        {{- range $i, $p := .Values.writableDirs }}
        - name: writable-{{ $i }}
          mountPath: {{ $p }}
        {{- end }}
        {{- range $i, $m := .Values.extraFileMounts }}
        # Overlay a single file (e.g. firebase-config.js) from a ConfigMap onto the built image.
        # Injected at deploy, NOT baked into the image — keeps public-but-not-secret runtime config
        # (Firebase web config) out of the git-tracked source + image layers. readOnly by nature.
        - name: filemount-{{ $i }}
          mountPath: {{ $m.mountPath }}
          subPath: {{ $m.subPath | default $m.key }}
          readOnly: true
        {{- end }}
      {{- end }}
  {{- if or .Values.tmpDir.enabled .Values.writableDirs .Values.extraFileMounts .Values.persistence.enabled }}
  volumes:
    {{- if .Values.persistence.enabled }}
    - name: data
      persistentVolumeClaim:
        claimName: {{ include "svc.fullname" . }}-data
    {{- end }}
    {{- if .Values.tmpDir.enabled }}
    - name: tmp
      emptyDir:
        sizeLimit: {{ .Values.tmpDir.sizeLimit }}
    {{- end }}
    {{- range $i, $p := .Values.writableDirs }}
    - name: writable-{{ $i }}
      emptyDir: {}
    {{- end }}
    {{- range $i, $m := .Values.extraFileMounts }}
    - name: filemount-{{ $i }}
      configMap:
        name: {{ $m.configMap }}
        items:
          - key: {{ $m.key }}
            path: {{ $m.subPath | default $m.key }}
    {{- end }}
  {{- end }}
  {{- with .Values.nodeSelector }}
  nodeSelector: {{- toYaml . | nindent 4 }}
  {{- end }}
  {{- with .Values.tolerations }}
  tolerations: {{- toYaml . | nindent 4 }}
  {{- end }}
  {{- with .Values.affinity }}
  affinity: {{- toYaml . | nindent 4 }}
  {{- end }}
{{- end -}}
