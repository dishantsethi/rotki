<script setup lang="ts">
import { BigNumber } from '@rotki/common';
import { type GeneralAccount } from '@rotki/common/lib/account';
import { Blockchain } from '@rotki/common/lib/blockchain';
import { type Ref } from 'vue';
import { type Module } from '@/types/modules';
import { type GalleryNft, type Nft, type Nfts } from '@/types/nfts';
import { type NftPriceArray } from '@/types/prices';

defineProps<{ modules: Module[] }>();

const { t } = useI18n();

const prices: Ref<NftPriceArray> = ref([]);
const priceError = ref('');
const total = ref(0);
const limit = ref(0);
const error = ref('');
const loading = ref(true);
const perAccount: Ref<Nfts | null> = ref(null);
const sortBy = ref<'name' | 'priceUsd' | 'collection'>('name');
const sortDescending = ref(false);

const { premiumURL } = useInterop();
const css = useCssModule();
const sortProperties = [
  {
    text: t('common.name'),
    value: 'name'
  },
  {
    text: t('common.price'),
    value: 'priceUsd'
  },
  {
    text: t('nft_gallery.sort.collection'),
    value: 'collection'
  }
];

const chains = [Blockchain.ETH];

const { mobile, name: breakpoint, width } = useDisplay();
const page = ref(1);

const itemsPerPage = computed(() => {
  if (get(breakpoint) === 'xs') {
    return 1;
  } else if (get(breakpoint) === 'sm') {
    return 2;
  } else if (get(width) >= 1600) {
    return 10;
  }
  return 8;
});

watch(breakpoint, () => {
  set(page, 1);
});

const selectedAccounts = ref<GeneralAccount[]>([]);
const selectedCollection = ref<string | null>(null);
const premium = usePremium();

watch(selectedAccounts, () => set(page, 1));
watch(selectedCollection, () => set(page, 1));

const items = computed(() => {
  const accounts = get(selectedAccounts);
  const selection = get(selectedCollection);
  const hasAccounts = accounts.length > 0;
  if (hasAccounts || selection) {
    return get(nfts)
      .filter(({ address, collection }) => {
        const sameAccount = hasAccounts
          ? accounts.find(a => a.address === address)
          : true;
        const sameCollection = selection ? selection === collection.name : true;
        return sameAccount && sameCollection;
      })
      .sort((a, b) => sortNfts(sortBy, sortDescending, a, b));
  }

  return get(nfts).sort((a, b) => sortNfts(sortBy, sortDescending, a, b));
});

const pages = computed(() => Math.ceil(get(items).length / get(itemsPerPage)));

const visibleNfts = computed(() => {
  const start = (get(page) - 1) * get(itemsPerPage);
  return get(items).slice(start, start + get(itemsPerPage));
});

const availableAddresses = computed(() =>
  get(perAccount) ? Object.keys(get(perAccount)!) : []
);

const nfts = computed<GalleryNft[]>(() => {
  const addresses: Nfts | null = get(perAccount);
  const value = get(prices);
  if (!addresses) {
    return [];
  }

  const allNfts: GalleryNft[] = [];
  for (const address in addresses) {
    const addressNfts: Nft[] = addresses[address];
    for (const nft of addressNfts) {
      const price = value.find(({ asset }) => asset === nft.tokenIdentifier);
      const { priceEth, priceUsd, ...data } = nft;
      let priceDetails: {
        priceInAsset: BigNumber;
        priceAsset: string;
        priceUsd: BigNumber;
      };
      if (price && price.manuallyInput) {
        priceDetails = {
          priceAsset: price.priceAsset,
          priceInAsset: price.priceInAsset,
          priceUsd: price.usdPrice
        };
      } else {
        priceDetails = {
          priceAsset: 'ETH',
          priceInAsset: priceEth,
          priceUsd
        };
      }

      allNfts.push({ ...data, ...priceDetails, address });
    }
  }
  return allNfts;
});

const collections = computed(() => {
  if (!get(nfts)) {
    return [];
  }
  return get(nfts)
    .map(({ collection }) => collection.name ?? '')
    .filter(uniqueStrings);
});

const { fetchNfts: nftFetch } = useNfts();

const fetchNfts = async (ignoreCache = false) => {
  set(loading, true);
  const { message, result } = await nftFetch(ignoreCache);
  if (result) {
    set(total, result.entriesFound);
    set(limit, result.entriesLimit);
    set(perAccount, result.addresses);
  } else {
    set(error, message);
  }
  set(loading, false);
};

const noData = computed(
  () =>
    get(visibleNfts).length === 0 &&
    !(get(selectedCollection) || get(selectedAccounts).length > 0)
);

const { fetchNftsPrices } = useAssetPricesApi();

