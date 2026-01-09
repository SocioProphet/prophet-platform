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
	if err != nil { log.Fatal(err) }
	defer ln.Close()
	log.Printf("exemplar server on %s", sock)
	for {
		c, _ := ln.Accept()
		go func(conn net.Conn) {
			defer conn.Close()
			r := bufio.NewReader(conn)
			line, _ := r.ReadString('\n')
			if line == "PING\n" { fmt.Fprint(conn, "PONG\n") } else { fmt.Fprint(conn, "ERR\n") }
		}(c)
	}
}
func getenv(k, d string) string { if v := os.Getenv(k); v != "" { return v }; return d }
