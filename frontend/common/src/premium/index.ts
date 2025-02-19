import { type MaybeRef } from '@vueuse/core';
import { type ComputedRef, type Ref } from 'vue';
import { type AssetInfo } from '../data';
import { type LpType, type ProfitLossModel } from '../defi';
import {
  type BalancerBalance,
  type BalancerProfitLoss
} from '../defi/balancer';
import {
  type XswapBalance,
  type XswapPool,
  type XswapPoolProfit
} from '../defi/xswap';
import { type AssetBalanceWithPrice, type BigNumber } from '../index';
import {
  type DebugSettings,
  type FrontendSettingsPayload,
  type Theme,
  type Themes,
  type TimeUnit
} from '../settings';
import {
  type LocationData,
  type NetValue,
  type OwnedAssets,
  type TimedAssetBalances,
  type TimedBalances
} from '../statistics';

export interface PremiumInterface {
  readonly useHostComponents: boolean;
  readonly version: number;
  readonly api: () => PremiumApi;
  readonly debug?: DebugSettings;
}

export interface StatisticsApi {
  assetValueDistribution(): Promise<TimedAssetBalances>;
  locationValueDistribution(): Promise<LocationData>;
  ownedAssets(): Promise<OwnedAssets>;
  timedBalances(
    asset: string,
    start: number,
    end: number
  ): Promise<TimedBalances>;
  fetchNetValue(): Promise<void>;
  netValue: (startingData: number) => Ref<NetValue>;
}

export interface DateUtilities {
  epoch(): number;
  format(date: string, oldFormat: string, newFormat: string): string;
  now(format: string): string;
  epochToFormat(epoch: number, format: string): string;
  dateToEpoch(date: string, format: string): number;
  epochStartSubtract(amount: number, unit: TimeUnit): number;
  toUserSelectedFormat(timestamp: number): string;
  getDateInputISOFormat(format: string): string;
  convertToTimestamp(date: string, dateFormat?: string): number;
}

export interface CompoundApi {
  compoundRewards: Ref<ProfitLossModel[]>;
  compoundDebtLoss: Ref<ProfitLossModel[]>;
  compoundLiquidationProfit: Ref<ProfitLossModel[]>;
  compoundInterestProfit: Ref<ProfitLossModel[]>;
}

export interface BalancerApi {
  balancerProfitLoss: (addresses: string[]) => Ref<BalancerProfitLoss[]>;
  balancerBalances: (addresses: string[]) => Ref<BalancerBalance[]>;
  balancerPools: Ref<XswapPool[]>;
  balancerAddresses: Ref<string[]>;
  fetchBalancerBalances: (refresh: boolean) => Promise<void>;
  fetchBalancerEvents: (refresh: boolean) => Promise<void>;
}

export interface SushiApi {
  balances: (addresses: string[]) => Ref<XswapBalance[]>;
  poolProfit: (addresses: string[]) => Ref<XswapPoolProfit[]>;
  addresses: Ref<string[]>;
  pools: Ref<XswapPool[]>;
  fetchBalances: (refresh: boolean) => Promise<void>;
  fetchEvents: (refresh: boolean) => Promise<void>;
}

export interface BalancesApi {
  byLocation: Ref<Record<string, BigNumber>>;
  aggregatedBalances: Ref<AssetBalanceWithPrice[]>;
  exchangeRate: (currency: string) => Ref<BigNumber>;
}

export interface AssetsApi {
  assetInfo(identifier: MaybeRef<string>): ComputedRef<AssetInfo | null>;
  assetSymbol(identifier: MaybeRef<string>): ComputedRef<string>;
  tokenAddress(identifier: MaybeRef<string>): ComputedRef<string>;
}

export interface UtilsApi {
  truncate(text: string, length: number): string;
  getPoolName(type: LpType, assets: string[]): string;
}

export interface DataUtilities {
  readonly assets: AssetsApi;
  readonly utils: UtilsApi;
  readonly statistics: StatisticsApi;
  readonly compound: CompoundApi;
  readonly balancer: BalancerApi;
  readonly balances: BalancesApi;
  readonly sushi: SushiApi;
}

export interface UserSettingsApi {
  currencySymbol: Ref<string>;
  floatingPrecision: Ref<number>;
  shouldShowAmount: Ref<boolean>;
  shouldShowPercentage: Ref<boolean>;
  scrambleData: Ref<boolean>;
  scrambleMultiplier: Ref<number>;
  selectedTheme: Ref<Theme>;
  dateInputFormat: Ref<string>;
  privacyMode: Ref<number>;
  graphZeroBased: Ref<boolean>;
  showGraphRangeSelector: Ref<boolean>;
}

export interface SettingsApi {
  update(settings: FrontendSettingsPayload): Promise<void>;
  defaultThemes(): Themes;
  themes(): Themes;
  user: UserSettingsApi;
  i18n: {
    t: (
      key: string,
      values?: Record<string, unknown>,
      choice?: number
    ) => string;
    /**
     * @deprecated
     */
    tc: (
      key: string,
      choice?: number,
      values?: Record<string, unknown>
    ) => string;
  };
}

export interface PremiumApi {
  readonly date: DateUtilities;
  readonly data: DataUtilities;
  readonly settings: SettingsApi;
}
