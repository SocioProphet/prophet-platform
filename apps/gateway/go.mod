module github.com/SocioProphet/prophet-platform/apps/gateway

go 1.25.0

require github.com/SocioProphet/prophet-platform/libs/go/tritrpcbridge v0.0.0

require (
	golang.org/x/crypto v0.49.0 // indirect
	golang.org/x/sys v0.42.0 // indirect
)

replace github.com/SocioProphet/prophet-platform/libs/go/tritrpcbridge => ../../libs/go/tritrpcbridge
