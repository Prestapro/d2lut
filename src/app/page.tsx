'use client';

import { useState, useEffect, useCallback, Suspense } from 'react';
import { StatsCards } from '@/components/stats-cards';
import { CategoryTabs } from '@/components/category-tabs';
import { ItemPriceTable } from '@/components/item-price-table';
import { FilterBuilder } from '@/components/filter-builder';
import { PriceHistoryModal } from '@/components/price-history-modal';
import { D2Item, TIER_COLORS } from '@/lib/d2r-data';
import { RefreshCw, Github, Download } from 'lucide-react';
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
}

export default function Home() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [items, setItems] = useState<D2Item[]>([]);
  const [categories, setCategories] = useState<Stats['categories']>([]);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState<D2Item | null>(null);
  const [isBuilding, setIsBuilding] = useState(false);

  // Fetch stats
  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch('/api/stats');
      const data = await res.json();
      setStats(data);
      setCategories(data.categories || []);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  }, []);

  // Fetch items
  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (activeCategory) {
        params.set('category', activeCategory);
      }
      const res = await fetch(`/api/items?${params.toString()}`);
      const data: ItemsResponse = await res.json();
      setItems(data.items);
    } catch (error) {
      console.error('Failed to fetch items:', error);
    } finally {
      setLoading(false);
    }
  }, [activeCategory]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  // Build filter
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

  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-gradient-to-b from-zinc-950 via-zinc-900 to-zinc-950 text-white">
      {/* Header */}
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

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8 space-y-8">
        {/* Stats */}
        {stats && <StatsCards stats={stats} />}
        {/* Category Tabs */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-zinc-300">Browse Items</h2>
          <Suspense fallback={<div className="text-zinc-500">Loading categories...</div>}>
            <CategoryTabs
              categories={categories}
              activeCategory={activeCategory}
              onCategoryChange={setActiveCategory}
            />
          </Suspense>
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Items Table */}
          <div className="lg:col-span-3">
            {loading ? (
              <div className="text-center py-12 text-zinc-500">
                <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4" />
                Loading items...
              </div>
            ) : (
              <Suspense fallback={<div className="text-zinc-500">Loading items...</div>}>
                <ItemPriceTable
                  items={items}
                  onItemSelect={setSelectedItem}
                />
              </Suspense>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            <FilterBuilder onBuild={handleBuildFilter} isBuilding={isBuilding} />

            {/* Quick Stats */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 space-y-3">
              <h3 className="font-semibold text-zinc-300">Tier Legend</h3>
              <div className="space-y-2">
                {Object.entries(TIER_COLORS).map(([tier, color]) => {
                  const ranges: Record<string, string> = {
                    GG: '500+ FG',
                    HIGH: '100-500 FG',
                    MID: '20-100 FG',
                    LOW: '5-20 FG',
                    TRASH: '<5 FG',
                  };
                  return (
                    <div key={tier} className="flex items-center justify-between text-sm">
                      <span style={{ color }} className="font-medium">
                        {tier}
                      </span>
                      <span className="text-zinc-500">{ranges[tier]}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Info */}
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

      {/* Footer */}
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

      {/* Price History Modal */}
      <PriceHistoryModal
        item={selectedItem}
        open={!!selectedItem}
        onClose={() => setSelectedItem(null)}
      />
    </div>
  );
}
