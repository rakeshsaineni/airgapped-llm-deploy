{{- define "llm-stack.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "llm-stack.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "llm-stack.labels" -}}
app.kubernetes.io/name: {{ include "llm-stack.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/* registry override + digest pinning: <registry>/<repo>@sha256:... or <repo>:<tag> */}}
{{- define "llm-stack.image" -}}
{{- $repo := .img.repository -}}
{{- if .global.imageRegistry -}}
{{- $parts := splitList "/" $repo -}}
{{- if gt (len $parts) 2 -}}
{{- $repo = printf "%s/%s" .global.imageRegistry (join "/" (rest $parts)) -}}
{{- else -}}
{{- $repo = printf "%s/%s" .global.imageRegistry $repo -}}
{{- end -}}
{{- end -}}
{{- if .img.digest -}}
{{- printf "%s@%s" $repo .img.digest -}}
{{- else -}}
{{- printf "%s:%s" $repo .img.tag -}}
{{- end -}}
{{- end -}}

{{- define "llm-stack.podSecurity" -}}
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  fsGroup: 10001
  seccompProfile:
    type: RuntimeDefault
{{- end -}}

{{- define "llm-stack.containerSecurity" -}}
securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: ["ALL"]
{{- end -}}
