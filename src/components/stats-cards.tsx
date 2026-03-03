'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TIER_COLORS } from '@/lib/d2r-data';

interface StatsCardsProps {
  stats: {
    totalItems?: number;
    avgPrice?: number;
    topItem?: {
      displayName: string;
      priceFg?: number;
      tier?: string;
    };
    ggItems?: number;
    highItems?: number;
    lastUpdated?: string;
  } | null;
}

export function StatsCards({ stats }: StatsCardsProps) {
  // Provide safe defaults
  const safeStats = {
    totalItems: stats?.totalItems ?? 0,
    avgPrice: stats?.avgPrice ?? 0,
    topItem: stats?.topItem ?? null,
    ggItems: stats?.ggItems ?? 0,
    highItems: stats?.highItems ?? 0,
  };

  const cards = [
    {
      title: 'Total Items',
      value: safeStats.totalItems.toString(),
      description: 'Items tracked',
      icon: '📦',
    },
    {
      title: 'Average Price',
      value: `${safeStats.avgPrice.toFixed(1)} FG`,
      description: 'Across all items',
      icon: '💰',
    },
    {
      title: 'Top Value Item',
      value: safeStats.topItem?.displayName || 'N/A',
      description: safeStats.topItem ? `${safeStats.topItem.priceFg?.toFixed(0) ?? 0} FG` : '',
      icon: '👑',
      tier: safeStats.topItem?.tier,
    },
    {
      title: 'GG + HIGH Items',
      value: `${safeStats.ggItems + safeStats.highItems}`,
      description: `${safeStats.ggItems} GG, ${safeStats.highItems} HIGH`,
      icon: '⭐',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <Card key={card.title} className="bg-zinc-900 border-zinc-800">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">
              {card.title}
            </CardTitle>
            <span className="text-2xl">{card.icon}</span>
          </CardHeader>
          <CardContent>
            <div
              className="text-2xl font-bold"
              style={{
                color: card.tier ? TIER_COLORS[card.tier] : '#ffd700'
              }}
            >
              {card.value}
            </div>
            <p className="text-xs text-zinc-500 mt-1">{card.description}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
