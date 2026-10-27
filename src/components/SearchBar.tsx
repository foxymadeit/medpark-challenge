import { MagnifyingGlassIcon } from '@phosphor-icons/react';
import type { ReactNode } from 'react';

/** Search row above a list (History, Participants): the search field on the left, optional filters on the right. */
export function SearchBar({ value, onChange, placeholder, children }: { value: string; onChange: (value: string) => void; placeholder: string; children?: ReactNode }) {
  return (
    <div className="search-bar">
      <label className="search">
        <MagnifyingGlassIcon size={16} aria-hidden />
        <span className="sr-only">{placeholder}</span>
        <input type="search" placeholder={placeholder} value={value} onChange={(e) => onChange(e.target.value)} />
      </label>
      {children}
    </div>
  );
}
