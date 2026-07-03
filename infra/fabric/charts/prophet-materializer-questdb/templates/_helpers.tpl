{- define "prophet-materializer-questdb.fullname" -}
{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" -}
{- end -}
