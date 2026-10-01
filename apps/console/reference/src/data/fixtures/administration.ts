export interface AdministrationUser {
  name: string;
  role: string;
  access: string;
  status: string;
}
export const administrationUsers: AdministrationUser[] = [
  {
    name: "Mike Prickett",
    role: "Agency owner",
    access: "Portfolio and administration",
    status: "Active",
  },
  {
    name: "Alex Rivera · sample user",
    role: "Account manager",
    access: "Client operations",
    status: "Active",
  },
  {
    name: "Jordan Lee · sample user",
    role: "Client viewer",
    access: "Assigned client only",
    status: "Invited",
  },
];
