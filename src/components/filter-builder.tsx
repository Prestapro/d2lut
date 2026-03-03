'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Download, Settings } from 'lucide-react';

interface FilterBuilderProps {
  onBuild: (preset: string, threshold: number) => void;
  isBuilding?: boolean;
}

export function FilterBuilder({ onBuild, isBuilding = false }: FilterBuilderProps) {
  const [preset, setPreset] = useState('default');
  const [threshold, setThreshold] = useState(5);

  const presets = [
    { id: 'default', name: 'Default', description: 'Balanced filter with all items' },
    { id: 'roguecore', name: 'Rogue Core', description: 'Minimal HC-focused filter' },
    { id: 'minimal', name: 'Minimal', description: 'Hide low value items' },
    { id: 'verbose', name: 'Verbose', description: 'Show all items with details' },
  ];

  const handleBuild = () => {
    onBuild(preset, threshold);
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
            <select
              value={preset}
              onChange={(e) => setPreset(e.target.value)}
              className="w-full h-10 px-3 py-2 bg-zinc-800 border border-zinc-700 text-white rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500 text-sm"
            >
              <option value="" disabled className="text-zinc-500">Select preset</option>
              {presets.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} - {p.description}
                </option>
              ))}
            </select>
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
              placeholder="5"
            />
          </div>
        </div>

        <Button
          onClick={handleBuild}
          disabled={isBuilding}
          className="w-full bg-amber-600 hover:bg-amber-700 text-white"
        >
          <Download className="mr-2 h-4 w-4" />
          {isBuilding ? 'Building...' : 'Download Filter'}
        </Button>

        <p className="text-xs text-zinc-500 text-center">
          Downloads a .filter file for Diablo 2 Resurrected
        </p>
      </CardContent>
    </Card>
  );
}
