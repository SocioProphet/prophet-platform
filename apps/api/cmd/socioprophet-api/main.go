package main

import (
	"bufio"
	"fmt"
	"log"
	"net"
	"os"
)

func main() {
	sock := getenv("TRITRPC_SOCK", "/tmp/socioprophet.sock")
	_ = os.Remove(sock)
	ln, err := net.Listen("unix", sock)
	if err != nil {
		log.Fatalf("listen error: %v", err)
	}
	defer ln.Close()
	log.Printf("SocioProphet API (UDS) listening at %s", sock)
	for {
		c, err := ln.Accept()
		if err != nil {
			log.Printf("accept error: %v", err)
			continue
		}
		go handle(c)
	}
}

func handle(c net.Conn) {
	defer c.Close()
	r := bufio.NewReader(c)
	line, err := r.ReadString('\n')
	if err != nil {
		return
	}
	if line == "PING\n" {
		fmt.Fprint(c, "PONG\n")
		return
	}
	fmt.Fprint(c, "ERR unknown\n")
}

func getenv(k, d string) string {
	if v := os.Getenv(k); v != "" { return v }
	return d
}
