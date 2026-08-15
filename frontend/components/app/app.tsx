'use client';

import type { AppConfig } from '@/app-config';
import { KisanMitraAI } from '@/components/app/kisan-mitra';

interface AppProps {
  appConfig: AppConfig;
}

export function App({ appConfig }: AppProps) {
  return <KisanMitraAI appConfig={appConfig} />;
}
