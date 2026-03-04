'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { StatsCards } from '@/components/stats-cards';
import { CategoryTabs } from '@/components/category-tabs';
import { ItemPriceTable, SortField, SortOrder } from '@/components/item-price-table';
import { FilterBuilder } from '@/components/filter-builder';
import { PriceHistoryModal } from '@/components/price-history-modal';
import { D2Item, TIER_COLORS, TIER_LABELS } from '@/lib/d2r-utils';
import { RefreshCw, Github } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

interface Stats {
  totalItems: number;
  avgPrice: number;
  topItem?: D2Item;
  ggItems: number;
  highItems: number;
  lastUpdated: string;
  categories: Array<{
    id: string;
    name: string;
    count: number;
    icon: string;
  }>;
}

interface ItemsResponse {
  items: D2Item[];
  total: number;
  limit: number;
  offset: number;
  hasMore: boolean;
}

export function HomePageClient() {
  const [mounted, setMounted] = useState(false);
  const [stats, setStats] = useState<Stats | null>(null);
  const [items, setItems] = useState<D2Item[]>([]);
  const [categories, setCategories] = useState<Stats['categories']>([]);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [tierFilter, setTierFilter] = useState<string>('all');
  const [sortField, setSortField] = useState<SortField>('price');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [offset, setOffset] = useState(0);
  const [limit] = useState(100);
  const [totalItems, setTotalItems] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState<D2Item | null>(null);
  const [isBuilding, setIsBuilding] = useState(false);

  useEffect(() => {
    setMounted(true);

    const params = new URLSearchParams(window.location.search);
    const category = params.get('category');
    const initialSearch = params.get('search') || '';
    const tier = params.get('tier') || 'all';
    const sort = params.get('sort');
    const order = params.get('order');
    const offsetRaw = Number.parseInt(params.get('offset') || '0', 10);

    setActiveCategory(category);
    setSearch(initialSearch);
    setDebouncedSearch(initialSearch.trim());
    setTierFilter(tier);
    setSortField(sort === 'name' || sort === 'category' || sort === 'price' ? sort : 'price');
    setSortOrder(order === 'asc' || order === 'desc' ? order : 'desc');
    setOffset(Number.isFinite(offsetRaw) && offsetRaw >= 0 ? offsetRaw : 0);
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search.trim()), 250);
    return () => clearTimeout(timer);
  }, [search]);

  const hasInitializedFilters = useRef(false);

  useEffect(() => {
    if (!hasInitializedFilters.current) {
      hasInitializedFilters.current = true;
      return;
    }
    setOffset(0);
  }, [activeCategory, tierFilter, sortField, sortOrder, debouncedSearch]);

  useEffect(() => {
    if (!mounted) return;

    const params = new URLSearchParams();

    if (activeCategory) params.set('category', activeCategory);
    if (debouncedSearch) params.set('search', debouncedSearch);
    if (tierFilter !== 'all') params.set('tier', tierFilter);
    if (sortField !== 'price') params.set('sort', sortField);
    if (sortOrder !== 'desc') params.set('order', sortOrder);
    if (offset > 0) params.set('offset', String(offset));

    const query = params.toString();
    const basePath = window.location.pathname || '/';
    const nextUrl = query ? `${basePath}?${query}` : basePath;
    window.history.replaceState(null, '', nextUrl);
  }, [activeCategory, debouncedSearch, tierFilter, sortField, sortOrder, offset, mounted]);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch('/api/stats');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setStats(data);
      setCategories(data.categories || []);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
      toast.error('Failed to load stats');
    }
  }, []);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (activeCategory) {
        params.set('category', activeCategory);
      }
      if (debouncedSearch) {
        params.set('search', debouncedSearch);
      }
      if (tierFilter !== 'all') {
        params.set('tier', tierFilter);
      }
      params.set('sort', sortField);
      params.set('order', sortOrder);
      params.set('minPrice', '0');
      params.set('limit', String(limit));
      params.set('offset', String(offset));
      const res = await fetch(`/api/items?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ItemsResponse = await res.json();
      setItems(data.items);
      setTotalItems(data.total);
    } catch (error) {
      console.error('Failed to fetch items:', error);
      toast.error('Failed to load items');
    } finally {
      setLoading(false);
    }
  }, [activeCategory, debouncedSearch, tierFilter, sortField, sortOrder, limit, offset]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  const handleBuildFilter = async (preset: string, threshold: number) => {
    setIsBuilding(true);
    try {
      const res = await fetch('/api/filter/build', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset, threshold }),
      });

      if (!res.ok) throw new Error('Failed to build filter');

      const content = await res.text();
      const blob = new Blob([content], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `d2lut_${preset}_${Date.now()}.filter`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      toast.success('Filter downloaded successfully!');
    } catch (error) {
      console.error('Failed to build filter:', error);
      toast.error('Failed to build filter');
    } finally {
      setIsBuilding(false);
    }
  };

  if (!mounted) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-zinc-950 via-zinc-900 to-zinc-950 text-white">
        <div className="container mx-auto px-4 py-16">
          <div className="text-center py-12 text-zinc-500">
            <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4" />
            Loading dashboard...
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-zinc-950 via-zinc-900 to-zinc-950 text-white">
      <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
                <span className="text-xl">⚔️</span>
              </div>
              <div>
                <h1 className="text-xl font-bold bg-gradient-to-r from-amber-400 to-orange-500 bg-clip-text text-transparent">
                  D2LUT
                </h1>
                <p className="text-xs text-zinc-500">D2R Loot Filter Generator</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  fetchStats();
                  fetchItems();
                }}
                className="text-zinc-400 hover:text-white"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
              <a
                href="https://github.com/Prestapro/d2lut"
                target="_blank"
                rel="noopener noreferrer"
                className="text-zinc-400 hover:text-white"
              >
                <Github className="h-5 w-5" />
              </a>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 space-y-8">
        {stats && <StatsCards stats={stats} />}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-zinc-300">Browse Items</h2>
          <CategoryTabs
            categories={categories}
            activeCategory={activeCategory}
            onCategoryChange={setActiveCategory}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-3">
            {loading ? (
              <div className="text-center py-12 text-zinc-500">
                <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4" />
                Loading items...
              </div>
            ) : (
              <ItemPriceTable
                items={items}
                total={totalItems}
                limit={limit}
                offset={offset}
                search={search}
                tierFilter={tierFilter}
                sortField={sortField}
                sortOrder={sortOrder}
                onSearchChange={setSearch}
                onTierFilterChange={setTierFilter}
                onSortChange={(field, order) => {
                  setSortField(field);
                  setSortOrder(order);
                }}
                onPageChange={setOffset}
                onItemSelect={setSelectedItem}
              />
            )}
          </div>

          <div className="space-y-6">
            <FilterBuilder onBuild={handleBuildFilter} isBuilding={isBuilding} />

            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 space-y-3">
              <h3 className="font-semibold text-zinc-300">Tier Legend</h3>
              <div className="space-y-2">
                {Object.entries(TIER_COLORS).map(([tier, color]) => (
                  <div key={tier} className="flex items-center justify-between text-sm">
                    <span style={{ color }} className="font-medium">
                      {tier}
                    </span>
                    <span className="text-zinc-500">{TIER_LABELS[tier]}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 space-y-2 text-sm text-zinc-400">
              <p>
                💡 <strong className="text-white">Tip:</strong> Click on any item to view its price history.
              </p>
              <p>
                📊 Prices are sourced from d2jsp forum observations and updated regularly.
              </p>
            </div>
          </div>
        </div>
      </main>

      <footer className="border-t border-zinc-800 py-6 mt-12">
        <div className="container mx-auto px-4 text-center text-sm text-zinc-500">
          <p>
            D2LUT - D2R Loot Filter Generator • Built with ❤️ for the Diablo 2 community
          </p>
          <p className="mt-1">
            Data sourced from d2jsp.org • Not affiliated with Blizzard Entertainment
          </p>
        </div>
      </footer>

      <PriceHistoryModal
        item={selectedItem}
        open={!!selectedItem}
        onClose={() => setSelectedItem(null)}
      />
    </div>
  );
}
