{{- define "svc.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "svc.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- default .Release.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "svc.labels" -}}
app.kubernetes.io/name: {{ include "svc.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: socioprophet
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- define "svc.selectorLabels" -}}
app: {{ include "svc.fullname" . }}
app.kubernetes.io/name: {{ include "svc.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "svc.image" -}}
{{- $reg := .Values.image.registry | trimSuffix "/" -}}
{{- $repo := required "image.repository is required" .Values.image.repository -}}
{{- $tag := .Values.image.tag | default .Chart.AppVersion -}}
{{- printf "%s/%s:%s" $reg $repo $tag -}}
{{- end -}}

{{/*
The GUARANTEED replica floor — what the cluster will always be running once things
settle. With an HPA the deployment's own `replicas` field is not authoritative (the
chart deliberately omits it, deployment.yaml:7), so the floor is the autoscaler's
minReplicas; without one it is replicaCount.

This is what a PodDisruptionBudget must be reasoned about against. A PDB whose budget
cannot be satisfied by the floor does not "protect" the workload — it wedges every
voluntary eviction, which on Autopilot means node upgrades, repairs and consolidation
all stall against it indefinitely. See pdb.yaml.
*/}}
{{- define "svc.replicaFloor" -}}
{{- if .Values.autoscaling.enabled -}}
{{- .Values.autoscaling.minReplicas -}}
{{- else -}}
{{- .Values.replicaCount -}}
{{- end -}}
{{- end -}}

{{- define "svc.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "svc.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}
