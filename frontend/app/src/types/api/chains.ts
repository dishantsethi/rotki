import { z } from 'zod';

export const ChainInfo = z.object({
  name: z.string(),
  type: z.string(),
  evmChainName: z.string().nullish()
});

export type ChainInfo = z.infer<typeof ChainInfo>;

export const SupportedChains = z.array(ChainInfo);

export type SupportedChains = z.infer<typeof SupportedChains>;