const fetchPrices = async () => {
  try {
    const data = await fetchNftsPrices();
    set(prices, data);
  } catch (e: any) {
    set(priceError, e.message);
  }
};

onMounted(fetchPrices);
onMounted(fetchNfts);

const sortNfts = (
  sortBy: Ref<'name' | 'priceUsd' | 'collection'>,
  sortDesc: Ref<boolean>,
  a: GalleryNft,
  b: GalleryNft
): number => {
  const sortProp = get(sortBy);
  const desc = get(sortDesc);
  const isCollection = sortProp === 'collection';
  const aElement = isCollection ? a.collection.name : a[sortProp];
  const bElement = isCollection ? b.collection.name : b[sortProp];
  if (typeof aElement === 'string' && typeof bElement === 'string') {
    return desc
      ? bElement.localeCompare(aElement, 'en', { sensitivity: 'base' })
      : aElement.localeCompare(bElement, 'en', { sensitivity: 'base' });
  } else if (aElement instanceof BigNumber && bElement instanceof BigNumber) {
    return (
      desc ? bElement.minus(aElement) : aElement.minus(bElement)
    ).toNumber();
  } else if (aElement === null && bElement === null) {
    return 0;
  } else if (aElement && !bElement) {
    return desc ? 1 : -1;
  } else if (!aElement && bElement) {
    return desc ? -1 : 1;
  }
  return 0;
};
</script>

<template>
  <ProgressScreen v-if="loading && visibleNfts.length === 0">
    {{ t('nft_gallery.loading') }}
  </ProgressScreen>
  <NoDataScreen v-else-if="noData">
    <template #title>
      {{ error ? t('nft_gallery.error_title') : t('nft_gallery.empty_title') }}
    </template>
    <span class="text-subtitle-2 text--secondary">
      {{ error ? error : t('nft_gallery.empty_subtitle') }}
    </span>
  </NoDataScreen>
  <div v-else class="py-4">
    <VRow justify="space-between">
      <VCol>
        <VRow align="center">
          <VCol :cols="mobile ? '12' : '6'">
            <BlockchainAccountSelector
              v-model="selectedAccounts"
              :label="t('nft_gallery.select_account')"
              :chains="chains"
              dense
              outlined
              no-padding
              flat
              :usable-addresses="availableAddresses"
            />
          </VCol>
          <VCol :cols="mobile ? '12' : '6'">
            <VCard flat>
              <div>
                <VAutocomplete
                  v-model="selectedCollection"
                  :label="t('nft_gallery.select_collection')"
                  single-line
                  clearable
                  hide-details
                  hide-selected
                  :items="collections"
                  outlined
                  background-color=""
                  dense
                />
              </div>
            </VCard>
          </VCol>
          <VCol :cols="mobile ? '12' : '6'">
            <SortingSelector
              :sort-by="sortBy"
              :sort-properties="sortProperties"
              :sort-desc="sortDescending"
              @update:sort-by="sortBy = $event"
              @update:sort-desc="sortDescending = $event"
            />
          </VCol>
          <VCol :cols="mobile ? '12' : '6'">
            <Pagination v-if="pages > 0" v-model="page" :length="pages" />
          </VCol>
        </VRow>
      </VCol>
      <VCol cols="auto" class="pr-0">
        <NftImageRenderingSettingMenu />
      </VCol>
      <VCol cols="auto" class="pr-0">
        <ActiveModules :modules="modules" />
      </VCol>
      <VCol cols="auto">
        <RefreshButton
          :loading="loading"
          :tooltip="t('nft_gallery.refresh_tooltip')"
          @refresh="fetchNfts(true)"
        />
      </VCol>
    </VRow>
    <VRow v-if="!premium && visibleNfts.length > 0" justify="center">
      <VCol cols="auto">
        <I18n path="nft_gallery.upgrade">
          <template #limit> {{ limit }}</template>
          <template #link>
            <BaseExternalLink
              :text="t('upgrade_row.rotki_premium')"
              :href="premiumURL"
            />
          </template>
        </I18n>
      </VCol>
    </VRow>
    <VRow
      v-if="visibleNfts.length === 0"
      align="center"
      justify="center"
      :class="css.empty"
    >
      <VCol cols="auto" class="text--secondary text-h6">
        {{ t('nft_gallery.empty_filter') }}
      </VCol>
    </VRow>
    <VRow v-else>
      <VCol
        v-for="item in visibleNfts"
        :key="item.tokenIdentifier"
        cols="12"
        sm="6"
        md="6"
        lg="3"
        :class="css.xl"
      >
        <NftGalleryItem :item="item" />
      </VCol>
    </VRow>
  </div>
</template>

<style module lang="scss">
.empty {
  min-height: 80vh;
}

.xl {
  @media only screen and (min-width: 1600px) {
    flex: 0 0 20% !important;
    max-width: 20% !important;
  }
}
</style>
