package main

import (
    "encoding/json"
    "errors"
    "io"
    "log"
    "net"
    "os"
    "strings"

    "github.com/SocioProphet/prophet-platform/libs/go/tritrpcbridge/binding"
)

const defaultUnixSocket = "/tmp/socioprophet.sock"

func main() {
    key, err := binding.ResolveSharedKey(os.Getenv("TRITRPC_KEY_HEX"), os.Getenv("TRITRPC_ALLOW_INSECURE_DEV_KEY") == "1")
    if err != nil {
        log.Fatalf("shared key: %v", err)
    }

    listenAddr := firstNonEmpty(os.Getenv("TRITRPC_LISTEN_ADDR"), legacySockAddr())
    ln, resolved, err := binding.Listen(listenAddr, defaultUnixSocket)
    if err != nil {
        log.Fatalf("listen error: %v", err)
    }
    defer ln.Close()
    log.Printf("SocioProphet API (TriTRPC v1) listening at %s", resolved)

    for {
        c, err := ln.Accept()
        if err != nil {
            log.Printf("accept error: %v", err)
            continue
        }
        go handle(c, key)
    }
}

func handle(c net.Conn, key [32]byte) {
    defer c.Close()
    nonce, frame, err := binding.ReadRecord(c)
    if err != nil {
        if !errors.Is(err, io.EOF) {
            log.Printf("read record: %v", err)
        }
        return
    }
    env, err := binding.VerifyEnvelope(frame, nonce, key)
    if err != nil {
        log.Printf("verify envelope: %v", err)
        return
    }

    switch {
    case env.Service == binding.HealthService && env.Method == binding.HealthPingReq:
        handleHealth(c, env, key)
    case env.Service == binding.ValidateChangeService && env.Method == binding.ValidateChangeReq:
        handleValidateChange(c, env, key)
    default:
        log.Printf("unexpected route: %s %s", env.Service, env.Method)
    }
}

func handleHealth(c net.Conn, env interface{ }, key [32]byte) {
    trienv, ok := env.(interface{ })
    _ = trienv
    var req binding.HealthPingRequest
    payloadEnv, ok := any(env).(interface{ })
    _ = payloadEnv
    if err := binding.DecodeJSONPayload(any(env).(*struct{}), &req); err != nil {
        _ = ok
    }
}
