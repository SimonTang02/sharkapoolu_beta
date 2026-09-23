# Other Job Boards to Consider

This is a watchlist for future adapters. The goal is not to add every source immediately, but to prioritize sources that are useful for China/Hong Kong/US hardware, semiconductor, EDA, digital IC, analog IC, verification, and computer-architecture roles.

## Mainland China

| Platform | Best use | Bot priority | Notes |
| --- | --- | --- | --- |
| 智联招聘 / Zhaopin | General full-time and campus roles | Medium | Broad coverage; likely noisy, but useful for larger employers and manufacturing/semiconductor hiring. |
| 前程无忧 / 51job | General full-time, campus, lower-tier cities | Medium | Useful for traditional electronics/manufacturing companies. |
| 猎聘 / Liepin | Experienced full-time roles | Low for internships, medium for full-time | Better for senior/experienced hiring than intern search. |
| 脉脉 / Maimai | Company discovery, referrals, passive opportunities | Low as crawler, high as manual reference | Social/network-heavy; better for finding people and hidden opportunities than pure scraping. |
| 牛客 / Nowcoder | Campus recruiting and written-test prep | Medium | Useful for 校招/实习 information, especially tech-campus cycles. |
| 应届生求职网 / Yingjiesheng | Campus recruiting | Medium | Often useful for campus timelines and announcements. |
| 海投网 / Haitou | Campus recruiting aggregator | Medium | Good for school-year pipelines, but needs duplicate control. |

## Hong Kong

| Platform | Best use | Bot priority | Notes |
| --- | --- | --- | --- |
| JIJIS | University-vetted internships and graduate roles | High if account access is available | Good quality for Hong Kong students; usually requires eligible university login. |
| CUHK CU Careers / CU Job Link | CUHK student/fresh-grad postings and campus events | High if account access works | CPDC portal/app can expose job postings; CUHK Login may require 2FA/DUO, so cookie/session export is likely safer than raw password automation. |
| CTgoodjobs | Local Hong Kong full-time roles | Medium | Good broad local board; may include engineering/technology roles. |
| CPJobs | Professional roles | Medium | Useful for Hong Kong professional and mid-level roles. |
| LinkedIn Jobs | Multinational companies, referrals | High as manual/alert source | Strong for foreign companies and networking; login/API limits mean email alerts or saved searches may be safer. |
| Indeed Hong Kong | Aggregated postings | Medium | Good breadth; duplicates need handling. |
| eFinancialCareers | Finance/quant/fintech hardware-adjacent roles | Low for IC, medium for quant/finance | Useful only if widening target direction. |

## United States

| Platform | Best use | Bot priority | Notes |
| --- | --- | --- | --- |
| LinkedIn Jobs | Big tech, semiconductor, networking/referrals | High as manual/alert source | Best combined with saved searches and email alerts. |
| Indeed | Broad job aggregation | Medium | Very broad; useful with strict filters and dedupe. |
| Handshake | University internships/new-grad roles | High if school account access is available | Strong for internships and campus roles. |
| Simplify | Internship/new-grad tracking and autofill workflow | High for manual workflow | Useful for application management; check integration constraints before automation. |
| RippleMatch | Early-career matching | Medium | Better for early-career pipeline than raw scraping. |
| Wellfound | Startups | Medium | Good for smaller chip/AI hardware startups when target is broadened. |
| Otta / Welcome to the Jungle | Curated tech roles | Low to medium | More software/product heavy; still useful for some hardware-adjacent startups. |
| Built In | US tech companies by region | Medium | Useful for city-specific searches. |
| USAJobs | Government/research lab roles | Low for private IC internships | Useful only for government/public-sector paths. |

## Recommended next adapters

1. JIJIS, if your school access works and you want Hong Kong student-vetted roles.
2. Handshake, if your Penn access exposes hardware/semiconductor internships.
3. LinkedIn saved-search email ingestion, because direct scraping is fragile but email alerts are stable.
4. Zhaopin/51job for mainland full-time/campus breadth.
5. Simplify for application tracking/autofill support, not blind auto-submit.
