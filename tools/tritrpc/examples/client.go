package main

import (
	"bufio"
	"fmt"
	"net"
	"os"
)

func main() {
	sock := getenv("TRITRPC_SOCK", "/tmp/socioprophet.sock")
	c, err := net.Dial("unix", sock)
	if err != nil { panic(err) }
	defer c.Close()
	fmt.Fprint(c, "PING\n")
	s := bufio.NewScanner(c)
	s.Scan()
	fmt.Println("recv:", s.Text())
}
func getenv(k, d string) string { if v := os.Getenv(k); v != "" { return v }; return d }
