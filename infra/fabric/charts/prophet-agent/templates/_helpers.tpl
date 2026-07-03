{- define "prophet-agent.fullname" -}
{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" -}
{- end -}
