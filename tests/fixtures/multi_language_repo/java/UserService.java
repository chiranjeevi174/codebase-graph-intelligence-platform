package com.example.service;

public interface UserOperation {
    void processUser(String name);
}

public class UserService extends BaseService implements UserOperation {
    public UserService() {}

    @Override
    public void processUser(String name) {
        logMessage("Processing user: " + name);
    }
}
