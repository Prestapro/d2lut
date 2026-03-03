'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TIER_COLORS } from '@/lib/d2r-data';

interface StatsCardsProps {
  stats: {
    totalItems: number;
    avgPrice: number;
    topItem?: {
      displayName: string;
      priceFg?: number;
      tier?: string;
    };
    ggItems: number;
    highItems: number;
    lastUpdated: string;
  };
}

export function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    {
      title: 'Total Items',
      value: stats.totalItems.toString(),
      description: 'Items tracked',
      icon: '📦',
    },
    {
      title: 'Average Price',
      value: `${stats.avgPrice.toFixed(1)} FG`,
      description: 'Across all items',
      icon: '💰',
    },
    {
      title: 'Top Value Item',
      value: stats.topItem?.displayName || 'N/A',
      description: stats.topItem ? `${stats.topItem.priceFg?.toFixed(0)} FG` : '',
      icon: '👑',
      tier: stats.topItem?.tier,
    },
    {
      title: 'GG + HIGH Items',
      value: `${stats.ggItems + stats.highItems}`,
      description: `${stats.ggItems} GG, ${stats.highItems} HIGH`,
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
