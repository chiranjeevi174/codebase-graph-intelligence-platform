export async function fetchUsers(): Promise<any> {
    const response = await fetch("/api/users");
    return response.json();
}

export async function createNewUser(userData: any): Promise<any> {
    return axios.post("/api/users", userData);
}
