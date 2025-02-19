<script setup lang="ts">
import { EvmTokenKind, type UnderlyingToken } from '@rotki/common/lib/data';
import useVuelidate from '@vuelidate/core';
import { between, helpers, numeric, required } from '@vuelidate/validators';
import { evmTokenKindsData } from '@/types/blockchain/chains';

const props = defineProps<{ value: UnderlyingToken[] }>();

const emit = defineEmits<{ (e: 'input', value: UnderlyingToken[]): void }>();
const { t } = useI18n();

const { value } = toRefs(props);

const input = (value: UnderlyingToken[]) => emit('input', value);

const underlyingAddress = ref<string>('');
const tokenKind = ref<EvmTokenKind>(EvmTokenKind.ERC20);
const underlyingWeight = ref<string>('');
const form = ref<any>(null);

const rules = {
  address: {
    required: helpers.withMessage(
      t('underlying_token_manager.validation.address_non_empty'),
      required
    ),
    isValidEthAddress: helpers.withMessage(
      t('underlying_token_manager.validation.valid'),
      isValidEthAddress
    )
  },
  weight: {
    required: helpers.withMessage(
      t('underlying_token_manager.validation.non_empty'),
      required
    ),
    notNaN: helpers.withMessage(
      t('underlying_token_manager.validation.not_valid'),
      numeric
    ),
    minMax: helpers.withMessage(
      t('underlying_token_manager.validation.out_of_range'),
      between(1, 100)
    )
  }
};

const v$ = useVuelidate(
  rules,
  {
    address: underlyingAddress,
    weight: underlyingWeight
  },
  { $autoDirty: true, $stopPropagation: true }
);

const addToken = () => {
  const underlyingTokens = [...get(value)];
  const index = underlyingTokens.findIndex(
    ({ address }) => address === get(underlyingAddress)
  );

  const token = {
    address: get(underlyingAddress),
    tokenKind: get(tokenKind),
    weight: get(underlyingWeight)
  };

  if (index >= 0) {
    underlyingTokens[index] = token;
  } else {
    underlyingTokens.push(token);
  }

  (get(form) as any)?.reset();
  get(v$).$reset();
  input(underlyingTokens);
};

const editToken = (token: UnderlyingToken) => {
  set(underlyingAddress, token.address);
  set(tokenKind, token.tokenKind);
  set(underlyingWeight, token.weight);
  deleteToken(token.address);
};

const deleteToken = (address: string) => {
  const underlyingTokens = [...get(value)];
  input(
    underlyingTokens.filter(
      ({ address: tokenAddress }) => tokenAddress !== address
    )
  );
};
</script>

<template>
  <VForm ref="form" :value="!v$.$invalid">
    <div class="text-h6">
      {{ t('underlying_token_manager.labels.tokens') }}
    </div>
    <VRow class="mt-2">
      <VCol cols="12" md="7">
        <VTextField
          v-model="underlyingAddress"
          :error-messages="v$.address.$errors.map(e => e.$message)"
          outlined
          :label="t('common.address')"
        />
      </VCol>
      <VCol cols="12" md="2">
        <VSelect
          v-model="tokenKind"
          outlined
          :label="t('asset_form.labels.token_kind')"
          :items="evmTokenKindsData"
          item-text="label"
          item-value="identifier"
        />
      </VCol>
      <VCol cols="12" md="3">
        <VTextField
          v-model="underlyingWeight"
          type="number"
          max="100"
          min="1"
          :error-messages="v$.weight.$errors.map(e => e.$message)"
          persistent-hint
          :hint="t('underlying_token_manager.hint')"
          outlined
          :label="t('underlying_token_manager.labels.weight')"
        >
          <template #append-outer>
            <VBtn
              icon
              :disabled="v$.$invalid"
              class="mt-n2"
              @click="addToken()"
            >
              <VIcon>mdi-plus</VIcon>
            </VBtn>
          </template>
        </VTextField>
      </VCol>
    </VRow>
    <VSheet outlined rounded class="underlying-tokens">
      <VSimpleTable fixed-header height="200px">
        <thead>
          <tr>
            <th>{{ t('common.address') }}</th>
            <th>{{ t('underlying_token_manager.tokens.token_kind') }}</th>
            <th>{{ t('underlying_token_manager.tokens.weight') }}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="token in value" :key="token.address">
            <td class="grow">{{ token.address }}</td>
            <td class="shrink">{{ token.tokenKind.toUpperCase() }}</td>
            <td class="shrink text-no-wrap">
              {{
                t('underlying_token_manager.tokens.weight_percentage', {
                  weight: token.weight
                })
              }}
            </td>
            <td>
              <RowActions
                :edit-tooltip="t('underlying_token_manager.edit_tooltip')"
                :delete-tooltip="t('underlying_token_manager.delete_tooltip')"
                @delete-click="deleteToken(token.address)"
                @edit-click="editToken(token)"
              />
            </td>
          </tr>
        </tbody>
      </VSimpleTable>
    </VSheet>
  </VForm>
</template>
