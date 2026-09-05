import { Link } from "react-router-dom";

export interface BreadcrumbItem {
  label: string;
  to: string;
}

export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
      {items.map((item, index) => (
        <span key={item.to} className="flex items-center gap-2">
          {index > 0 && <span>/</span>}
          <Link to={item.to} className="hover:text-foreground hover:underline">
            {item.label}
          </Link>
        </span>
      ))}
    </nav>
  );
}
