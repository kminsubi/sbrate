# Executive Matrix Phase 2 FISIS Mapping

The executive four-peer matrix must not manufacture ratios or management-report
lines that are not backed by verified FISIS accounts.

## Verified source mappings

| Candidate metric | FISIS table | Account | Official account label | Rollout |
|---|---|---|---|---|
| Loan interest income | SE014 | A13 | 이자수익_대출채권이자 | already collected |
| Loan receivable trading gain | SE006 | A40 | 대출채권관련수익_대출채권매매이익 | collector pending |
| Loan receivable trading loss | SE006 | B530 | 대출채권관련손실_대출채권매매손실 | collector pending |
| Borrowing interest expense | SE014 | A22 | 이자비용_차입금이자 | collector pending |
| Bond interest expense | SE014 | A23 | 이자비용_사채이자 | collector pending |

The source mapping above was verified against the repository's FISIS catalog
snapshot (`data/fisis_catalog_summary.json`).

## Loan interest yield

Do **not** calculate a loan-interest yield by dividing cumulative loan interest
income by quarter-end loans and present it as the official yield.

The current FISIS catalog exposes loan interest income, but a verified
quarterly average-loan balance denominator was not found. Until an appropriate
average-balance source is verified, the matrix shows the loan-interest income
amount only and keeps loan-interest yield pending.

## Loan receivable trading P/L

Once collection is enabled, the natural net presentation is:

```text
loan receivable trading net P/L
= SE006 A40 trading gain - SE006 B530 trading loss
```

The collector change should be canaried before it becomes part of the live
management cache.
