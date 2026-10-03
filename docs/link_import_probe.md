# Paste-a-link: all 16 real URLs tried on 2026-10-03 (Beijing time)

Run from the build machine's network, one GET per page, honest user agent (`TodaysOutfit/0.3 ... single page fetch`, the app's name before it was renamed Dresser), no login, no JavaScript. 4 of 16 worked.

Sources: the first 4 rows and rows 5, 6, 7, 9 are in the checked-in probe output [`link_import_run.txt`](link_import_run.txt) (full pipeline with the vision model for the successes). Rows 8 and 10-16 come from my earlier page-only probes during the build (same code, no vision step); their raw output was not saved as a file, so they are recorded here from my notes of those runs.
The probe tool is `tools/link_import_probe.py URL ...`.

| # | Page | Result | Kind | What the user sees / what happened | In `link_import_run.txt` |
|---|---|---|---|---|---|
| 1 | allbirds.com Men's Tree Runner | **worked** | - | title + picture + fields (shoes / sneaker / black), 16.3 s with the vision model | yes |
| 2 | everlane.com Box-Cut Tee | **worked** | - | top / t-shirt / white / cotton, 13.6 s | yes |
| 3 | uniqlo.com/jp crew-neck T-shirt | **worked** | - | top / t-shirt / light gray / cotton, 17.6 s | yes |
| 4 | nike.com Air Force 1 '07 | **worked** | - | shoes / sneakers / white / leather, 21.1 s | yes |
| 5 | zara.com (guessed product URL) | failed | blocked | the shop answered HTTP 403 to the automated request | yes |
| 6 | patagonia.com Better Sweater | failed | no-data | page loads, but no product picture in the HTML (built with JavaScript) | yes |
| 7 | item.taobao.com item.htm?id=1 | failed | no-data | no picture in the HTML: "render products with JavaScript or require a login" message | yes |
| 8 | detail.tmall.com item.htm?id=1 | failed | no-data | same message as Taobao | no |
| 9 | xiaohongshu.com/explore/ (invented note id) | failed | no-data | a "page gone" page whose only picture is a 4.5 KB logo; rejected as "tiny, not a product photo" (before that check existed it was wrongly accepted) | yes |
| 10 | uniqlo.com/us product page | failed | network | no answer within the 10 s timeout from this network | no |
| 11 | llbean.com product page | failed | no-data | no picture in the HTML | no |
| 12 | hm.com (www2.hm.com/en_gb) | failed | refused | this machine's DNS answered 198.18.0.1, a non-public address, so the SSRF guard refused it; says nothing about H&M itself | no |
| 13 | muji.com/jp product page | failed | blocked | HTTP 403 | no |
| 14 | gap.com product page | failed | no-data | no picture in the HTML | no |
| 15 | asos.com product page | failed | network | no answer within 10 s | no |
| 16 | bonobos.com product page | failed | no-data | HTTP 404: my guessed URL was wrong, not the shop refusing | no |

Not a shop, also in `link_import_run.txt`: `http://127.0.0.1:8000/api/status` is refused by the SSRF guard (non-standard port; loopback anyway).

Reading it: pages that put the product picture in the HTML (simple server-rendered shops) work; big chains and the Chinese marketplaces mostly do not. Rows 12 and 16 are not the shops' fault; 10 and 15 may be my network. A real Xiaohongshu post and a real Taobao item page were never tried.
