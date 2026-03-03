'use client';

import { Button } from '@/components/ui/button';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';

interface Category {
  id: string;
  name: string;
  count: number;
  icon: string;
}

interface CategoryTabsProps {
  categories: Category[];
  activeCategory: string | null;
  onCategoryChange: (category: string | null) => void;
}

export function CategoryTabs({ categories, activeCategory, onCategoryChange }: CategoryTabsProps) {
  return (
    <ScrollArea className="w-full whitespace-nowrap">
      <div className="flex gap-2 pb-2">
        <Button
          variant={activeCategory === null ? 'default' : 'outline'}
          size="sm"
          onClick={() => onCategoryChange(null)}
          className={activeCategory === null
            ? 'bg-amber-600 hover:bg-amber-700 text-white'
            : 'border-zinc-700 text-zinc-300 hover:text-white hover:bg-zinc-800'
          }
        >
          📋 All ({categories.reduce((sum, c) => sum + c.count, 0)})
        </Button>
        {categories.map((category) => (
          <Button
            key={category.id}
            variant={activeCategory === category.id ? 'default' : 'outline'}
            size="sm"
            onClick={() => onCategoryChange(category.id)}
            className={activeCategory === category.id
              ? 'bg-amber-600 hover:bg-amber-700 text-white'
              : 'border-zinc-700 text-zinc-300 hover:text-white hover:bg-zinc-800'
            }
          >
            {category.icon} {category.name} ({category.count})
          </Button>
        ))}
      </div>
      <ScrollBar orientation="horizontal" />
    </ScrollArea>
  );
}
