package main

import "net/http"

func RegisterRoutes() {
    http.HandleFunc("/api/users", handleUsers)
}

func handleUsers(w http.ResponseWriter, r *http.Request) {
    w.Write([]byte("users"))
}
