'use client';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { TIER_COLORS, D2Item } from '@/lib/d2r-data';
import { Search, ArrowUp, ArrowDown, ChevronsUpDown, ChevronLeft, ChevronRight } from 'lucide-react';

interface ItemPriceTableProps {
  items: D2Item[];
  total: number;
  limit: number;
  offset: number;
  search: string;
  tierFilter: string;
  sortField: SortField;
  sortOrder: SortOrder;
  onSearchChange: (value: string) => void;
  onTierFilterChange: (value: string) => void;
  onSortChange: (field: SortField, order: SortOrder) => void;
  onPageChange: (offset: number) => void;
  onItemSelect?: (item: D2Item) => void;
}

export type SortField = 'name' | 'category' | 'price';
export type SortOrder = 'asc' | 'desc';

// Sort icon component defined outside render
function SortIcon({ field, sortField, sortOrder }: { field: SortField; sortField: SortField; sortOrder: SortOrder }) {
  if (sortField !== field) {
    return <ChevronsUpDown className="h-4 w-4 text-zinc-600" />;
  }
  return sortOrder === 'asc'
    ? <ArrowUp className="h-4 w-4 text-amber-500" />
    : <ArrowDown className="h-4 w-4 text-amber-500" />;
}

export function ItemPriceTable({
  items,
  total,
  limit,
  offset,
  search,
  tierFilter,
  sortField,
  sortOrder,
  onSearchChange,
  onTierFilterChange,
  onSortChange,
  onPageChange,
  onItemSelect,
}: ItemPriceTableProps) {
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      onSortChange(field, sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      onSortChange(field, 'desc');
    }
  };

  const showingFrom = total === 0 ? 0 : offset + 1;
  const showingTo = Math.min(offset + items.length, total);

  const disablePrev = offset <= 0;
  const disableNext = offset + limit >= total;

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
          <Input
            placeholder="Search items..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-10 bg-zinc-900 border-zinc-800 text-white placeholder:text-zinc-500"
          />
        </div>
        <Select value={tierFilter} onValueChange={onTierFilterChange}>
          <SelectTrigger className="w-full sm:w-40 bg-zinc-900 border-zinc-800 text-white">
            <SelectValue placeholder="Tier" />
          </SelectTrigger>
          <SelectContent className="bg-zinc-900 border-zinc-800">
            <SelectItem value="all" className="text-white hover:bg-zinc-800 focus:bg-zinc-800">
              All Tiers
            </SelectItem>
            <SelectItem value="GG" className="text-white hover:bg-zinc-800 focus:bg-zinc-800">
              <span style={{ color: TIER_COLORS.GG }}>GG (500+ FG)</span>
            </SelectItem>
            <SelectItem value="HIGH" className="text-white hover:bg-zinc-800 focus:bg-zinc-800">
              <span style={{ color: TIER_COLORS.HIGH }}>HIGH (100-500)</span>
            </SelectItem>
            <SelectItem value="MID" className="text-white hover:bg-zinc-800 focus:bg-zinc-800">
              <span style={{ color: TIER_COLORS.MID }}>MID (20-100)</span>
            </SelectItem>
            <SelectItem value="LOW" className="text-white hover:bg-zinc-800 focus:bg-zinc-800">
              <span style={{ color: TIER_COLORS.LOW }}>LOW (5-20)</span>
            </SelectItem>
            <SelectItem value="TRASH" className="text-white hover:bg-zinc-800 focus:bg-zinc-800">
              <span style={{ color: TIER_COLORS.TRASH }}>TRASH (&lt;5)</span>
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border border-zinc-800 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-zinc-900 hover:bg-zinc-900 border-zinc-800">
              <TableHead className="text-zinc-400">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSort('name')}
                  className="text-zinc-400 hover:text-white"
                >
                  Name
                  <SortIcon field="name" sortField={sortField} sortOrder={sortOrder} />
                </Button>
              </TableHead>
              <TableHead className="text-zinc-400">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSort('category')}
                  className="text-zinc-400 hover:text-white"
                >
                  Category
                  <SortIcon field="category" sortField={sortField} sortOrder={sortOrder} />
                </Button>
              </TableHead>
              <TableHead className="text-zinc-400 text-right">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSort('price')}
                  className="text-zinc-400 hover:text-white"
                >
                  Price (FG)
                  <SortIcon field="price" sortField={sortField} sortOrder={sortOrder} />
                </Button>
              </TableHead>
              <TableHead className="text-zinc-400 text-center">Tier</TableHead>
              <TableHead className="text-zinc-400 text-center">Confidence</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 ? (
              <TableRow className="border-zinc-800">
                <TableCell colSpan={5} className="text-center text-zinc-500 py-8">
                  No items found
                </TableCell>
              </TableRow>
            ) : (
              items.map((item) => (
                <TableRow
                  key={item.variantKey}
                  className="border-zinc-800 hover:bg-zinc-800/50 cursor-pointer"
                  onClick={() => onItemSelect?.(item)}
                >
                  <TableCell className="font-medium text-white">
                    {item.displayName}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="border-zinc-700 text-zinc-400">
                      {item.category}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right font-mono text-amber-400">
                    {item.priceFg?.toFixed(1) || '0'}
                  </TableCell>
                  <TableCell className="text-center">
                    <span
                      className="font-bold px-2 py-1 rounded"
                      style={{
                        color: TIER_COLORS[item.tier || 'TRASH'],
                        backgroundColor: `${TIER_COLORS[item.tier || 'TRASH']}20`,
                      }}
                    >
                      {item.tier}
                    </span>
                  </TableCell>
                  <TableCell className="text-center">
                    <span
                      className={`text-sm ${
                        item.confidence === 'high'
                          ? 'text-green-400'
                          : item.confidence === 'medium'
                          ? 'text-yellow-400'
                          : 'text-red-400'
                      }`}
                    >
                      {item.confidence}
                    </span>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Footer */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-sm">
        <div className="text-zinc-500">
          Showing {showingFrom}-{showingTo} of {total}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(Math.max(0, offset - limit))}
            disabled={disablePrev}
            className="border-zinc-700 text-zinc-300 hover:text-white"
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            Prev
          </Button>
          <span className="text-zinc-500 px-2">
            {currentPage}/{totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(offset + limit)}
            disabled={disableNext}
            className="border-zinc-700 text-zinc-300 hover:text-white"
          >
            Next
            <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
      </div>
    </div>
  );
}
