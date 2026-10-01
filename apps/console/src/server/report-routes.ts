const uuid = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}";
export const reportRoutes = [
  {
    pattern: new RegExp(`^organizations/${uuid}/command-center/reports/$`),
    method: "GET",
    upstream: "",
    query: [],
  },
] as const;
