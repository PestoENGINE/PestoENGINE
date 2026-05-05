export interface Asset {
  id: string;
  ticker: string;
  desiredPercentage: number;
  shares: number;
  fees: number;
  percentageFee: boolean;
}

export interface Settings {
  increment: number;
  onlyBuy: boolean;
  optimalRedistribute: boolean;
}

export interface AssetResultOut {
  id: number;
  ticker: string;
  current_percentage: number;
  desired_percentage: number;
  shares: number;
  allocated: number;
  ticker_price: number;
  fees: number;
  buy: number;
}

export interface RebalanceResponse {
  results: AssetResultOut[];
  total_fees: number;
  change: number;
}

export interface PortfolioExport {
  version: 1;
  exportedAt: string;
  settings: Settings;
  assets: Omit<Asset, 'id'>[];
}
