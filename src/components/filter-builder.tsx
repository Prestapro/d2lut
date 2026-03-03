'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Download, Settings, RefreshCw, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

interface FilterBuilderProps {
  onBuild: (preset: string, threshold: number) => void;
  isBuilding?: boolean;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export function FilterBuilder({ onBuild, isBuilding = false, onRefresh, isRefreshing = false }: FilterBuilderProps) {
  const [preset, setPreset] = useState('default');
  const [threshold, setThreshold] = useState(0);

  const presets = [
    { id: 'default', name: 'Default', description: 'Balanced filter with all items' },
    { id: 'roguecore', name: 'Rogue Core', description: 'Minimal HC-focused filter' },
    { id: 'minimal', name: 'Minimal', description: 'Hide low value items' },
    { id: 'verbose', name: 'Verbose', description: 'Show all items with details' },
  ];

  const handleBuild = () => {
    onBuild(preset, threshold);
  };

  const handleRefreshPrices = async () => {
    if (!onRefresh) return;
    onRefresh();
  };

  return (
    <Card className="bg-zinc-900 border-zinc-800">
      <CardHeader className="pb-3">
        <CardTitle className="text-white flex items-center gap-2">
          <Settings className="h-5 w-5 text-amber-500" />
          Filter Builder
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="preset" className="text-zinc-400">
              Preset
            </Label>
            <Select value={preset} onValueChange={setPreset}>
              <SelectTrigger className="bg-zinc-800 border-zinc-700 text-white">
                <SelectValue placeholder="Select preset" />
              </SelectTrigger>
              <SelectContent className="bg-zinc-800 border-zinc-700">
                {presets.map((p) => (
                  <SelectItem
                    key={p.id}
                    value={p.id}
                    className="text-white hover:bg-zinc-700 focus:bg-zinc-700"
                  >
                    <div>
                      <div className="font-medium">{p.name}</div>
                      <div className="text-xs text-zinc-400">{p.description}</div>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="threshold" className="text-zinc-400">
              Min Price Threshold (FG)
            </Label>
            <Input
              id="threshold"
              type="number"
              min="0"
              step="5"
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value) || 0)}
              className="bg-zinc-800 border-zinc-700 text-white"
              placeholder="0"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <Button
            onClick={handleBuild}
            disabled={isBuilding}
            className="bg-amber-600 hover:bg-amber-700 text-white"
          >
            {isBuilding ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Download className="mr-2 h-4 w-4" />
            )}
            {isBuilding ? 'Building...' : 'Download'}
          </Button>
          
          {onRefresh && (
            <Button
              onClick={handleRefreshPrices}
              disabled={isRefreshing}
              variant="outline"
              className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
            >
              {isRefreshing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              {isRefreshing ? 'Scraping...' : 'Refresh Prices'}
            </Button>
          )}
        </div>

        <p className="text-xs text-zinc-500 text-center">
          Downloads a .filter file for Diablo 2 Resurrected
        </p>
        
        {onRefresh && (
          <p className="text-xs text-zinc-600 text-center">
            Refresh prices from d2jsp forum (takes ~30s)
          </p>
        )}
      </CardContent>
    </Card>
  );
}
