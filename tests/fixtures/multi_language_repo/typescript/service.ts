export interface UserInterface {
    id: string;
    name: string;
}

export class BaseTSService {
    protected debug(msg: string): void {
        console.debug(msg);
    }
}

export class TSUserService extends BaseTSService implements UserInterface {
    id: string = "1";
    name: string = "Default";

    createUser(username: string): UserInterface {
        this.debug("Creating TS User " + username);
        return { id: "101", name: username };
    }
}
