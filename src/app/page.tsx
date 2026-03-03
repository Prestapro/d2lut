import { Suspense } from 'react';
import { HomePageClient } from '@/components/home-page-client';

export default function Home() {
  return (
    <Suspense fallback={null}>
      <HomePageClient />
    </Suspense>
  );
}
