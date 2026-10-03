const { JSUserService } = require('./service');

function main() {
    const service = new JSUserService();
    service.createUser("Bob");
}

main();
