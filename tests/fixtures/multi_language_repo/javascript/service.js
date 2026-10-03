class BaseLogger {
    log(msg) {
        console.log(msg);
    }
}

class JSUserService extends BaseLogger {
    createUser(name) {
        this.log("Creating user " + name);
        return { name: name };
    }
}

module.exports = { JSUserService };
