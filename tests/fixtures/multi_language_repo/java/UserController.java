package com.example.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class UserController {

    @GetMapping("/api/users")
    public String getUsers() {
        return "user_list";
    }

    @PostMapping("/api/users")
    public String createUser() {
        return "user_created";
    }
}
