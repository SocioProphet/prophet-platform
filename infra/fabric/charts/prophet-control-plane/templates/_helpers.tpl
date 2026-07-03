{- define "prophet-control-plane.fullname" -}
{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" -}
{- end -}
