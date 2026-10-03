import { TSUserService } = require('./service');

function runApp(): void {
    const service = new TSUserService();
    service.createUser("Charlie");
}

runApp();
