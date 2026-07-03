{- define "prophet-ingest-gateway.fullname" -}
{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" -}
{- end -}
