# India Crypto Venue Review

**Review date:** 11 November 2026  
**Scope:** Public official exchange/regulator material. This is an engineering access review, not a legal opinion or account-specific confirmation.

## Decision

Do not hard-code a venue as legally approved. Keep the exchange allowlist empty until the operator's verified residence, account entity, product eligibility, API permissions and legal review have been confirmed.

Two venues merit account-level verification for an India profile. Neither should be auto-enabled by the platform.

## Venue findings

| Venue | Official evidence found | Engineering conclusion |
|---|---|---|
| Coinbase India | Coinbase's India help page lists cash balances/deposits/withdrawals, crypto buys/sells, Advanced Trade and perpetual futures. Its India user agreement says Advanced Trade API access is available subject to jurisdiction, and derivatives API access is only where available and eligible. The derivatives service is brokered by Coinbase India on Deribit, not a generic Coinbase International perpetual account. | **First candidate for account-level verification.** Spot API and derivatives API/product eligibility must be separately confirmed in the user's verified account. A dedicated derivatives adapter may be required; do not assume standard CCXT Coinbase covers the India/Deribit route. |
| Binance | Binance's legal page lists Nest Exchange Limited as an offshore FIU-IND reporting entity. Binance's India API-key help page documents KYC, 2FA, API permissions and IP restrictions; it notes Futures permission depends on Futures account activation and other account settings. FIU-IND's 19 June 2024 order imposed a ₹18.82 crore penalty for prior PMLA compliance violations. | **Second candidate for account-level verification.** FIU registration is AML reporting-entity status, not a blanket product licence or guarantee of a particular user's access. Verify Spot and Futures tabs, API permissions, contract availability, account entity and current terms. Use IP allowlisting and never grant withdrawals. |
| Kraken | Kraken's licensing page, updated 30 September 2026, says service availability depends on verified residence and product-specific restrictions. Its published jurisdiction list did not provide India-specific confirmation in the material reviewed. | **Not recommended yet.** Obtain explicit India residency and product/API confirmation from Kraken before using it. Absence from the licensing list is not proof of a prohibition. |
| OKX | OKX's API agreement, updated 28 July 2026, requires a verified account and jurisdiction/product eligibility. It restricts market-data use to personal, non-commercial trading/account management, and prohibits commercial redistribution or using the data to train/evaluate commercial AI systems without permission. No India-specific account/product confirmation was established in this review. | **Not recommended yet.** Verify India account eligibility and the intended data-use terms. Do not use OKX data in a commercial product or commercial AI training without written rights. |

## API security requirements

- Create a dedicated API key per application and account.
- Enable read and trade only when required; never enable withdrawal/transfer permissions.
- Use IP allowlisting wherever the venue supports it.
- Separate spot and derivatives keys if the venue supports distinct permissions.
- Use test/sandbox environments before paper or live routing.
- Confirm the key's actual permission matrix from the account UI and test read-only endpoints first.
- Re-check product eligibility, symbol availability, rate limits and API terms at each release. Account UI and legal terms override generic API documentation.

## Official sources

- Coinbase India availability: https://help.coinbase.com/en-in/coinbase/getting-started/getting-started-with-coinbase/india-whats-available
- Coinbase India user agreement: https://www.coinbase.com/legal/user_agreement/india
- Binance licenses and registrations: https://merchant.binance.com/en-GB/legal/licenses/
- Binance India API key setup and permissions: https://www.binance.com/en-IN/support/faq/detail/360002502072
- FIU-IND Binance order, 19 June 2024: https://www.fiuindia.gov.in/pdfs/judgements/Binance_Order_10_2024.pdf
- Kraken licenses and regional restrictions: https://support.kraken.com/articles/where-is-kraken-licensed-or-regulated
- OKX API agreement: https://www.okx.com/help/okx-api-agreement
- OKX API documentation: https://www.okx.com/docs-v5/en/

## What this review does not establish

- It does not establish that the operator is an India tax resident. Tax residency and actual location may differ.
- It does not establish that a particular account can access every product listed on a help page.
- It does not determine whether a specific perpetual contract is appropriate or lawful for the operator.
- It does not confirm current fees, margin tiers, funding schedules, minimum order sizes, liquidation mechanics or API rate limits.
- It does not authorize automated execution.

Before a venue is added to a live allowlist, verify the exact legal contracting entity, current account access, product permissions, API scopes, and relevant legal/tax treatment for the operator's actual residence.
