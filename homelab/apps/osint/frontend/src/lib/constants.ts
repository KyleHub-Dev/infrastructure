export const entityColors: Record<string, string> = {
  Person: "#8b5ccc",
  Username: "#5c83cc",
  Email: "#53a3ad",
  Domain: "#53ad7a",
  IPAddress: "#cc5c5c",
  PlatformAccount: "#9966b3",
  Phone: "#7a8299",
};

export function statusTextClass(status: string): string {
  switch (status) {
    case "running": return "text-success";
    case "completed": return "text-primary";
    case "failed": return "text-error";
    default: return "text-muted-foreground";
  }
}

export function statusDotClass(status: string): string {
  switch (status) {
    case "running": return "bg-success";
    case "completed": return "bg-primary";
    case "failed": return "bg-error";
    default: return "bg-muted-foreground";
  }
}

export const inputClass =
  "w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground focus:ring-1 focus:ring-ring focus:outline-none";

export const selectClass = `${inputClass} cursor-pointer appearance-none bg-[url('data:image/svg+xml,%3Csvg%20width%3D%2210%22%20height%3D%226%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cpath%20d%3D%22M0%200l5%206%205-6z%22%20fill%3D%22%238b5cf6%22%2F%3E%3C%2Fsvg%3E')] bg-no-repeat bg-[position:right_12px_center]`;
