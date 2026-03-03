'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { D2Item, TIER_COLORS } from '@/lib/d2r-utils';
import { XCircle } from 'lucide-react';

interface PriceData {
  date: string;
  price: number;
}

interface PriceHistoryResponse {
  item: D2Item;
  history: PriceData[];
  minPrice: number;
  maxPrice: number;
  avgPrice: number;
}

interface PriceHistoryModalProps {
  item: D2Item | null;
  open: boolean;
  onClose: () => void;
}

export function PriceHistoryModal({ item, open, onClose }: PriceHistoryModalProps) {
  const [history, setHistory] = useState<PriceHistoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const fetchingRef = useRef(false);

  const fetchHistory = useCallback(async (variantKey: string) => {
    if (fetchingRef.current) return;
    fetchingRef.current = true;
    setLoading(true);
    
    try {
      const res = await fetch(`/api/prices/${encodeURIComponent(variantKey)}`);
      if (!res.ok) {
        throw new Error(`Failed to fetch history: HTTP ${res.status}`);
      }
      const data = await res.json();
      setHistory(data);
    } catch (error) {
      console.error('Failed to fetch history:', error);
      setHistory(null);
    } finally {
      setLoading(false);
      fetchingRef.current = false;
    }
  }, []);

  useEffect(() => {
    if (item && open) {
      fetchHistory(item.variantKey);
    }
  }, [item, open, fetchHistory]);

  // Reset state when modal closes
  useEffect(() => {
    if (!open) {
      setHistory(null);
    }
  }, [open]);

  if (!item) return null;

  const maxHeight = history && history.history.length > 0
    ? Math.max(...history.history.map(h => h.price)) * 1.1
    : 100;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-zinc-900 border-zinc-800 text-white max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            <span
              className="font-bold"
              style={{ color: TIER_COLORS[item.tier || 'TRASH'] }}
            >
              {item.displayName}
            </span>
            <Badge variant="outline" className="border-zinc-700">
              {item.category}
            </Badge>
          </DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="py-8 text-center text-zinc-500">Loading...</div>
        ) : history ? (
          <div className="space-y-6">
            {/* Stats */}
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-amber-400">
                  {item.priceFg != null ? `${item.priceFg.toFixed(1)} FG` : 'N/A'}
                </div>
                <div className="text-xs text-zinc-500">Current Price</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-400">
                  {history.maxPrice.toFixed(1)} FG
                </div>
                <div className="text-xs text-zinc-500">30d High</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-red-400">
                  {history.minPrice.toFixed(1)} FG
                </div>
                <div className="text-xs text-zinc-500">30d Low</div>
              </div>
            </div>

            {/* Simple Bar Chart */}
            <div className="space-y-2">
              <div className="text-sm text-zinc-400">30-Day Price History</div>
              <div className="flex items-end gap-1 h-32 bg-zinc-800/50 rounded p-2">
                {history.history.slice(-14).map((point, i) => {
                  const height = (point.price / maxHeight) * 100;
                  return (
                    <div
                      key={i}
                      className="flex-1 flex flex-col items-center gap-1"
                    >
                      <div
                        className="w-full bg-amber-600/80 rounded-t"
                        style={{ height: `${height}%`, minHeight: '4px' }}
                        title={`${point.date}: ${point.price.toFixed(1)} FG`}
                      />
                      {i % 2 === 0 && (
                        <span className="text-[10px] text-zinc-600">
                          {point.date.slice(5)}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Item Details */}
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-zinc-500">Variant Key: </span>
                <code className="text-zinc-300 bg-zinc-800 px-1 rounded">
                  {item.variantKey}
                </code>
              </div>
              <div>
                <span className="text-zinc-500">D2R Code: </span>
                <code className="text-zinc-300 bg-zinc-800 px-1 rounded">
                  {item.d2rCode || 'N/A'}
                </code>
              </div>
              <div>
                <span className="text-zinc-500">Observations: </span>
                <span className="text-zinc-300">{item.nObservations || 0}</span>
              </div>
              <div>
                <span className="text-zinc-500">Confidence: </span>
                <span
                  className={
                    item.confidence === 'high'
                      ? 'text-green-400'
                      : item.confidence === 'medium'
                      ? 'text-yellow-400'
                      : 'text-red-400'
                  }
                >
                  {item.confidence}
                </span>
              </div>
            </div>

            {/* Close Button */}
            <button
              onClick={onClose}
              className="absolute top-4 right-4 text-zinc-500 hover:text-white"
            >
              <XCircle className="h-5 w-5" />
            </button>
          </div>
        ) : (
          <div className="py-8 text-center text-zinc-500">
            No price history available
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
