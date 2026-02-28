import { useState } from "react";

interface SearchBarProps {
  onInvestigate: (query: string, type: string) => void;
}

export function SearchBar({ onInvestigate }: SearchBarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchType, setSearchType] = useState<"username" | "email" | "domain" | "ip">("username");

  return (
    <div className="flex items-center gap-3 px-5 py-2.5 border-b border-border/50 bg-card/60 shrink-0">
      <input
        className="flex-1 max-w-[480px] bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:ring-1 focus:ring-ring focus:outline-none"
        type="text"
        placeholder="Search target..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
      />
      <div className="flex">
        {(["username", "email", "domain", "ip"] as const).map((t, i) => (
          <button
            key={t}
            className={`border border-border text-xs px-3 py-1.5 capitalize transition-colors hover:bg-secondary/80 hover:text-foreground
              ${searchType === t ? "bg-secondary text-primary border-primary/50" : "bg-transparent text-muted-foreground"}
              ${i === 0 ? "rounded-l-md" : ""} ${i === 3 ? "rounded-r-md" : ""} ${i > 0 ? "-ml-px" : ""}
            `}
            onClick={() => setSearchType(t)}
          >
            {t}
          </button>
        ))}
      </div>
      <button
        className="bg-primary/15 border border-primary/50 text-primary font-semibold text-xs px-5 py-2 rounded-md transition-colors hover:bg-primary/25"
        onClick={() => {
          if (!searchQuery.trim()) return;
          onInvestigate(searchQuery, searchType);
          setSearchQuery("");
        }}
      >
        Investigate
      </button>
    </div>
  );
}
